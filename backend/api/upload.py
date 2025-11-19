"""
File upload API endpoint for drag-and-drop from desktop
Handles uploading files to temporary cache and initiating copy jobs
"""
import logging
import os
import shutil
from pathlib import Path
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from ..auth import token_required

upload_bp = Blueprint('upload', __name__)

# Global instances (initialized by app)
rclone_wrapper = None
cache_dir = None


def init_upload(rclone, data_dir: str):
    """
    Initialize upload management

    Args:
        rclone: RcloneWrapper instance
        data_dir: Path to data directory
    """
    global rclone_wrapper, cache_dir

    rclone_wrapper = rclone
    cache_dir = Path(data_dir) / '.upload-cache'

    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Upload cache directory: {cache_dir}")


def cleanup_cache(exclude_job_ids=None):
    """
    Clean up the upload cache directory

    Args:
        exclude_job_ids: List of job IDs to exclude from cleanup (active jobs)
    """
    if not cache_dir or not cache_dir.exists():
        return

    exclude_job_ids = exclude_job_ids or []
    exclude_dirs = {f"job-{job_id}" for job_id in exclude_job_ids}

    try:
        for item in cache_dir.iterdir():
            if item.is_dir() and item.name not in exclude_dirs:
                logging.info(f"Cleaning up upload cache: {item}")
                shutil.rmtree(item, ignore_errors=True)
    except Exception as e:
        logging.warning(f"Error cleaning upload cache: {e}")


@upload_bp.route('/api/upload', methods=['POST'])
@token_required
def upload_files():
    """
    Upload files from desktop to temporary cache or directly to local filesystem

    Request:
        - multipart/form-data with files
        - form field 'destination': target path (e.g., "/path" or "remote:/path")
        - form field 'job_id': unique job ID for this upload session
        - form field 'direct_upload': 'true' for direct local upload (optional)

    Response:
        {
            "message": "Files uploaded successfully",
            "job_id": "...",
            "cache_path": "/full/path/to/cache",  # or "direct_path" for direct upload
            "files": ["file1.txt", "file2.pdf"]
        }
    """
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        destination = request.form.get('destination')
        job_id = request.form.get('job_id')
        direct_upload = request.form.get('direct_upload') == 'true'

        if not destination or not job_id:
            return jsonify({'error': 'Missing destination or job_id'}), 400

        files = request.files.getlist('files[]')
        if not files:
            return jsonify({'error': 'No files provided'}), 400

        # Direct upload to local filesystem (no cache)
        if direct_upload:
            uploaded_files = []
            dest_path = Path(destination).expanduser()  # Expand ~ to home directory
            logging.info(f"Direct upload destination: {destination} -> {dest_path}")

            # Ensure destination directory exists
            dest_path.mkdir(parents=True, exist_ok=True)

            for file in files:
                if file.filename:
                    # Secure the filename
                    filename = secure_filename(file.filename)
                    file_path = dest_path / filename

                    # Save the file directly to destination
                    file.save(str(file_path))
                    uploaded_files.append(filename)
                    logging.info(f"Uploaded file directly to local filesystem: {file_path}")

            return jsonify({
                'message': 'Files uploaded successfully',
                'job_id': job_id,
                'direct_path': str(dest_path),
                'files': uploaded_files
            })

        # Upload to cache (for remote destinations)
        # Create job-specific cache directory
        job_cache = cache_dir / f"job-{job_id}"
        job_cache.mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        for file in files:
            if file.filename:
                # Secure the filename and preserve directory structure
                filename = secure_filename(file.filename)
                file_path = job_cache / filename

                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Save the file
                file.save(str(file_path))
                uploaded_files.append(filename)
                logging.info(f"Uploaded file to cache: {filename}")

        return jsonify({
            'message': 'Files uploaded successfully',
            'job_id': job_id,
            'cache_path': str(job_cache),
            'files': uploaded_files
        })

    except Exception as e:
        logging.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/api/upload/cleanup/<job_id>', methods=['DELETE'])
@token_required
def cleanup_job_cache(job_id):
    """
    Clean up cache for a specific job

    Called after successful file transfer completion
    """
    try:
        job_cache = cache_dir / f"job-{job_id}"

        if job_cache.exists():
            shutil.rmtree(job_cache, ignore_errors=True)
            logging.info(f"Cleaned up cache for job {job_id}")
            return jsonify({'message': 'Cache cleaned successfully'})
        else:
            return jsonify({'message': 'Cache already clean'}), 404

    except Exception as e:
        logging.error(f"Cache cleanup error: {e}")
        return jsonify({'error': str(e)}), 500
