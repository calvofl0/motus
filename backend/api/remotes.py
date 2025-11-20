"""
Remote management API endpoints
Handles listing, adding, and deleting rclone remotes
"""
import logging
import os
from flask import Blueprint, request, jsonify

from ..auth import token_required
from ..rclone.rclone_config import RcloneConfig, RemoteTemplate
from ..rclone.exceptions import RcloneException
from ..rclone.oauth import OAuthRefreshManager, is_oauth_remote

remotes_bp = Blueprint('remotes', __name__)

# Global instances (initialized by app)
rclone_config = None
remote_template = None
oauth_manager = None


def init_remote_management(config_file: str, template_file: str = None, rclone_path: str = None):
    """
    Initialize remote management

    Args:
        config_file: Path to rclone config file
        template_file: Optional path to remote templates file
        rclone_path: Path to rclone executable (for OAuth operations)
    """
    global rclone_config, remote_template, oauth_manager

    rclone_config = RcloneConfig(config_file)

    if template_file and os.path.exists(template_file):
        remote_template = RemoteTemplate(template_file)
        logging.info(f"Remote templates loaded from {template_file}")
    else:
        remote_template = None
        if template_file:
            logging.warning(f"Remote templates file not found: {template_file}")

    # Initialize OAuth manager
    if rclone_path:
        oauth_manager = OAuthRefreshManager(rclone_path, config_file)
        logging.info("OAuth refresh manager initialized")


@remotes_bp.route('/api/remotes', methods=['GET'])
@token_required
def list_remotes():
    """
    List configured rclone remotes

    Response:
    {
        "remotes": [
            {
                "name": "myS3",
                "type": "s3",
                "config": {...}
            },
            ...
        ],
        "count": 2
    }
    """
    try:
        logging.info("Listing configured rclone remotes")

        # Reload config to get latest remotes
        rclone_config.reload()

        # Get all remotes with their configurations
        remote_names = rclone_config.list_remotes()
        remotes = []
        for name in remote_names:
            config = rclone_config.get_remote(name)
            remotes.append({
                'name': name,
                'type': config.get('type', 'unknown'),
                'config': config,
                'is_oauth': is_oauth_remote(config),
            })

        return jsonify({
            'remotes': remotes,
            'count': len(remotes),
        })

    except Exception as e:
        logging.error(f"List remotes error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/<remote_name>', methods=['DELETE'])
@token_required
def delete_remote(remote_name):
    """
    Delete a remote from rclone config

    Response:
    {
        "message": "Remote deleted successfully",
        "name": "myS3"
    }
    """
    try:
        logging.info(f"Deleting remote: {remote_name}")

        # Delete remote
        success = rclone_config.delete_remote(remote_name)

        if not success:
            return jsonify({'error': f'Remote not found: {remote_name}'}), 404

        return jsonify({
            'message': 'Remote deleted successfully',
            'name': remote_name,
        })

    except Exception as e:
        logging.error(f"Delete remote error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes', methods=['POST'])
@token_required
def add_remote():
    """
    Add a new remote to rclone config

    Request JSON:
    {
        "name": "my_bucket",
        "template": "mys3",  // optional
        "values": {  // field values for template
            "Access Key ID": "public",
            "Secret Access Key": "private"
        },
        "config": {  // or direct config (if no template)
            "type": "s3",
            "access_key_id": "public",
            ...
        }
    }

    Response:
    {
        "message": "Remote added successfully",
        "name": "my_bucket"
    }
    """
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'Missing required field: name'}), 400

        remote_name = data['name']
        template_name = data.get('template')
        values = data.get('values', {})
        config = data.get('config', {})

        logging.info(f"Adding remote: {remote_name}")

        # Validate remote name (alphanumeric, underscore, hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', remote_name):
            return jsonify({'error': 'Invalid remote name. Use only letters, numbers, underscores, and hyphens.'}), 400

        # Render template if provided
        if template_name:
            if not remote_template:
                return jsonify({'error': 'Remote templates not configured'}), 400

            try:
                config = remote_template.render_template(template_name, values)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
        elif not config:
            return jsonify({'error': 'Either template or config must be provided'}), 400

        # Validate config has type
        if 'type' not in config:
            return jsonify({'error': 'Remote config must have type field'}), 400

        # Add remote to config
        rclone_config.add_remote(remote_name, config)

        return jsonify({
            'message': 'Remote added successfully',
            'name': remote_name,
        })

    except Exception as e:
        logging.error(f"Add remote error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/<remote_name>/raw', methods=['GET'])
@token_required
def get_remote_raw(remote_name):
    """
    Get raw configuration text for a remote, including comments

    Response:
    {
        "name": "myS3",
        "raw_config": "# My S3 remote\\n[myS3]\\ntype = s3\\n..."
    }
    """
    try:
        logging.info(f"Getting raw config for remote: {remote_name}")

        # Get raw config text
        raw_config = rclone_config.get_remote_raw(remote_name)

        if raw_config is None:
            return jsonify({'error': f'Remote not found: {remote_name}'}), 404

        return jsonify({
            'name': remote_name,
            'raw_config': raw_config,
        })

    except Exception as e:
        logging.error(f"Get remote raw error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/<remote_name>/raw', methods=['PUT'])
@token_required
def update_remote_raw(remote_name):
    """
    Update a remote's configuration in-place with raw config text

    Request JSON:
    {
        "raw_config": "# Comment\\n[newname]\\ntype = s3\\n..."
    }

    Response:
    {
        "message": "Remote updated successfully",
        "old_name": "myS3",
        "new_name": "myS3renamed"
    }
    """
    try:
        data = request.get_json()
        if not data or 'raw_config' not in data:
            return jsonify({'error': 'Missing required field: raw_config'}), 400

        raw_config = data['raw_config']

        logging.info(f"Updating remote raw config: {remote_name}")

        # Update remote in-place
        success, new_name = rclone_config.update_remote_raw(remote_name, raw_config)

        if not success:
            return jsonify({'error': f'Failed to update remote: {remote_name}'}), 400

        return jsonify({
            'message': 'Remote updated successfully',
            'old_name': remote_name,
            'new_name': new_name,
        })

    except Exception as e:
        logging.error(f"Update remote raw error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/raw', methods=['POST'])
@token_required
def create_remote_raw():
    """
    Create a new remote from raw configuration text

    Request JSON:
    {
        "raw_config": "[myremote]\\ntype = s3\\n..."
    }

    Response:
    {
        "message": "Remote created successfully",
        "name": "myremote"
    }
    """
    try:
        data = request.get_json()
        if not data or 'raw_config' not in data:
            return jsonify({'error': 'Missing required field: raw_config'}), 400

        raw_config = data['raw_config']

        logging.info("Creating new remote from raw config")

        # Create remote from raw config
        success, remote_name = rclone_config.add_remote_raw(raw_config)

        if not success:
            if remote_name is None:
                return jsonify({'error': 'Invalid configuration or remote already exists'}), 400
            return jsonify({'error': f'Failed to create remote'}), 400

        return jsonify({
            'message': 'Remote created successfully',
            'name': remote_name,
        })

    except Exception as e:
        logging.error(f"Create remote raw error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/templates', methods=['GET'])
@token_required
def list_templates():
    """
    List available remote templates

    Response:
    {
        "templates": [
            {
                "name": "mys3",
                "fields": [
                    {"key": "access_key_id", "label": "Access Key ID"},
                    {"key": "secret_access_key", "label": "Secret Access Key"}
                ]
            },
            ...
        ],
        "count": 2,
        "available": true
    }
    """
    try:
        logging.info("Listing remote templates")

        if not remote_template:
            return jsonify({
                'templates': [],
                'count': 0,
                'available': False,
            })

        # Get all templates with their fields
        template_names = remote_template.list_templates()
        templates = []
        for name in template_names:
            template = remote_template.get_template(name)
            templates.append({
                'name': name,
                'fields': template['fields'],
            })

        return jsonify({
            'templates': templates,
            'count': len(templates),
            'available': True,
        })

    except Exception as e:
        logging.error(f"List templates error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/<remote_name>/oauth/refresh', methods=['POST'])
@token_required
def refresh_oauth_token(remote_name):
    """
    Start OAuth token refresh for a remote

    Response:
    {
        "message": "OAuth refresh started",
        "auth_url": "https://motus-server/api/oauth/callback/my_remote/auth?state=..."
    }
    """
    try:
        if not oauth_manager:
            return jsonify({'error': 'OAuth manager not initialized'}), 500

        # Check if remote exists and is OAuth-based
        rclone_config.reload()
        config = rclone_config.get_remote(remote_name)

        if not config:
            return jsonify({'error': f'Remote not found: {remote_name}'}), 404

        if not is_oauth_remote(config):
            return jsonify({'error': f'Remote {remote_name} is not OAuth-based (no token found)'}), 400

        # Get the base URL for callback
        # Use the request's host and scheme to construct the callback URL
        base_url = f"{request.scheme}://{request.host}"
        callback_url = f"{base_url}/api/oauth/callback"

        # Start OAuth refresh
        success, message, auth_url = oauth_manager.start_oauth_refresh(remote_name, callback_url)

        if not success:
            return jsonify({'error': message}), 500

        return jsonify({
            'message': message,
            'auth_url': auth_url,
        })

    except Exception as e:
        logging.error(f"OAuth refresh error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/', methods=['GET'])
def oauth_root_callback():
    """
    Handle OAuth callback at root path (/) with remote name in query parameter

    This is used when Azure requires redirect_uri to be http://localhost:PORT/
    without any path component. The remote name is passed as _motus_remote parameter.
    """
    remote_name = request.args.get('_motus_remote')
    if not remote_name:
        return "Missing remote parameter", 400

    # Remove _motus_remote from query string and pass to regular callback handler
    args_dict = request.args.to_dict()
    args_dict.pop('_motus_remote', None)

    # Reconstruct query string without _motus_remote
    from urllib.parse import urlencode
    query_string = urlencode(args_dict)

    callback_path = '/'
    if query_string:
        callback_path += f"?{query_string}"

    return oauth_callback_handler(remote_name, callback_path)


@remotes_bp.route('/api/oauth/callback/<remote_name>/<path:callback_path>', methods=['GET'])
def oauth_callback(remote_name, callback_path):
    """Handle OAuth callback with remote name in path"""
    # Get query parameters
    query_string = request.query_string.decode('utf-8')
    full_callback_path = f"/{callback_path}"
    if query_string:
        full_callback_path += f"?{query_string}"

    return oauth_callback_handler(remote_name, full_callback_path)


def oauth_callback_handler(remote_name, callback_path):
    """
    Handle OAuth callback from provider (proxied to local rclone server)

    This endpoint receives the OAuth callback and forwards it to the local
    rclone server that's waiting for the token. It also rewrites redirect_uri
    parameters in OAuth redirects to ensure the provider redirects back to
    this server instead of localhost.
    """
    try:
        if not oauth_manager:
            return jsonify({'error': 'OAuth manager not initialized'}), 500

        # Get query parameters
        query_string = request.query_string.decode('utf-8')
        full_callback_path = f"/{callback_path}"
        if query_string:
            full_callback_path += f"?{query_string}"

        logging.info(f"OAuth callback for {remote_name}: {full_callback_path}")

        # Construct the callback base URL
        # This is the URL that OAuth providers should redirect back to
        # e.g., http://motus-server:8889/api/oauth/callback
        callback_base_url = f"{request.scheme}://{request.host}/api/oauth/callback"

        # Proxy the callback to local rclone server
        result = oauth_manager.proxy_callback(remote_name, full_callback_path, callback_base_url)

        # Check if this is a redirect or a direct response
        if result.get('type') == 'redirect':
            # Return an HTML page with JavaScript redirect instead of server-side redirect
            # This ensures the redirect happens in the tab we opened with window.open()
            # keeping everything in the same browser
            redirect_url = result.get('url')
            logging.info(f"Redirecting browser to OAuth provider: {redirect_url}")

            # Escape the URL for safe inclusion in JavaScript
            import json
            safe_redirect_url = json.dumps(redirect_url)

            return f"""
            <html>
            <head>
                <title>Redirecting to OAuth Provider</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .message {{ color: #666; font-size: 18px; margin: 20px; }}
                    .spinner {{
                        font-size: 48px;
                        color: #28a745;
                        margin: 20px;
                        display: inline-block;
                        animation: spin 2s linear infinite;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
                <script>
                    // Redirect to OAuth provider in the same tab/browser
                    window.location.href = {safe_redirect_url};
                </script>
            </head>
            <body>
                <div class="spinner">↻</div>
                <div class="message">Redirecting to authentication provider...</div>
                <div class="message" style="font-size: 14px;">If you are not redirected automatically,
                    <a href="{redirect_url}">click here</a>.</div>
            </body>
            </html>
            """, 200

        # Otherwise it's a direct response
        status_code = result.get('status', 500)
        message = result.get('message', 'Unknown error')

        if status_code == 200:
            # Success - show success message
            return f"""
            <html>
            <head>
                <title>OAuth Success</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .success {{ color: green; font-size: 24px; margin: 20px; }}
                    .message {{ color: #666; margin: 20px; }}
                </style>
            </head>
            <body>
                <div class="success">✓ OAuth Token Refreshed Successfully</div>
                <div class="message">{message}</div>
                <div class="message">You can close this window and return to Motus.</div>
            </body>
            </html>
            """, 200
        else:
            return f"""
            <html>
            <head>
                <title>OAuth Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .error {{ color: red; font-size: 24px; margin: 20px; }}
                    .message {{ color: #666; margin: 20px; }}
                </style>
            </head>
            <body>
                <div class="error">✗ OAuth Token Refresh Failed</div>
                <div class="message">{message}</div>
                <div class="message">Please try again or check the server logs.</div>
            </body>
            </html>
            """, status_code

    except Exception as e:
        logging.error(f"OAuth callback error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/oauth/cancel/<remote_name>', methods=['POST'])
@token_required
def cancel_oauth_refresh(remote_name):
    """
    Cancel an ongoing OAuth refresh session

    Response:
    {
        "message": "OAuth refresh cancelled"
    }
    """
    try:
        if not oauth_manager:
            return jsonify({'error': 'OAuth manager not initialized'}), 500

        # Cleanup the OAuth session (kills the process)
        oauth_manager.cleanup_session(remote_name)

        return jsonify({
            'message': 'OAuth refresh cancelled',
        })

    except Exception as e:
        logging.error(f"OAuth cancel error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/oauth/status/<remote_name>', methods=['GET'])
@token_required
def get_oauth_status(remote_name):
    """
    Get the status of an OAuth refresh session

    Response:
    {
        "status": "pending" | "completed" | "failed" | "not_found",
        "message": "...",
        "return_code": 0  // only if completed or failed
    }
    """
    try:
        if not oauth_manager:
            return jsonify({'error': 'OAuth manager not initialized'}), 500

        session = oauth_manager.get_session_status(remote_name)

        if not session:
            return jsonify({
                'status': 'not_found',
                'message': 'No active OAuth session for this remote',
            })

        status = session.get('status', 'pending')
        response = {
            'status': status,
            'message': f'OAuth refresh {status}',
        }

        if 'return_code' in session:
            response['return_code'] = session['return_code']

        if status == 'failed' and 'stderr' in session:
            response['error'] = session['stderr']

        return jsonify(response)

    except Exception as e:
        logging.error(f"OAuth status error: {e}")
        return jsonify({'error': str(e)}), 500
