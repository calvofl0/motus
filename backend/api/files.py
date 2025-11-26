"""
File operations API endpoints
Handles ls, mkdir, delete, download operations
"""
import logging
import os
import secrets
from flask import Blueprint, request, jsonify, send_file, current_app

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


def calculate_path_size(path: str, remote_config: dict = None) -> int:
    """
    Calculate total size of a file or directory

    Args:
        path: Path to file or directory (supports remote:path syntax)
        remote_config: Optional remote configuration

    Returns:
        int: Size in bytes
    """
    try:
        # Use rclone size command to get accurate size
        result = rclone.size(path, remote_config)
        return result.get('bytes', 0)
    except Exception as e:
        logging.warning(f"Could not calculate size for {path}: {e}")
        return 0


def calculate_total_size(paths: list, remote_config: dict = None) -> int:
    """
    Calculate total size of multiple paths

    Args:
        paths: List of paths (files or directories)
        remote_config: Optional remote configuration

    Returns:
        int: Total size in bytes
    """
    total = 0
    for path in paths:
        total += calculate_path_size(path, remote_config)
    return total


def is_remote_path(path: str) -> bool:
    """Check if path is a remote path (contains ':')"""
    return ':' in path and not (len(path) > 1 and path[1] == ':')  # Not Windows path like C:


def is_single_file(path: str, remote_config: dict = None) -> bool:
    """Check if path is a single file (not a directory)"""
    try:
        result = rclone.ls(path, remote_config)
        files = result.get('files', [])
        # If it's a directory, ls will return multiple items or subdirectories
        # For single file, check if parent directory listing shows it as a file
        if len(files) == 0:
            # Try to list parent directory and check if this is a file
            if is_remote_path(path):
                # Remote path: split at last /
                parts = path.rsplit('/', 1)
                if len(parts) == 2:
                    parent_path, filename = parts
                    parent_result = rclone.ls(parent_path, remote_config)
                    for item in parent_result.get('files', []):
                        if item['Name'] == filename and not item.get('IsDir', False):
                            return True
            else:
                # Local path
                return os.path.isfile(path)
        return False
    except Exception as e:
        logging.warning(f"Could not determine if {path} is file: {e}")
        # If local path, use os.path
        if not is_remote_path(path):
            return os.path.isfile(path)
        return False


@files_bp.route('/api/files/download/prepare', methods=['POST'])
@token_required
def prepare_download():
    """
    Prepare download: check if files need to be zipped

    Request JSON:
    {
        "paths": ["/path/to/file1", "remote:/path/to/folder"],
        "remote_config": {...}  // optional
    }

    Response (direct download):
    {
        "type": "direct",
        "path": "/path/to/file"
    }

    Response (needs zip):
    {
        "type": "zip_job",
        "job_id": 123,
        "estimated_size": 1048576
    }
    """
    try:
        data = request.get_json()
        if not data or 'paths' not in data:
            return jsonify({'error': 'Missing required field: paths'}), 400

        paths = data['paths']
        if not paths or not isinstance(paths, list):
            return jsonify({'error': 'paths must be a non-empty list'}), 400

        remote_config = data.get('remote_config')
        config = current_app.motus_config

        # Calculate total size
        logging.info(f"Calculating size for {len(paths)} paths...")
        total_size = calculate_total_size(paths, remote_config)
        logging.info(f"Total size: {total_size} bytes")

        # Check if we can do direct download
        # Only for single file AND size < threshold
        if (len(paths) == 1 and
            is_single_file(paths[0], remote_config) and
            total_size < config.max_uncompressed_download_size):

            logging.info(f"Direct download for {paths[0]}")
            return jsonify({
                'type': 'direct',
                'path': paths[0],
                'size': total_size
            })

        # Need to create zip job
        logging.info(f"Creating zip job for {len(paths)} paths (total size: {total_size} bytes)")
        job_id = rclone.create_download_zip_job(paths, remote_config, total_size)

        return jsonify({
            'type': 'zip_job',
            'job_id': job_id,
            'estimated_size': total_size
        })

    except Exception as e:
        logging.error(f"Prepare download error: {e}")
        return jsonify({'error': str(e)}), 500


@files_bp.route('/api/files/download/direct', methods=['POST'])
@token_required
def download_direct():
    """
    Direct download of a single file

    Request JSON:
    {
        "path": "/path/to/file",
        "remote_config": {...}  // optional
    }

    Returns: File download
    """
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'Missing required field: path'}), 400

        path = data['path']
        remote_config = data.get('remote_config')

        # If it's a remote path, we need to download to temp first
        if is_remote_path(path):
            logging.info(f"Downloading remote file to temp: {path}")
            temp_file = rclone.download_to_temp(path, remote_config)

            # Get filename from path
            filename = path.rsplit('/', 1)[-1] if '/' in path else path
            if ':' in filename:
                filename = filename.split(':', 1)[-1]

            @current_app.after_this_request
            def cleanup(response):
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logging.info(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logging.error(f"Failed to cleanup temp file: {e}")
                return response

            return send_file(
                temp_file,
                as_attachment=True,
                download_name=filename
            )
        else:
            # Local file - direct send
            logging.info(f"Direct download of local file: {path}")
            if not os.path.exists(path):
                return jsonify({'error': 'File not found'}), 404

            if not os.path.isfile(path):
                return jsonify({'error': 'Path is not a file'}), 400

            return send_file(
                path,
                as_attachment=True,
                download_name=os.path.basename(path)
            )

    except Exception as e:
        logging.error(f"Direct download error: {e}")
        return jsonify({'error': str(e)}), 500


@files_bp.route('/api/files/download/zip/<download_token>', methods=['GET'])
@token_required
def download_zip(download_token):
    """
    Download a prepared zip file

    The download_token is generated when the zip job completes

    Returns: Zip file download (and cleans up after)
    """
    try:
        db = current_app.db
        config = current_app.motus_config

        # Find job by download token
        jobs = db.list_jobs(limit=1000)  # Search recent jobs
        job = None
        for j in jobs:
            if j.get('download_token') == download_token:
                job = j
                break

        if not job:
            return jsonify({'error': 'Download not found'}), 404

        if job['status'] != 'completed':
            return jsonify({'error': 'Download not ready', 'status': job['status']}), 400

        zip_path = job.get('zip_path')
        if not zip_path or not os.path.exists(zip_path):
            return jsonify({'error': 'Download expired or not found'}), 410

        zip_filename = job.get('zip_filename', 'download.zip')

        logging.info(f"Sending zip file: {zip_path}")

        # Clean up after download
        @current_app.after_this_request
        def cleanup(response):
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                    logging.info(f"Cleaned up zip file: {zip_path}")
            except Exception as e:
                logging.error(f"Failed to cleanup zip file: {e}")
            return response

        return send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )

    except Exception as e:
        logging.error(f"Zip download error: {e}")
        return jsonify({'error': str(e)}), 500


