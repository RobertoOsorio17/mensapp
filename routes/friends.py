from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import mysql, limiter, csrf
import MySQLdb
from auth_middleware import login_required

bp = Blueprint('friends', __name__)

@bp.route('/', methods=['GET', 'POST'])
@login_required
@limiter.limit("30 per minute")
def manage_friends():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Obtener solicitudes de amistad pendientes
        cur.execute("""
            SELECT u.id, u.username 
            FROM amigos a 
            JOIN usuarios u ON a.user_id = u.id 
            WHERE a.friend_id = %s AND a.status = 'pending'
        """, (session['user_id'],))
        requests = cur.fetchall()

        # Obtener lista de amigos
        cur.execute("""
            SELECT u.id, u.username 
            FROM amigos a 
            JOIN usuarios u ON a.friend_id = u.id 
            WHERE a.user_id = %s AND a.status = 'accepted'
        """, (session['user_id'],))
        friends = cur.fetchall()

        if request.method == 'POST':
            friend_username = request.form['friend_username']
            cur.execute("SELECT id FROM usuarios WHERE username = %s", (friend_username,))
            friend = cur.fetchone()
            if friend:
                cur.execute("""
                    INSERT INTO amigos (user_id, friend_id, status) 
                    VALUES (%s, %s, 'pending')
                    ON DUPLICATE KEY UPDATE status = 'pending'
                """, (session['user_id'], friend['id']))
                mysql.connection.commit()
                flash('Solicitud de amistad enviada.', 'success')
            else:
                flash('Usuario no encontrado.', 'danger')

        return render_template('friends.html', friends=friends, requests=requests)

    except MySQLdb.Error as e:
        flash(f'Ocurrió un error: {str(e)}', 'danger')
        return redirect(url_for('friends.manage_friends'))
    finally:
        cur.close()

@bp.route('/accept_friend/<int:friend_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def accept_friend(friend_id):
    cur = mysql.connection.cursor()
    try:
        # Actualizar la solicitud existente
        cur.execute("""
            UPDATE amigos 
            SET status = 'accepted' 
            WHERE user_id = %s AND friend_id = %s AND status = 'pending'
        """, (friend_id, session['user_id']))
        
        # Crear la relación recíproca
        cur.execute("""
            INSERT INTO amigos (user_id, friend_id, status)
            VALUES (%s, %s, 'accepted')
            ON DUPLICATE KEY UPDATE status = 'accepted'
        """, (session['user_id'], friend_id))
        
        if cur.rowcount == 0:
            return jsonify({
                'success': False,
                'message': 'No se encontró la solicitud de amistad o ya ha sido procesada.'
            })
        
        mysql.connection.commit()
        return jsonify({
            'success': True,
            'message': 'Solicitud de amistad aceptada.'
        })
    except MySQLdb.Error as e:
        return jsonify({
            'success': False,
            'message': f'Ocurrió un error: {str(e)}'
        })
    finally:
        cur.close()

@bp.route('/reject_friend/<int:friend_id>', methods=['POST'])
@login_required
def reject_friend(friend_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            DELETE FROM amigos 
            WHERE user_id = %s AND friend_id = %s AND status = 'pending'
        """, (friend_id, session['user_id']))
        
        if cur.rowcount == 0:
            return jsonify({
                'success': False,
                'message': 'No se encontró la solicitud de amistad o ya ha sido procesada.'
            })
        
        mysql.connection.commit()
        return jsonify({
            'success': True,
            'message': 'Solicitud de amistad rechazada.'
        })
    except MySQLdb.Error as e:
        return jsonify({
            'success': False,
            'message': f'Ocurrió un error: {str(e)}'
        })
    finally:
        cur.close()

@bp.route('/list', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def get_friends_list():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("""
            SELECT u.id, u.username 
            FROM amigos a 
            JOIN usuarios u ON a.friend_id = u.id 
            WHERE a.user_id = %s AND a.status = 'accepted'
        """, (session['user_id'],))
        friends = cur.fetchall()
        return jsonify({'success': True, 'friends': friends})
    except MySQLdb.Error as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()

@bp.route('/requests', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def get_friend_requests():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("""
            SELECT u.id, u.username 
            FROM amigos a 
            JOIN usuarios u ON a.user_id = u.id 
            WHERE a.friend_id = %s AND a.status = 'pending'
        """, (session['user_id'],))
        requests = cur.fetchall()
        return jsonify({'success': True, 'requests': requests})
    except MySQLdb.Error as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()

@bp.route('/chat/<int:friend_id>')
@login_required
def chat(friend_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Verificar si el usuario es amigo
        cur.execute("""
            SELECT * FROM amigos 
            WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s) 
            AND status = 'accepted'
        """, (session['user_id'], friend_id, friend_id, session['user_id']))
        friendship = cur.fetchone()
        
        if not friendship:
            flash('No tienes permiso para chatear con este usuario.', 'danger')
            return redirect(url_for('friends.manage_friends'))

        # Obtener los últimos 50 mensajes
        cur.execute("""
            SELECT sender_id, receiver_id, 
                   HEX(content) as content, 
                   HEX(nonce) as nonce, 
                   timestamp 
            FROM mensajes 
            WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
            ORDER BY timestamp DESC LIMIT 50
        """, (session['user_id'], friend_id, friend_id, session['user_id']))
        messages = list(cur.fetchall())
        messages.reverse()

        # Obtener información del amigo
        cur.execute("SELECT username FROM usuarios WHERE id = %s", (friend_id,))
        friend = cur.fetchone()

        # Generar chat_id
        chat_id = f"{min(session['user_id'], friend_id)}_{max(session['user_id'], friend_id)}"
        
        return render_template('chat.html', 
                             friend_id=friend_id, 
                             friend_username=friend['username'], 
                             messages=messages,
                             chat_id=chat_id)

    except MySQLdb.Error as e:
        flash(f'Ocurrió un error: {str(e)}', 'danger')
        return redirect(url_for('friends.manage_friends'))
    finally:
        cur.close()
