"""
File operations API endpoints
Handles ls, mkdir, delete operations
"""
import logging
from flask import Blueprint, request, jsonify

from ..auth import token_required
from ..rclone.wrapper import RcloneWrapper
from ..rclone.exceptions import RcloneException

files_bp = Blueprint('files', __name__)

# Global rclone wrapper instance (initialized by app)
rclone = None


def init_rclone(rclone_instance: RcloneWrapper):
    """Initialize the rclone wrapper"""
    global rclone
    rclone = rclone_instance


@files_bp.route('/api/files/ls', methods=['POST'])
@token_required
def list_files():
    """
    List files and directories

    Request JSON:
    {
        "path": "/path/to/list",
        "remote_config": {  // optional
            "type": "s3",
            "region": "us-west-2",
            "access_key_id": "...",
            "secret_access_key": "..."
        }
    }

    Response:
    {
        "files": [
            {
                "Name": "file.txt",
                "Size": 1024,
                "IsDir": false,
                "ModTime": "2024-01-01T00:00:00Z"
            },
            ...
        ],
        "path": "/path/to/list"
    }
    """
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'Missing required field: path'}), 400

        path = data['path']
        remote_config = data.get('remote_config')

        logging.info(f"Listing files at {path}")

        files = rclone.ls(path, remote_config)

        return jsonify({
            'files': files,
            'path': path,
        })

    except RcloneException as e:
        logging.error(f"List files error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in list_files: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@files_bp.route('/api/files/mkdir', methods=['POST'])
@token_required
def make_directory():
    """
    Create a directory

    Request JSON:
    {
        "path": "/path/to/create",
        "remote_config": {  // optional
            "type": "s3",
            ...
        }
    }

    Response:
    {
        "message": "Directory created successfully",
        "path": "/path/to/create"
    }
    """
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'Missing required field: path'}), 400

        path = data['path']
        remote_config = data.get('remote_config')

        logging.info(f"Creating directory {path}")

        rclone.mkdir(path, remote_config)

        return jsonify({
            'message': 'Directory created successfully',
            'path': path,
        })

    except RcloneException as e:
        logging.error(f"Make directory error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in make_directory: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@files_bp.route('/api/files/delete', methods=['POST'])
@token_required
def delete_file():
    """
    Delete a file or directory

    Request JSON:
    {
        "path": "/path/to/delete",
        "remote_config": {  // optional
            "type": "s3",
            ...
        }
    }

    Response:
    {
        "message": "Deleted successfully",
        "path": "/path/to/delete"
    }
    """
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'Missing required field: path'}), 400

        path = data['path']
        remote_config = data.get('remote_config')

        logging.info(f"Deleting {path}")

        rclone.delete(path, remote_config)

        return jsonify({
            'message': 'Deleted successfully',
            'path': path,
        })

    except RcloneException as e:
        logging.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in delete_file: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@files_bp.route('/api/files/expand-home', methods=['POST'])
@token_required
def expand_home():
    """
    Expand home directory (~) in a path to the actual home directory

    Request JSON:
    {
        "path": "~/Documents"
    }

    Response:
    {
        "expanded_path": "/home/username/Documents"
    }
    """
    import os
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'Missing required field: path'}), 400

        path = data['path']

        # Use os.path.expanduser which is cross-platform
        expanded = os.path.expanduser(path)

        logging.info(f"Expanded path: {path} -> {expanded}")

        return jsonify({
            'expanded_path': expanded
        })

    except Exception as e:
        logging.error(f"Expand home error: {e}")
        return jsonify({'error': str(e)}), 500


