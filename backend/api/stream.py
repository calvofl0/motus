"""
Server-Sent Events (SSE) for real-time job progress
"""
import json
import logging
import time
from flask import Blueprint, Response, request

from ..auth import token_required
from ..rclone.wrapper import RcloneWrapper
from ..models import Database

stream_bp = Blueprint('stream', __name__)

# Global instances (initialized by app)
rclone = None
db = None


def init_stream(rclone_instance: RcloneWrapper, db_instance: Database):
    """Initialize rclone wrapper and database"""
    global rclone, db
    rclone = rclone_instance
    db = db_instance


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

                    # Prepare event data
                    event_data = {
                        'job_id': job_id,
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
                        db.update_job(
                            job_id=job_id,
                            status='running',
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
