"""
Server-Sent Events (SSE) for real-time job progress and session events
"""
import json
import logging
import queue
import time
from flask import Blueprint, Response, jsonify, request

from ..auth import token_required
from ..rclone.wrapper import RcloneWrapper
from ..models import Database

stream_bp = Blueprint('stream', __name__)

# Global instances (initialized by app)
rclone = None
db = None
_registered_frontends = None  # reference to app._registered_frontends dict
_frontends_lock = None        # reference to app._frontends_lock


def init_stream(rclone_instance: RcloneWrapper, db_instance: Database, frontends: dict, frontends_lock):
    """Initialize rclone wrapper, database, and frontend event queue references"""
    global rclone, db, _registered_frontends, _frontends_lock
    rclone = rclone_instance
    db = db_instance
    _registered_frontends = frontends
    _frontends_lock = frontends_lock


@stream_bp.route('/api/stream/jobs/<int:job_id>')
@token_required
def stream_job_progress(job_id):
    """
    Stream job progress via Server-Sent Events

    Response: text/event-stream

    Event format:
    data: {"progress": 45, "text": "...", "finished": false}

    """
    def generate():
        """Generator function for SSE"""
        try:
            # Verify job exists
            job = db.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                return

            # Stream updates until job finishes
            while True:
                try:
                    # Get current status
                    finished = rclone.job_finished(job_id)
                    progress = rclone.job_percent(job_id)
                    text = rclone.job_text(job_id)
                    error_text = rclone.job_error_text(job_id)
                    exit_status = rclone.job_exitstatus(job_id)

                    # Get current job status from database
                    job = db.get_job(job_id)
                    current_status = job.get('status') if job else 'unknown'

                    # Prepare event data
                    event_data = {
                        'job_id': job_id,
                        'status': current_status,
                        'progress': progress,
                        'text': text,
                        'error_text': error_text,
                        'finished': finished,
                        'exit_status': exit_status,
                    }

                    # Send event
                    yield f"data: {json.dumps(event_data)}\n\n"

                    # Update database
                    if finished:
                        status = 'completed' if exit_status == 0 else 'failed'
                        db.update_job(
                            job_id=job_id,
                            status=status,
                            progress=progress,
                            error_text=error_text if error_text else None,
                        )
                        break
                    else:
                        # Only update status to 'running' if job is actually running
                        # Don't change status for stopped/aborted jobs
                        current_status = job.get('status')
                        if current_status in ('running', 'pending'):
                            db.update_job(
                                job_id=job_id,
                                status='running',
                                progress=progress,
                            )
                        else:
                            # Job is stopped/aborted, just update progress without changing status
                            db.update_job(
                                job_id=job_id,
                                progress=progress,
                            )

                    # Wait before next update
                    time.sleep(2)

                except Exception as e:
                    logging.error(f"Error in SSE stream: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break

        except Exception as e:
            logging.error(f"Error in SSE generator: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
        }
    )


@stream_bp.route('/api/stream/events')
@token_required
def stream_events():
    """
    Multiplexed Server-Sent Events stream for a registered frontend session.

    Delivers all server-push events over a single persistent connection,
    eliminating per-job SSE streams and avoiding browser connection-limit issues.

    Event types (JSON in the data field):
      {"type": "shutdown"}  - server is shutting down
      (future) {"type": "job_progress", "job_id": N, ...}
      (future) {"type": "listing_updated", "remote": "...", "prefix": "..."}

    Keep-alive: SSE comments (": ping") are sent every 30 s when the queue is
    idle. These are not dispatched as message events in the browser.

    Query parameters (EventSource cannot send custom headers):
      frontend_id  - the frontend_id obtained from /api/frontend/register
      token        - auth token (already checked by @token_required via query param)
    """
    frontend_id = request.args.get('frontend_id')
    if not frontend_id:
        return jsonify({'error': 'frontend_id required'}), 400

    with _frontends_lock:
        if frontend_id not in _registered_frontends:
            return jsonify({'error': 'frontend not registered'}), 404
        event_queue = _registered_frontends[frontend_id]['queue']

    def generate():
        while True:
            try:
                event = event_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get('type') == 'shutdown':
                    break
            except queue.Empty:
                # Keep-alive comment — not dispatched as a message event
                yield ": ping\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )
