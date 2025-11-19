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

remotes_bp = Blueprint('remotes', __name__)

# Global instances (initialized by app)
rclone_config = None
remote_template = None


def init_remote_management(config_file: str, template_file: str = None):
    """
    Initialize remote management

    Args:
        config_file: Path to rclone config file
        template_file: Optional path to remote templates file
    """
    global rclone_config, remote_template

    rclone_config = RcloneConfig(config_file)

    if template_file and os.path.exists(template_file):
        remote_template = RemoteTemplate(template_file)
        logging.info(f"Remote templates loaded from {template_file}")
    else:
        remote_template = None
        if template_file:
            logging.warning(f"Remote templates file not found: {template_file}")


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
