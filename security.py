from functools import wraps
from flask import make_response

def security_headers(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://code.getmdl.io; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://code.getmdl.io; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:;"
        return response
    return decorated_function
