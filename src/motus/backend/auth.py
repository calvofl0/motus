"""
Token-based authentication (Jupyter-style)
Simple token parameter check for single-user apps
"""
from functools import wraps
from flask import request, jsonify, current_app


def token_required(f):
    """
    Decorator to require token authentication
    Token can be provided via:
    - Query parameter: ?token=xxx
    - Header: Authorization: token xxx
    - Cookie: motus_token=xxx
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check query parameter
        token = request.args.get('token')

        # Check Authorization header
        if not token and 'Authorization' in request.headers:
            auth = request.headers['Authorization']
            if auth.startswith('token '):
                token = auth[6:]  # Remove 'token ' prefix

        # Check cookie
        if not token:
            token = request.cookies.get('motus_token')

        # Verify token
        expected_token = current_app.config.get('MOTUS_TOKEN')
        if not token or token != expected_token:
            return jsonify({'error': 'Invalid or missing token'}), 401

        return f(*args, **kwargs)

    return decorated


def verify_token(token):
    """
    Verify if a token is valid

    Args:
        token: The token to verify

    Returns:
        bool: True if token is valid, False otherwise
    """
    if not token:
        return False

    expected_token = current_app.config.get('MOTUS_TOKEN')
    return token == expected_token


def optional_token(f):
    """
    Optional token authentication
    Sets request.authenticated = True if valid token provided
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check query parameter
        token = request.args.get('token')

        # Check Authorization header
        if not token and 'Authorization' in request.headers:
            auth = request.headers['Authorization']
            if auth.startswith('token '):
                token = auth[6:]

        # Check cookie
        if not token:
            token = request.cookies.get('motus_token')

        # Set authentication status
        expected_token = current_app.config.get('MOTUS_TOKEN')
        request.authenticated = (token == expected_token)

        return f(*args, **kwargs)

    return decorated
