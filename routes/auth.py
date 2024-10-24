from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from extensions import mysql, limiter
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
from flask_wtf.csrf import CSRFError
from security import security_headers
import datetime
import jwt
import os
import secrets
import re
import MySQLdb

bp = Blueprint('auth', __name__)

# Configuración
SECRET_KEY = os.environ.get('SECRET_KEY', 'tu_clave_secreta_aqui')
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 15 * 60  # 15 minutos en segundos

# Configuración de Argon2id
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    encoding='utf-8',
    type=Type.ID
)

def is_password_strong(password):
    if len(password) < 12:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    if not re.search("[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def generate_token(user_id):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    token = jwt.encode({
        'user_id': user_id,
        'exp': expiration,
        'jti': secrets.token_hex(16)
    }, SECRET_KEY, algorithm='HS256')
    return token, expiration

def verify_token(token):
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return data['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def revoke_token(token):
    # Aquí implementarías la lógica para revocar el token
    # Por ejemplo, añadirlo a una lista negra en la base de datos
    pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('remember_token')
        if token:
            user_id = verify_token(token)
            if user_id:
                session['user_id'] = user_id
                return f(*args, **kwargs)
        return redirect(url_for('auth.login'))
    return decorated_function

@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
@security_headers
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if not is_password_strong(password):
            flash('La contraseña debe tener al menos 12 caracteres, incluir mayúsculas, '
                  'minúsculas, números y caracteres especiales.', 'danger')
            return render_template('register.html')

        cur = mysql.connection.cursor()
        try:
            # Generar hash con Argon2id
            password_hash = ph.hash(password)
            
            cur.execute("""
                INSERT INTO usuarios (username, password_hash, email, created_at) 
                VALUES (%s, %s, %s, NOW())
            """, (username, password_hash, email))
            
            mysql.connection.commit()
            flash('Registro exitoso. Por favor inicia sesión.', 'success')
            return redirect(url_for('auth.login'))
            
        except MySQLdb.IntegrityError:
            flash('El nombre de usuario o email ya existe.', 'danger')
        except MySQLdb.Error as e:
            flash(f'Error al registrar: {str(e)}', 'danger')
        finally:
            cur.close()
    
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
@security_headers
def login():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                # Verificar si la cuenta está bloqueada
                cur.execute('''
                    SELECT * FROM usuarios 
                    WHERE username = %s AND (
                        locked_until IS NULL OR 
                        locked_until < NOW()
                    )
                ''', (username,))
                user = cur.fetchone()
                
                if user:
                    try:
                        # Verificar contraseña con Argon2id
                        if ph.verify(user['password_hash'], password):
                            # Si el hash necesita ser actualizado (por cambios en los parámetros)
                            if ph.check_needs_rehash(user['password_hash']):
                                new_hash = ph.hash(password)
                                cur.execute("""
                                    UPDATE usuarios 
                                    SET password_hash = %s 
                                    WHERE id = %s
                                """, (new_hash, user['id']))
                            
                            # Reset failed attempts y crear nueva sesión
                            session_id = secrets.token_urlsafe(32)
                            cur.execute("""
                                UPDATE usuarios 
                                SET failed_attempts = 0, 
                                    locked_until = NULL,
                                    session_id = %s,
                                    last_login = NOW()
                                WHERE id = %s
                            """, (session_id, user['id']))
                            
                            session.clear()
                            session['user_id'] = user['id']
                            session['username'] = user['username']
                            session['session_id'] = session_id
                            session['created_at'] = datetime.datetime.now().isoformat()
                            
                            mysql.connection.commit()
                            return redirect(url_for('friends.manage_friends'))
                    except VerifyMismatchError:
                        pass
                    
                # Incrementar intentos fallidos
                cur.execute("""
                    UPDATE usuarios 
                    SET failed_attempts = COALESCE(failed_attempts, 0) + 1,
                        locked_until = CASE 
                            WHEN COALESCE(failed_attempts, 0) + 1 >= 5 
                            THEN DATE_ADD(NOW(), INTERVAL 15 MINUTE)
                            ELSE NULL 
                        END
                    WHERE username = %s
                """, (username,))
                mysql.connection.commit()
                
                flash('Usuario o contraseña incorrectos.', 'danger')
                
            except MySQLdb.Error as e:
                flash(f'Error al iniciar sesión: {str(e)}', 'danger')
            finally:
                cur.close()
    except CSRFError:
        flash('Error de seguridad. Por favor, intenta de nuevo.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('login.html')

@bp.route('/logout')
def logout():
    token = request.cookies.get('remember_token')
    if token:
        revoke_token(token)
    session.pop('user_id', None)
    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('remember_token')
    flash('Has cerrado sesión.', 'success')
    return response

@bp.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('La sesión ha expirado o la petición no es válida. Por favor, intenta de nuevo.', 'danger')
    return redirect(url_for('auth.login'))
