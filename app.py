# app.py
from flask import Flask, redirect, url_for, jsonify, session
from flask_wtf.csrf import CSRFProtect, generate_csrf
from dotenv import load_dotenv
from extensions import mysql, socketio, csrf, limiter  # Importamos socketio de extensions
import os
from flask_session import Session
from datetime import timedelta

def create_app():
    app = Flask(__name__)
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Configuración básica
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'tu_clave_secreta_aqui'),
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_session'),
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=3600,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        # Configuración MySQL
        MYSQL_HOST=os.environ.get('MYSQL_HOST', 'localhost'),
        MYSQL_USER=os.environ.get('MYSQL_USER', 'root'),
        MYSQL_PASSWORD=os.environ.get('MYSQL_PASSWORD', ''),
        MYSQL_DB=os.environ.get('MYSQL_DB', 'mensapp'),
        MYSQL_CURSORCLASS='DictCursor',
        MYSQL_AUTOCOMMIT=True,
        MYSQL_CHARSET='utf8mb4'
    )
    
    # Asegurarse de que el directorio de sesiones existe
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    
    # Inicializar extensiones en orden correcto
    Session(app)
    mysql.init_app(app)
    csrf.init_app(app)
    
    # Inicializar Socket.IO después de las otras extensiones
    socketio.init_app(
        app,
        manage_session=False,
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True,
        ping_timeout=60,
        async_mode='threading'
    )
    
    # Registrar blueprints
    from routes import auth, friends, chat
    app.register_blueprint(auth.bp, url_prefix='/auth')
    app.register_blueprint(friends.bp, url_prefix='/friends')
    app.register_blueprint(chat.bp, url_prefix='/chat')
    
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    return app

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True)

