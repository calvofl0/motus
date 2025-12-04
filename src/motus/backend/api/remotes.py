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
from ..rclone.custom_remote import CustomRemoteCreationManager

remotes_bp = Blueprint('remotes', __name__)

# Global instances (initialized by app)
rclone_config = None
remote_template = None
oauth_manager = None
custom_remote_manager = None


def init_remote_management(config_file: str, template_file: str = None, rclone_path: str = None,
                          readonly_config_file: str = None, cache_dir: str = None):
    """
    Initialize remote management with two-tier config support

    Args:
        config_file: Path to rclone config file (user's master config or merged config)
        template_file: Optional path to remote templates file
        rclone_path: Path to rclone executable (for OAuth operations)
        readonly_config_file: Optional path to readonly remotes config (from --extra-remotes)
        cache_dir: Cache directory for merged config file
    """
    global rclone_config, remote_template, oauth_manager, custom_remote_manager

    # Initialize RcloneConfig with two-tier support
    rclone_config = RcloneConfig(
        config_file,
        readonly_config_file=readonly_config_file,
        cache_dir=cache_dir
    )

    if template_file and os.path.exists(template_file):
        remote_template = RemoteTemplate(template_file)
        logging.info(f"Remote templates loaded from {template_file}")
    else:
        remote_template = None
        if template_file:
            logging.warning(f"Remote templates file not found: {template_file}")

    # Initialize OAuth manager and Custom Remote manager
    # IMPORTANT: Use user_config_file (not merged config) because rclone writes directly to the config
    # After rclone writes (OAuth token, new remote), the merged config is regenerated
    if rclone_path:
        # Use user config file for write operations (OAuth refresh, remote creation)
        user_config_file = rclone_config.user_config_file
        oauth_manager = OAuthRefreshManager(rclone_path, user_config_file)
        logging.info("OAuth refresh manager initialized")

        # Initialize custom remote creation manager (also uses user config for writes)
        custom_remote_manager = CustomRemoteCreationManager(rclone_path, user_config_file)
        logging.info("Custom remote creation manager initialized")


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
                'is_readonly': rclone_config.is_readonly_remote(name),
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

    except ValueError as e:
        # Raised when trying to delete a readonly remote
        logging.warning(f"Delete remote blocked: {e}")
        return jsonify({'error': str(e)}), 403
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

    except ValueError as e:
        # Raised when trying to update a readonly remote
        logging.warning(f"Update remote blocked: {e}")
        return jsonify({'error': str(e)}), 403
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
    Start OAuth token refresh for a remote using interactive flow

    This uses rclone's --non-interactive state machine. The user will need to
    run `rclone authorize` on their laptop and paste the resulting token.

    Response:
    {
        "status": "needs_token" | "error" | "complete",
        "authorize_command": "rclone authorize ...",  // if needs_token
        "session_id": "remote_name",  // if needs_token
        "message": "Status or error message"
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

        # Check if this is a readonly remote
        if rclone_config.is_readonly_remote(remote_name):
            return jsonify({
                'error': f'Cannot refresh OAuth token for readonly remote: {remote_name}. '
                         'This remote is from a readonly configuration file (--extra-remotes).'
            }), 403

        if not is_oauth_remote(config):
            return jsonify({'error': f'Remote {remote_name} is not OAuth-based (no token found)'}), 400

        # Get remote type
        remote_type = config.get('type', 'unknown')

        # Start interactive OAuth refresh
        result = oauth_manager.start_oauth_refresh_interactive(remote_name, remote_type)

        return jsonify(result)

    except Exception as e:
        logging.error(f"OAuth refresh error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/<remote_name>/oauth/submit-token', methods=['POST'])
@token_required
def submit_oauth_token(remote_name):
    """
    Submit the OAuth token from rclone authorize to continue the refresh flow

    Request JSON:
    {
        "token": "LONG_STRING_FROM_RCLONE_AUTHORIZE"
    }

    Response:
    {
        "status": "complete" | "needs_token" | "error",
        "message": "Status or error message"
    }
    """
    try:
        if not oauth_manager:
            return jsonify({'error': 'OAuth manager not initialized'}), 500

        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({'error': 'Missing required field: token'}), 400

        token = data['token']

        # Continue OAuth refresh with token
        result = oauth_manager.continue_oauth_refresh(remote_name, token)

        # If OAuth refresh completed successfully, regenerate merged config
        if result.get('status') == 'complete':
            rclone_config._regenerate_merged_config()
            logging.info(f"Regenerated merged config after OAuth refresh for '{remote_name}'")

        return jsonify(result)

    except Exception as e:
        logging.error(f"OAuth token submission error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/providers', methods=['GET'])
@token_required
def list_providers():
    """
    List available remote providers from rclone

    Response:
    {
        "providers": [
            {"name": "s3", "description": "Amazon S3"},
            {"name": "drive", "description": "Google Drive"},
            ...
        ],
        "count": 50
    }
    """
    try:
        if not custom_remote_manager:
            return jsonify({'error': 'Custom remote manager not initialized'}), 500

        providers = custom_remote_manager.get_providers()

        return jsonify({
            'providers': providers,
            'count': len(providers),
        })

    except Exception as e:
        logging.error(f"List providers error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/custom/start', methods=['POST'])
@token_required
def start_custom_remote():
    """
    Start creating a custom remote with given name and type

    Request JSON:
    {
        "name": "my_remote",
        "type": "s3"
    }

    Response:
    {
        "status": "needs_input" | "complete" | "error",
        "question": {...},  // if needs_input
        "session_id": "my_remote",  // if needs_input
        "message": "Status or error message"
    }
    """
    try:
        if not custom_remote_manager:
            return jsonify({'error': 'Custom remote manager not initialized'}), 500

        data = request.get_json()
        if not data or 'name' not in data or 'type' not in data:
            return jsonify({'error': 'Missing required fields: name and type'}), 400

        remote_name = data['name']
        remote_type = data['type']

        # Validate remote name (alphanumeric, underscore, hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', remote_name):
            return jsonify({'error': 'Invalid remote name. Use only letters, numbers, underscores, and hyphens.'}), 400

        # Start creation
        result = custom_remote_manager.start_creation(remote_name, remote_type)

        # If creation completed immediately, regenerate merged config
        if result.get('status') == 'complete':
            rclone_config._regenerate_merged_config()
            logging.info(f"Regenerated merged config after creating remote '{remote_name}'")

        return jsonify(result)

    except Exception as e:
        logging.error(f"Start custom remote error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/custom/continue', methods=['POST'])
@token_required
def continue_custom_remote():
    """
    Continue the custom remote creation flow with an answer

    Request JSON:
    {
        "session_id": "my_remote",
        "answer": "user's answer"
    }

    Response:
    {
        "status": "needs_input" | "complete" | "error",
        "question": {...},  // if needs_input
        "session_id": "my_remote",  // if needs_input
        "message": "Status or error message"
    }
    """
    try:
        if not custom_remote_manager:
            return jsonify({'error': 'Custom remote manager not initialized'}), 500

        data = request.get_json()
        if not data or 'session_id' not in data or 'answer' not in data:
            return jsonify({'error': 'Missing required fields: session_id and answer'}), 400

        session_id = data['session_id']
        answer = data['answer']

        # Continue creation
        result = custom_remote_manager.continue_creation(session_id, answer)

        # If creation completed, regenerate merged config
        if result.get('status') == 'complete':
            rclone_config._regenerate_merged_config()
            logging.info(f"Regenerated merged config after creating remote '{session_id}'")

        return jsonify(result)

    except Exception as e:
        logging.error(f"Continue custom remote error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/custom/cancel', methods=['POST'])
@token_required
def cancel_custom_remote():
    """
    Cancel an active custom remote creation session

    Request JSON:
    {
        "session_id": "my_remote"
    }

    Response:
    {
        "message": "Session cancelled"
    }
    """
    try:
        if not custom_remote_manager:
            return jsonify({'error': 'Custom remote manager not initialized'}), 500

        data = request.get_json()
        if not data or 'session_id' not in data:
            return jsonify({'error': 'Missing required field: session_id'}), 400

        session_id = data['session_id']

        # Cancel session
        custom_remote_manager.cancel_creation(session_id)

        return jsonify({
            'message': 'Session cancelled'
        })

    except Exception as e:
        logging.error(f"Cancel custom remote error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/api/remotes/resolve-alias', methods=['POST'])
@token_required
def resolve_alias():
    """
    Resolve an alias remote path to its underlying remote path

    Request:
    {
        "remote": "MyAlias3",
        "path": "/some/folder"
    }

    Response:
    {
        "resolved_path": "onedrive:/underlying/path"
    }
    """
    try:
        data = request.get_json()
        remote_name = data.get('remote')
        path = data.get('path', '')

        if not remote_name:
            return jsonify({'error': 'Missing remote parameter'}), 400

        logging.info(f"Resolving alias path: {remote_name}:{path}")

        # Reload config to get latest remotes
        rclone_config.reload()

        # Recursively resolve alias chain using RcloneConfig method
        resolved_remote, resolved_path = rclone_config.resolve_alias_chain(remote_name, path)

        # Construct resolved path
        resolved_full_path = f"{resolved_remote}:{resolved_path}"

        logging.info(f"Resolved to: {resolved_full_path}")

        return jsonify({
            'resolved_path': resolved_full_path
        })

    except ValueError as e:
        # ValueError is raised by resolve_alias_chain for validation errors
        logging.error(f"Resolve alias error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Resolve alias error: {e}")
        return jsonify({'error': str(e)}), 500


@remotes_bp.route('/', methods=['GET'])
def serve_index():
    """
    Serve the main index.html page

    Note: The old OAuth callback handling has been removed since we now use
    the interactive rclone authorize flow instead of the proxy-based flow.
    """
    from flask import current_app, send_from_directory
    return send_from_directory(current_app.static_folder, 'index.html')


