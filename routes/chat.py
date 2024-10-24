from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import mysql, limiter, socketio
from flask_socketio import emit, join_room, leave_room
from utils import login_required
import MySQLdb
import datetime
from crypto_utils import ChatCrypto
from datetime import datetime, timedelta
from auth_middleware import login_required, socket_auth_required

bp = Blueprint('chat', __name__)

@bp.route('/chat/<int:friend_id>')
@login_required
@limiter.limit("60 per minute")
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

def get_chat_session(user_id: str, friend_id: str) -> ChatCrypto:
    session_key = f"chat_session_{min(user_id, friend_id)}_{max(user_id, friend_id)}"
    
    # Crear nueva instancia si no existe o si es un diccionario
    if session_key not in session or not isinstance(session[session_key], ChatCrypto):
        crypto = ChatCrypto(user_id, friend_id)
        session[session_key] = crypto
        return crypto
    
    return session[session_key]

@socketio.on('send_message')
def handle_message(data):
    try:
        sender_id = session['user_id']
        receiver_id = data['receiver_id']
        encrypted_data = data['encrypted_data']
        
        # Convertir a bytes antes de almacenar
        ciphertext = bytes.fromhex(encrypted_data['ciphertext'])
        nonce = bytes.fromhex(encrypted_data['nonce'])
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO mensajes (sender_id, receiver_id, content, nonce)
                VALUES (%s, %s, %s, %s)
            """, (sender_id, receiver_id, ciphertext, nonce))
            mysql.connection.commit()
            
            room = f"chat_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
            emit('new_message', {
                'sender_id': sender_id,
                'encrypted_data': encrypted_data,
                'timestamp': datetime.now().isoformat()
            }, room=room)
        finally:
            cur.close()
    except Exception as e:
        print(f"Error en handle_message: {str(e)}")
        emit('error', {'message': 'Error interno del servidor'}, room=request.sid)

@socketio.on('join_chat')
def handle_join_chat(data):
    friend_id = data.get('friend_id')
    if friend_id:
        chat_id = f"{min(session['user_id'], friend_id)}_{max(session['user_id'], friend_id)}"
        session['current_chat'] = chat_id

@socketio.on('leave_chat')
def on_leave_chat(data):
    room = f"chat_{min(session['user_id'], data['friend_id'])}_{max(session['user_id'], data['friend_id'])}"
    leave_room(room)
