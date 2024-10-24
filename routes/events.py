from flask_socketio import emit, join_room, leave_room
from extensions import socketio, mysql
from flask import session, request
from crypto_utils import ChatCrypto  # Solo importamos la clase
from datetime import datetime
import MySQLdb
from auth_middleware import socket_auth_required  # Añadir esta importación

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('status', {'msg': f'{username} ha entrado al chat.'}, room=room)

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('status', {'msg': f'{username} ha salido del chat.'}, room=room)

@socketio.on('message')
def handle_message(data):
    emit('message', data, room=data['room'])

@socketio.on('send_message')
@socket_auth_required
def handle_message(data):
    try:
        sender_id = session['user_id']
        receiver_id = data['receiver_id']
        encrypted_data = data['encrypted_data']
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO mensajes (sender_id, receiver_id, content, nonce)
                VALUES (%s, %s, %s, %s)
            """, (sender_id, receiver_id, encrypted_data['ciphertext'], encrypted_data['nonce']))
            mysql.connection.commit()
            
            room = f"chat_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
            emit('new_message', {
                'id': cur.lastrowid,
                'sender_id': sender_id,
                'encrypted_data': encrypted_data,
                'timestamp': datetime.now().isoformat()
            }, room=room)
        finally:
            cur.close()
    except Exception as e:
        print(f"Error en handle_message: {str(e)}")
        emit('error', {'message': 'Error interno del servidor'}, room=request.sid)

@socketio.on('key_rotation')
def handle_key_rotation(data):
    sender_id = session['user_id']
    receiver_id = data['receiver_id']
    crypto = ChatCrypto(str(sender_id), str(receiver_id))
    new_version = crypto.rotate_key()
    
    room = f"chat_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
    emit('key_updated', {'version': new_version}, room=room)

@socketio.on('join_chat')
@socket_auth_required
def on_join_chat(data):
    try:
        friend_id = data['friend_id']
        room = f"chat_{min(session['user_id'], friend_id)}_{max(session['user_id'], friend_id)}"
        join_room(room)
        print(f"{request.sid} is entering room {room}")
    except Exception as e:
        print(f"Error en join_chat: {str(e)}")
        return False

@socketio.on('connect')
@socket_auth_required
def handle_connect():
    print(f"Cliente conectado: {request.sid}")
    return True

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Cliente desconectado: {request.sid}")

@socketio.on_error()
def error_handler(e):
    print(f"Error en Socket.IO: {str(e)}")
