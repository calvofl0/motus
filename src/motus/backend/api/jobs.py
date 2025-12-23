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

        # Check if job is actually running in rclone's queue
        running_jobs = rclone.get_running_jobs()

        if job_id in running_jobs:
            # Job is active - get live status from rclone
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

            # Get log text if job is finished
            log_text = None
            if finished:
                log_text = rclone.job_log_text(job_id)
                if log_text is None:
                    logging.warning(f"Job {job_id}: Unable to read log file for finished job")

            # Update database with live status
            db.update_job(
                job_id=job_id,
                status=status,
                progress=progress,
                error_text=error_text if error_text else None,
                log_text=log_text,
            )

            # Clean up log file after storing in database (only if we successfully read it)
            if finished and log_text is not None:
                rclone.job_cleanup_log(job_id)
                logging.debug(f"Job {job_id}: Cleaned up log file after saving to database")
        else:
            # Job not in queue - use database status as-is
            # (interrupted, cancelled, completed, failed jobs are not in the queue)
            status = job['status']

            # IMPORTANT: If DB says 'running' but job not in queue, it finished
            # so fast we never polled while it was running. Check completion now.
            if status == 'running':
                finished = rclone.job_finished(job_id)
                if finished:
                    # Job actually finished - get final status
                    exit_status = rclone.job_exitstatus(job_id)
                    progress = 100
                    error_text = rclone.job_error_text(job_id)

                    if exit_status == 0:
                        status = 'completed'
                    else:
                        status = 'failed'

                    logging.info(f"Job {job_id}: Fast job finished - updating DB to status={status}, exit={exit_status}")

                    # Get log text
                    log_text = rclone.job_log_text(job_id)
                    if log_text is None:
                        logging.warning(f"Job {job_id}: Unable to read log file for fast finished job")

                    # Update database with final status
                    db.update_job(
                        job_id=job_id,
                        status=status,
                        progress=progress,
                        error_text=error_text if error_text else None,
                        log_text=log_text,
                    )

                    # Clean up log file after storing in database (only if we successfully read it)
                    if log_text is not None:
                        rclone.job_cleanup_log(job_id)
                        logging.debug(f"Job {job_id}: Cleaned up log file after saving to database")
                else:
                    # Job says 'running' but not in queue and not finished?
                    # This shouldn't happen, but keep current status
                    logging.warning(f"Job {job_id}: DB says running, not in queue, not finished - keeping status")
                    progress = job.get('progress', 0)
                    error_text = job.get('error_text', '')
                    exit_status = -1
            else:
                # Job has terminal status in DB already
                progress = job.get('progress', 0)
                error_text = job.get('error_text', '')
                exit_status = -1

                # Recovery: If job is finished but has no log_text in DB, try to recover from file
                if status in ['completed', 'failed'] and not job.get('log_text'):
                    log_text = rclone.job_log_text(job_id)
                    if log_text is not None:
                        logging.info(f"Job {job_id}: Recovered log file for finished job, saving to database")
                        db.update_job(job_id=job_id, log_text=log_text)
                        # Clean up log file after successful recovery
                        rclone.job_cleanup_log(job_id)
                    else:
                        logging.debug(f"Job {job_id}: No log file available for recovery")

            text = ""
            finished = status in ['completed', 'failed', 'cancelled', 'interrupted']
            logging.info(f"Job {job_id}: NOT in queue - final status={status}, finished={finished}")

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
            # Log text (for failed job log viewer)
            'log_text': job.get('log_text'),
            # Download-specific fields (for download jobs)
            'download_token': job.get('download_token'),
            'zip_path': job.get('zip_path'),
            'zip_filename': job.get('zip_filename'),
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

        # Get log text before marking as cancelled
        log_text = rclone.job_log_text(job_id)

        # Update database with cancelled status and log
        db.update_job(
            job_id=job_id,
            status='cancelled',
            log_text=log_text
        )

        # Clean up log file
        rclone.job_cleanup_log(job_id)

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
    - status: Filter by status (optional, special values: 'aborted' for failed+interrupted, 'resumable' for interrupted not yet resumed)
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

        # Special handling for status filters
        if status == 'aborted':
            # Failed + interrupted (but not resumed)
            jobs = db.list_aborted_jobs(limit=limit, offset=offset)
        elif status == 'resumable':
            # Interrupted but not yet resumed (for popup)
            jobs = db.list_interrupted_resumable_jobs(limit=limit, offset=offset)
        else:
            jobs = db.list_jobs(status=status, limit=limit, offset=offset)

        # IMPORTANT: Enrich running jobs with live data from rclone
        # and update any fast-finishing jobs that show as 'running'
        # but are no longer in the queue (completed between polls)
        running_jobs = rclone.get_running_jobs()
        for job in jobs:
            if job['status'] == 'running':
                if job['job_id'] in running_jobs:
                    # Job is actively running - enrich with live data
                    job['progress'] = rclone.job_percent(job['job_id'])
                    job['text'] = rclone.job_text(job['job_id'])

                    # Update database with current progress
                    db.update_job(
                        job_id=job['job_id'],
                        progress=job['progress'],
                    )
                else:
                    # Fast job finished - check and update
                    if rclone.job_finished(job['job_id']):
                        exit_status = rclone.job_exitstatus(job['job_id'])
                        if exit_status == 0:
                            job['status'] = 'completed'
                        else:
                            job['status'] = 'failed'

                        logging.info(f"Job {job['job_id']}: Fast job detected in list_jobs - updating to {job['status']}")

                        # Get log text
                        log_text = rclone.job_log_text(job['job_id'])

                        # Update database
                        db.update_job(
                            job_id=job['job_id'],
                            status=job['status'],
                            progress=100,
                            error_text=rclone.job_error_text(job['job_id']) or None,
                            log_text=log_text,
                        )

                        # Clean up log file after storing in database (always cleanup)
                        rclone.job_cleanup_log(job['job_id'])

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


@jobs_bp.route('/api/jobs/check', methods=['POST'])
@token_required
def check_integrity():
    """
    Start an integrity check job (compare hashes)

    Request JSON: Same as /copy (src_path, dst_path, etc.)

    Response:
    {
        "job_id": 123,
        "message": "Integrity check started"
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

        logging.info(f"Starting integrity check: {src_path} vs {dst_path}")

        # Start the check job
        job_id = rclone.check(
            src_path=src_path,
            dst_path=dst_path,
            src_config=src_config,
            dst_config=dst_config,
        )

        # Record in database
        db.create_job(
            job_id=job_id,
            operation='check',
            src_path=src_path,
            dst_path=dst_path,
            src_config=src_config,
            dst_config=dst_config,
        )

        return jsonify({
            'job_id': job_id,
            'message': 'Integrity check started',
        })

    except RcloneException as e:
        logging.error(f"Check job error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in check_integrity: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/<int:job_id>/resume', methods=['POST'])
@token_required
def resume_job(job_id):
    """
    Resume a job (non-destructive copy)

    Response:
    {
        "job_id": 456,  // new job ID
        "message": "Job resumed"
    }
    """
    try:
        # Get original job
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        logging.info(f"Resuming job {job_id}")

        # Start new copy job with same parameters
        new_job_id = rclone.copy(
            src_path=job['src_path'],
            dst_path=job['dst_path'],
            src_config=job.get('src_config'),
            dst_config=job.get('dst_config'),
            copy_links=False,
        )

        # Record in database
        db.create_job(
            job_id=new_job_id,
            operation='copy',
            src_path=job['src_path'],
            dst_path=job['dst_path'],
            src_config=job.get('src_config'),
            dst_config=job.get('dst_config'),
        )

        # Mark old job as resumed
        db.mark_job_as_resumed(job_id, new_job_id)

        return jsonify({
            'job_id': new_job_id,
            'message': 'Job resumed',
        })

    except Exception as e:
        logging.error(f"Error resuming job: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/<int:job_id>/sync', methods=['POST'])
@token_required
def sync_job(job_id):
    """
    Sync a job (DESTRUCTIVE - deletes extra files at destination)

    Response:
    {
        "job_id": 456,  // new job ID
        "message": "Sync job started"
    }
    """
    try:
        # Get original job
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        logging.info(f"Syncing job {job_id}")

        # Start new sync job with same parameters
        new_job_id = rclone.sync(
            src_path=job['src_path'],
            dst_path=job['dst_path'],
            src_config=job.get('src_config'),
            dst_config=job.get('dst_config'),
        )

        # Record in database
        db.create_job(
            job_id=new_job_id,
            operation='sync',
            src_path=job['src_path'],
            dst_path=job['dst_path'],
            src_config=job.get('src_config'),
            dst_config=job.get('dst_config'),
        )

        # Mark old job as resumed
        db.mark_job_as_resumed(job_id, new_job_id)

        return jsonify({
            'job_id': new_job_id,
            'message': 'Sync job started',
        })

    except Exception as e:
        logging.error(f"Error syncing job: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/clear_stopped', methods=['POST'])
@token_required
def clear_stopped_jobs():
    """
    Delete all stopped (non-running) jobs

    Response:
    {
        "message": "Deleted N jobs",
        "count": N
    }
    """
    try:
        count, deleted_job_ids = db.delete_stopped_jobs()

        # Clean up JobQueue in-memory state for deleted jobs
        for job_id in deleted_job_ids:
            try:
                rclone.job_delete(job_id)
            except Exception as e:
                # Job might not be in queue anymore, that's OK
                logging.debug(f"Could not delete job {job_id} from queue: {e}")

        # Reinitialize job counter to max_id + 1
        rclone.initialize_job_counter(db)

        return jsonify({
            'message': f'Deleted {count} jobs',
            'count': count,
        })

    except Exception as e:
        logging.error(f"Error clearing stopped jobs: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.route('/api/jobs/<int:job_id>/log', methods=['GET'])
@token_required
def get_job_log(job_id):
    """
    Get the full rclone log for a job

    Response:
    {
        "job_id": 123,
        "log_text": "rclone log content..."
    }
    """
    try:
        # Get job from database
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        # Get log text from database (stored after job completion)
        log_text = job.get('log_text', '')

        # If log text is not in database, try to get it from rclone (for running jobs or recovery)
        if not log_text:
            log_text = rclone.job_log_text(job_id) or ''
            # If we successfully recovered the log and job is finished, save it to database
            if log_text and job['status'] in ['completed', 'failed']:
                logging.info(f"Job {job_id}: Recovered log via /log endpoint, saving to database")
                db.update_job(job_id=job_id, log_text=log_text)
                # Clean up log file after successful recovery
                rclone.job_cleanup_log(job_id)

        return jsonify({
            'job_id': job_id,
            'log_text': log_text,
        })

    except Exception as e:
        logging.error(f"Error getting job log: {e}")
        return jsonify({'error': 'Internal server error'}), 500
