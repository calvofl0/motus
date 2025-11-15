"""
Job management API endpoints
Handles copy, move, and job status operations
"""
import logging
from flask import Blueprint, request, jsonify

from ..auth import token_required
from ..rclone.wrapper import RcloneWrapper
from ..rclone.exceptions import RcloneException
from ..models import Database

jobs_bp = Blueprint('jobs', __name__)

# Global instances (initialized by app)
rclone = None
db = None


def init_jobs(rclone_instance: RcloneWrapper, db_instance: Database):
    """Initialize rclone wrapper and database"""
    global rclone, db
    rclone = rclone_instance
    db = db_instance


@jobs_bp.route('/api/jobs/copy', methods=['POST'])
@token_required
def copy_files():
    """
    Start a copy job

    Request JSON:
    {
        "src_path": "/source/path",
        "dst_path": "/destination/path",
        "src_config": {  // optional, for remote source
            "type": "s3",
            ...
        },
        "dst_config": {  // optional, for remote destination
            "type": "s3",
            ...
        },
        "copy_links": false  // optional, follow symlinks
    }

    Response:
    {
        "job_id": 123,
        "message": "Copy job started"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        # Validate required fields
        if 'src_path' not in data or 'dst_path' not in data:
            return jsonify({'error': 'Missing required fields: src_path, dst_path'}), 400

        src_path = data['src_path']
        dst_path = data['dst_path']
        src_config = data.get('src_config')
        dst_config = data.get('dst_config')
        copy_links = data.get('copy_links', False)

        logging.info(f"Starting copy job: {src_path} -> {dst_path}")

        # Start the copy job
        job_id = rclone.copy(
            src_path=src_path,
            dst_path=dst_path,
            src_config=src_config,
            dst_config=dst_config,
            copy_links=copy_links,
        )

        # Record in database
        db.create_job(
            job_id=job_id,
            operation='copy',
            src_path=src_path,
            dst_path=dst_path,
            src_config=src_config,
            dst_config=dst_config,
        )

        return jsonify({
            'job_id': job_id,
            'message': 'Copy job started',
        })

    except RcloneException as e:
        logging.error(f"Copy job error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in copy_files: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/move', methods=['POST'])
@token_required
def move_files():
    """
    Start a move job

    Request JSON: Same as /copy

    Response:
    {
        "job_id": 123,
        "message": "Move job started"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        # Validate required fields
        if 'src_path' not in data or 'dst_path' not in data:
            return jsonify({'error': 'Missing required fields: src_path, dst_path'}), 400

        src_path = data['src_path']
        dst_path = data['dst_path']
        src_config = data.get('src_config')
        dst_config = data.get('dst_config')
        copy_links = data.get('copy_links', False)

        logging.info(f"Starting move job: {src_path} -> {dst_path}")

        # Start the move job
        job_id = rclone.move(
            src_path=src_path,
            dst_path=dst_path,
            src_config=src_config,
            dst_config=dst_config,
            copy_links=copy_links,
        )

        # Record in database
        db.create_job(
            job_id=job_id,
            operation='move',
            src_path=src_path,
            dst_path=dst_path,
            src_config=src_config,
            dst_config=dst_config,
        )

        return jsonify({
            'job_id': job_id,
            'message': 'Move job started',
        })

    except RcloneException as e:
        logging.error(f"Move job error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in move_files: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/<int:job_id>', methods=['GET'])
@token_required
def get_job_status(job_id):
    """
    Get job status

    Response:
    {
        "job_id": 123,
        "operation": "copy",
        "src_path": "/source",
        "dst_path": "/destination",
        "status": "running",
        "progress": 45,
        "text": "Status text from rclone...",
        "error_text": "Error messages if any...",
        "finished": false,
        "exit_status": -1
    }
    """
    try:
        # Get job from database
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        # Get live status from rclone
        finished = rclone.job_finished(job_id)
        progress = rclone.job_percent(job_id)
        text = rclone.job_text(job_id)
        error_text = rclone.job_error_text(job_id)
        exit_status = rclone.job_exitstatus(job_id)

        # Determine status
        if finished:
            if exit_status == 0:
                status = 'completed'
            else:
                status = 'failed'
        else:
            status = 'running'

        # Update database
        db.update_job(
            job_id=job_id,
            status=status,
            progress=progress,
            error_text=error_text if error_text else None,
        )

        return jsonify({
            'job_id': job_id,
            'operation': job['operation'],
            'src_path': job['src_path'],
            'dst_path': job['dst_path'],
            'status': status,
            'progress': progress,
            'text': text,
            'error_text': error_text,
            'finished': finished,
            'exit_status': exit_status,
            'created_at': job['created_at'],
            'updated_at': job['updated_at'],
        })

    except Exception as e:
        logging.error(f"Error getting job status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/<int:job_id>/stop', methods=['POST'])
@token_required
def stop_job(job_id):
    """
    Stop a running job

    Response:
    {
        "message": "Job stopped",
        "job_id": 123
    }
    """
    try:
        # Check if job exists
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        logging.info(f"Stopping job {job_id}")

        # Stop the job
        rclone.job_stop(job_id)

        # Update database
        db.update_job(job_id=job_id, status='cancelled')

        return jsonify({
            'message': 'Job stopped',
            'job_id': job_id,
        })

    except Exception as e:
        logging.error(f"Error stopping job: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs', methods=['GET'])
@token_required
def list_jobs():
    """
    List all jobs

    Query parameters:
    - status: Filter by status (optional)
    - limit: Max number of results (default: 100)
    - offset: Offset for pagination (default: 0)

    Response:
    {
        "jobs": [
            {
                "job_id": 123,
                "operation": "copy",
                "status": "completed",
                ...
            },
            ...
        ]
    }
    """
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        jobs = db.list_jobs(status=status, limit=limit, offset=offset)

        return jsonify({'jobs': jobs})

    except Exception as e:
        logging.error(f"Error listing jobs: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/<int:job_id>', methods=['DELETE'])
@token_required
def delete_job(job_id):
    """
    Delete a job record

    Response:
    {
        "message": "Job deleted",
        "job_id": 123
    }
    """
    try:
        # Check if job exists
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        # Delete from rclone queue if still tracked
        try:
            rclone.job_delete(job_id)
        except:
            pass  # May not be in queue anymore

        # Delete from database
        db.delete_job(job_id)

        return jsonify({
            'message': 'Job deleted',
            'job_id': job_id,
        })

    except Exception as e:
        logging.error(f"Error deleting job: {e}")
        return jsonify({'error': 'Internal server error'}), 500
