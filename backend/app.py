"""
Main Flask application for Motus
Single-user rclone GUI with token authentication
"""
import json
import logging
import os
import signal
import sys
import time
import threading
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS

from .config import Config
from .models import Database
from .rclone.wrapper import RcloneWrapper
from .rclone.exceptions import RcloneNotFoundError
from .auth import token_required

# Import API blueprints
from .api.files import files_bp, init_rclone as init_files_rclone
from .api.jobs import jobs_bp, init_jobs
from .api.stream import stream_bp, init_stream
from .api.remotes import remotes_bp, init_remote_management
from .api.upload import upload_bp, init_upload, cleanup_cache


# Global variables for idle timer
_last_activity_time = None
_idle_timer_thread = None
_idle_timer_stop_event = None


def cancel_two_phase_downloads(rclone: RcloneWrapper, db: Database, job_ids, status='cancelled'):
    """
    Cancel zip jobs and their associated copy jobs

    Two-phase downloads create:
    - Zip job: visible to user
    - Copy job: internal, targets cache/temp/download_temp_* path

    Args:
        rclone: RcloneWrapper instance
        db: Database instance
        job_ids: List of job IDs to process (from rclone.get_running_jobs())
        status: Status to set ('cancelled' or 'interrupted')
    """
    cancelled_jobs = set()

    # Fetch all job details for the provided job_ids
    jobs = {}
    for job_id in job_ids:
        job = db.get_job(job_id)
        if job:
            jobs[job_id] = job

    # Identify zip jobs and their associated copy jobs
    for job_id, job in jobs.items():
        try:
            # If it's a zip job, find and cancel associated copy job
            if job['operation'] == 'zip':
                # Find copy jobs in the same job_ids list with destination in cache/temp/
                for other_id, other_job in jobs.items():
                    if (other_job['operation'] == 'copy' and
                        other_job['dst_path'] and
                        '/cache/download/temp/download_temp_' in other_job['dst_path']):

                        # Get log text
                        log_text = rclone.job_log_text(other_id)

                        # Cancel the copy job
                        db.update_job(
                            job_id=other_id,
                            status=status,
                            error_text=f'Associated with {status} zip job {job_id}',
                            log_text=log_text
                        )
                        rclone.job_cleanup_log(other_id)
                        cancelled_jobs.add(other_id)
                        logging.info(f"Cancelled copy job {other_id} associated with zip job {job_id}")

                # Get log text for zip job
                log_text = rclone.job_log_text(job_id)

                # Cancel the zip job
                db.update_job(
                    job_id=job_id,
                    status=status,
                    error_text='Two-phase download cancelled',
                    log_text=log_text
                )
                rclone.job_cleanup_log(job_id)
                cancelled_jobs.add(job_id)
                logging.info(f"Cancelled zip job {job_id}")

        except Exception as e:
            logging.error(f"Error cancelling two-phase download for job {job_id}: {e}")

    return cancelled_jobs


def perform_shutdown(rclone: RcloneWrapper, db: Database, config: Config):
    """
    Perform graceful shutdown - stop jobs and cleanup

    This is extracted to be reusable from both signal handlers and API endpoint
    """
    # Get running jobs before stopping
    running_jobs = rclone.get_running_jobs()

    if running_jobs:
        logging.info(f"Stopping {len(running_jobs)} running jobs...")
        # Stop all running jobs
        rclone.shutdown()

        # Mark zip jobs and their associated copy jobs as interrupted
        handled_jobs = cancel_two_phase_downloads(rclone, db, running_jobs, 'interrupted')

        # Mark remaining jobs (not part of two-phase downloads) as interrupted
        for job_id in running_jobs:
            # Skip if already handled by cancel_two_phase_downloads
            if job_id in handled_jobs:
                continue

            try:
                # Get log text before marking as interrupted
                log_text = rclone.job_log_text(job_id)

                # Update database with interrupted status and log
                db.update_job(
                    job_id=job_id,
                    status='interrupted',
                    error_text='Job interrupted by server shutdown',
                    log_text=log_text
                )

                # Clean up log file
                rclone.job_cleanup_log(job_id)
            except Exception as e:
                logging.error(f"Error marking job {job_id} as interrupted: {e}")

    # Clean up connection info files
    cleanup_connection_info(config)

    # Clean up download cache - remove ALL zips on shutdown
    cleanup_download_cache(config, clean_all=True)

    logging.info("Shutdown complete")
    return len(running_jobs)


def cleanup_connection_info(config: Config):
    """Remove PID and connection info files"""
    data_dir = Path(config.data_dir)
    pid_file = data_dir / 'motus.pid'
    connection_file = data_dir / 'connection.json'
    dev_port_file = data_dir / 'dev-port.json'

    try:
        if pid_file.exists():
            pid_file.unlink()
            logging.debug(f"Removed PID file: {pid_file}")
    except Exception as e:
        logging.warning(f"Could not remove PID file: {e}")

    try:
        if connection_file.exists():
            connection_file.unlink()
            logging.debug(f"Removed connection file: {connection_file}")
    except Exception as e:
        logging.warning(f"Could not remove connection file: {e}")

    try:
        if dev_port_file.exists():
            dev_port_file.unlink()
            logging.debug(f"Removed dev port file: {dev_port_file}")
    except Exception as e:
        logging.warning(f"Could not remove dev port file: {e}")


def setup_signal_handlers(rclone: RcloneWrapper, db: Database, config: Config):
    """Setup signal handlers for graceful shutdown"""
    def shutdown_handler(signum, frame):
        """Handle SIGTERM/SIGINT for graceful shutdown"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logging.info(f"\n{sig_name} received, shutting down gracefully...")

        # Stop idle timer if running
        stop_idle_timer()

        perform_shutdown(rclone, db, config)
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    logging.info("Signal handlers registered for graceful shutdown")


def update_activity():
    """Update the last activity timestamp"""
    global _last_activity_time
    _last_activity_time = time.time()


def idle_timer_worker(max_idle_time: int, rclone: RcloneWrapper, db: Database, config: Config):
    """Background worker to monitor idle time and shutdown if exceeded"""
    global _idle_timer_stop_event, _last_activity_time

    logging.info(f"Idle timer started - will shutdown after {max_idle_time} seconds of inactivity")

    while not _idle_timer_stop_event.is_set():
        time.sleep(10)  # Check every 10 seconds

        if _last_activity_time is None:
            continue  # No activity yet, skip

        # Check if there are any running jobs
        running_jobs = rclone.get_running_jobs()
        if running_jobs:
            # There are active jobs, reset activity time
            update_activity()
            continue

        # Calculate idle time
        idle_time = time.time() - _last_activity_time

        if idle_time >= max_idle_time:
            logging.info(f"Idle timeout reached ({idle_time:.1f}s >= {max_idle_time}s) - shutting down")
            # Shutdown in separate thread to avoid blocking
            def shutdown_delayed():
                perform_shutdown(rclone, db, config)
                os._exit(0)

            threading.Thread(target=shutdown_delayed, daemon=True).start()
            break


def start_idle_timer(max_idle_time: int, rclone: RcloneWrapper, db: Database, config: Config):
    """Start the idle timer background thread"""
    global _idle_timer_thread, _idle_timer_stop_event, _last_activity_time

    if max_idle_time <= 0:
        return  # Idle timer disabled

    _idle_timer_stop_event = threading.Event()
    _last_activity_time = time.time()  # Initialize with current time

    _idle_timer_thread = threading.Thread(
        target=idle_timer_worker,
        args=(max_idle_time, rclone, db, config),
        daemon=True
    )
    _idle_timer_thread.start()


def stop_idle_timer():
    """Stop the idle timer background thread"""
    global _idle_timer_stop_event

    if _idle_timer_stop_event:
        _idle_timer_stop_event.set()


def cleanup_orphaned_two_phase_downloads(db: Database, config: Config):
    """
    Cancel orphaned two-phase downloads from previous crash/shutdown

    Two-phase downloads that were interrupted leave:
    - Zip jobs in 'running' or 'interrupted' status
    - Copy jobs targeting cache/temp/download_temp_* paths

    This function marks them as 'cancelled' since they can't be resumed.
    """
    try:
        # Get all interrupted and running jobs
        interrupted_jobs = db.list_jobs(status='interrupted', limit=1000)
        running_jobs = db.list_jobs(status='running', limit=1000)
        all_jobs = interrupted_jobs + running_jobs

        cancelled_count = 0

        for job in all_jobs:
            # Cancel zip jobs
            if job['operation'] == 'zip':
                db.update_job(
                    job_id=job['job_id'],
                    status='cancelled',
                    error_text='Two-phase download cancelled (cannot resume after restart)'
                )
                cancelled_count += 1
                logging.info(f"Cancelled orphaned zip job {job['job_id']}")

            # Cancel copy jobs targeting temp directory (internal download jobs)
            elif (job['operation'] == 'copy' and
                  job['dst_path'] and
                  '/cache/download/temp/download_temp_' in job['dst_path']):
                db.update_job(
                    job_id=job['job_id'],
                    status='cancelled',
                    error_text='Internal download job cancelled (cannot resume after restart)'
                )
                cancelled_count += 1
                logging.info(f"Cancelled orphaned copy job {job['job_id']}")

        if cancelled_count > 0:
            logging.warning(f"Cancelled {cancelled_count} orphaned two-phase download jobs")

    except Exception as e:
        logging.error(f"Error cleaning up orphaned two-phase downloads: {e}")


def cleanup_orphaned_logs(logs_dir: str, db, rclone):
    """
    Clean up orphaned log files from previous runs

    - For interrupted/running jobs: save logs to database
    - For other orphaned logs: delete them
    """
    if not os.path.exists(logs_dir):
        return

    try:
        log_files = [f for f in os.listdir(logs_dir) if f.startswith('job_') and f.endswith('.log')]

        if not log_files:
            return

        logging.info(f"Found {len(log_files)} orphaned log files, cleaning up...")

        # Get all interrupted jobs (these are the ones we care about saving logs for)
        interrupted_jobs = db.list_jobs(status='interrupted')
        interrupted_job_ids = {job['job_id'] for job in interrupted_jobs}

        cleaned = 0
        saved = 0

        for log_file in log_files:
            # Extract job_id from filename: job_123.log -> 123
            try:
                job_id = int(log_file.replace('job_', '').replace('.log', ''))
            except ValueError:
                logging.warning(f"Invalid log filename format: {log_file}")
                continue

            log_path = os.path.join(logs_dir, log_file)

            # If this is an interrupted job, save the log to database
            if job_id in interrupted_job_ids:
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                        log_text = f.read()

                    db.update_job(job_id=job_id, log_text=log_text)
                    logging.info(f"Saved log for interrupted job {job_id} to database")
                    saved += 1
                except Exception as e:
                    logging.warning(f"Failed to save log for job {job_id}: {e}")

            # Delete the log file (whether we saved it or not)
            try:
                os.remove(log_path)
                cleaned += 1
            except Exception as e:
                logging.warning(f"Failed to delete orphaned log file {log_file}: {e}")

        if cleaned > 0 or saved > 0:
            logging.info(f"Cleaned up {cleaned} log files ({saved} saved to database)")

    except Exception as e:
        logging.error(f"Error during log cleanup: {e}")


def cleanup_download_cache(config: Config, clean_all: bool = False):
    """
    Clean up zip files from download cache

    Args:
        config: Configuration object
        clean_all: If True, remove all zips (used on shutdown).
                   If False, only remove zips older than max_age (used on startup).

    - Called at startup (clean_all=False) and shutdown (clean_all=True)
    """
    cache_dir = config.download_cache_dir
    if not os.path.exists(cache_dir):
        return

    try:
        zip_files = [f for f in os.listdir(cache_dir) if f.endswith('.zip')]

        if not zip_files:
            return

        now = time.time()
        max_age = config.download_cache_max_age
        cleaned = 0

        for zip_file in zip_files:
            zip_path = os.path.join(cache_dir, zip_file)
            try:
                if clean_all:
                    # On shutdown: remove all ZIPs
                    os.remove(zip_path)
                    cleaned += 1
                    logging.info(f"Cleaned up zip file on shutdown: {zip_file}")
                else:
                    # On startup: only remove expired ZIPs
                    file_age = now - os.path.getmtime(zip_path)
                    if file_age > max_age:
                        os.remove(zip_path)
                        cleaned += 1
                        logging.info(f"Cleaned up expired zip file: {zip_file} (age: {int(file_age)}s)")
            except Exception as e:
                logging.warning(f"Failed to clean up zip file {zip_file}: {e}")

        if cleaned > 0:
            action = "all" if clean_all else "expired"
            logging.info(f"Cleaned up {cleaned} {action} zip files from download cache")

    except Exception as e:
        logging.error(f"Error during download cache cleanup: {e}")


def create_app(config: Config = None):
    """
    Create and configure Flask application

    Args:
        config: Config object (if None, creates default)

    Returns:
        Configured Flask app
    """
    if config is None:
        config = Config()

    # Configure logging
    setup_logging(config)

    logging.info("Creating Flask application...")
    logging.info(f"Configuration: {config}")

    # Clean up stale connection files from previous crashes
    cleanup_connection_info(config)

    app = Flask(
        __name__,
        static_folder='../frontend-dist',
        static_url_path='',
    )

    # Flask config
    app.config['SECRET_KEY'] = config.secret_key
    app.config['MOTUS_TOKEN'] = config.token
    # Set max upload size (None = unlimited)
    app.config['MAX_CONTENT_LENGTH'] = config.max_upload_size if config.max_upload_size > 0 else None

    # Enable CORS if configured (for development)
    if config.allow_cors:
        CORS(app)
        logging.warning("CORS enabled - development mode")

    # Initialize database
    logging.info(f"Initializing database at {config.database_path}")
    db = Database(config.database_path)

    # Initialize rclone wrapper
    try:
        logging.info("Initializing rclone wrapper...")
        # Store temporary job logs in cache directory (cleaned up after storing in DB)
        logs_dir = config.log_cache_dir
        rclone = RcloneWrapper(config.rclone_path, config.rclone_config_file, logs_dir)
        # Initialize job counter from database to avoid ID conflicts
        rclone.initialize_job_counter(db)
        logging.info("rclone initialized successfully")
    except RcloneNotFoundError as e:
        logging.error(f"rclone initialization failed: {e}")
        raise

    # Mark any orphaned running jobs as interrupted (from previous crash/shutdown)
    orphaned_count = db.mark_running_as_interrupted()
    if orphaned_count > 0:
        logging.warning(f"Marked {orphaned_count} orphaned jobs as interrupted")

    # Cancel orphaned two-phase downloads (zip + copy jobs left from crash)
    cleanup_orphaned_two_phase_downloads(db, config)

    # Cleanup orphaned log files from previous runs
    cleanup_orphaned_logs(logs_dir, db, rclone)

    # Clean up old download cache files
    cleanup_download_cache(config)

    # Initialize API modules with dependencies
    init_files_rclone(rclone)
    init_jobs(rclone, db)
    init_stream(rclone, db)
    # Use rclone's discovered config file path (not the config's, which may be None)
    init_remote_management(rclone.rclone_config_file, config.remote_templates_file, rclone.rclone_path)
    init_upload(rclone, config.upload_cache_dir, config.max_upload_size)

    # Merge additional remotes if configured
    if config.add_remotes_file:
        try:
            logging.info(f"Merging remotes from {config.add_remotes_file}")
            added_count = rclone.rclone_config.merge_remotes_from_file(config.add_remotes_file)
            if added_count > 0:
                logging.info(f"Successfully added {added_count} remote(s) from {config.add_remotes_file}")
            else:
                logging.info(f"All remotes from {config.add_remotes_file} already exist")
        except FileNotFoundError as e:
            logging.error(f"Failed to merge remotes: {e}")
        except Exception as e:
            logging.error(f"Error merging remotes from {config.add_remotes_file}: {e}")

    # Validate local filesystem alias (must be done after add_remotes merge)
    if config.local_filesystem_alias:
        try:
            logging.info(f"Validating local_filesystem_alias '{config.local_filesystem_alias}'")
            resolved_remote, resolved_path = rclone.rclone_config.resolve_alias_chain(config.local_filesystem_alias, '')
            configured_remotes = rclone.rclone_config.list_remotes()

            if resolved_remote in configured_remotes:
                # It's still a remote, not local filesystem
                logging.warning(
                    f"local_filesystem_alias '{config.local_filesystem_alias}' does not resolve to local filesystem "
                    f"(resolves to remote '{resolved_remote}'). Ignoring."
                )
                config.local_filesystem_alias = None
            else:
                # It's local filesystem - valid
                logging.info(
                    f"local_filesystem_alias '{config.local_filesystem_alias}' validated "
                    f"(resolves to local path: {resolved_remote}{resolved_path})"
                )
        except Exception as e:
            logging.warning(f"Failed to validate local_filesystem_alias '{config.local_filesystem_alias}': {e}. Ignoring.")
            config.local_filesystem_alias = None

    # Cleanup upload cache from previous runs (exclude active jobs)
    running_job_ids = rclone.get_running_jobs()
    interrupted_job_ids = [job['job_id'] for job in db.list_aborted_jobs()]
    active_job_ids = running_job_ids + interrupted_job_ids
    cleanup_cache(exclude_job_ids=active_job_ids)
    if active_job_ids:
        logging.info(f"Preserved upload cache for {len(active_job_ids)} active/interrupted jobs")

    # Auto-cleanup database if configured and no failed/interrupted jobs
    if config.auto_cleanup_db:
        failed_jobs = db.list_jobs(status='failed', limit=1)
        interrupted_jobs = db.list_aborted_jobs(limit=1)

        if not failed_jobs and not interrupted_jobs:
            logging.info("Auto-cleanup enabled and no failed/interrupted jobs found - cleaning database")
            count, _ = db.delete_all_jobs()
            if count > 0:
                logging.info(f"Deleted {count} jobs from database")
            # Reset job counter to 1
            rclone._job_counter = 0
            logging.info("Reset job counter to start at 1")
        else:
            logging.info("Auto-cleanup enabled but failed/interrupted jobs exist - skipping cleanup")

    # Register blueprints
    app.register_blueprint(files_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(stream_bp)
    app.register_blueprint(remotes_bp)
    app.register_blueprint(upload_bp)

    # Store instances in app context
    app.rclone = rclone
    app.db = db
    app.motus_config = config

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(rclone, db, config)

    # Add activity tracking middleware
    @app.before_request
    def track_activity():
        """Track user activity for idle timer"""
        # Only track API requests (not static files)
        if request.path.startswith('/api/'):
            update_activity()

    # Add routes
    register_routes(app, config)

    # Start idle timer if configured
    start_idle_timer(config.max_idle_time, rclone, db, config)

    logging.info("Flask application created successfully")

    return app


def register_routes(app: Flask, config: Config):
    """Register additional routes"""

    @app.route('/')
    def index():
        """Serve frontend"""
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/favicon.ico')
    def favicon_ico():
        """Serve favicon.ico if present in frontend directory"""
        return send_from_directory(app.static_folder, 'favicon.ico')

    @app.route('/favicon.png')
    def favicon_png():
        """Serve favicon.png if present in frontend directory"""
        return send_from_directory(app.static_folder, 'favicon.png')

    @app.route('/api/health')
    def health():
        """Health check endpoint"""
        return jsonify({
            'status': 'ok',
            'version': '1.0.0',
        })

    @app.route('/api/config')
    def get_config():
        """Get public configuration"""
        from .config import format_size
        return jsonify({
            'base_url': config.base_url,
            'version': '1.0.0',
            'default_mode': config.default_mode,
            'max_upload_size': config.max_upload_size,
            'max_upload_size_formatted': format_size(config.max_upload_size),
            'max_idle_time': config.max_idle_time,
            'allow_expert_mode': config.allow_expert_mode,
            'local_filesystem_alias': config.local_filesystem_alias,
        })

    @app.route('/api/preferences', methods=['GET'])
    @token_required
    def get_preferences():
        """Get user preferences"""
        prefs_file = os.path.join(config.data_dir, 'preferences.json')
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)
                return jsonify(prefs)
            except Exception as e:
                logging.error(f"Failed to load preferences: {e}")

        # Return defaults
        return jsonify({
            'view_mode': 'list',
            'show_hidden_files': False
        })

    @app.route('/api/preferences', methods=['POST'])
    @token_required
    def save_preferences():
        """Save user preferences"""
        try:
            data = request.get_json()
            prefs_file = os.path.join(config.data_dir, 'preferences.json')

            with open(prefs_file, 'w') as f:
                json.dump(data, f, indent=2)

            return jsonify({'message': 'Preferences saved'})
        except Exception as e:
            logging.error(f"Failed to save preferences: {e}")
            return jsonify({'error': 'Failed to save preferences'}), 500

    @app.route('/api/shutdown', methods=['POST'])
    @token_required
    def shutdown():
        """
        Gracefully shutdown the server

        Returns count of running jobs that were stopped
        """
        running_jobs_count = len(app.rclone.get_running_jobs())

        # Shutdown in background thread to allow response to be sent
        def shutdown_delayed():
            import sys
            print("\n[Shutdown] Thread started, waiting 0.5s...", file=sys.stderr, flush=True)
            time.sleep(0.5)  # Give time for response to be sent
            print("[Shutdown] Calling perform_shutdown()...", file=sys.stderr, flush=True)
            try:
                perform_shutdown(app.rclone, app.db, app.motus_config)
                print("[Shutdown] perform_shutdown() completed", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[Shutdown] ERROR in perform_shutdown: {e}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc(file=sys.stderr)

            print("[Shutdown] About to call os._exit(0) - process should die NOW", file=sys.stderr, flush=True)
            sys.stderr.flush()
            os._exit(0)  # Force exit - this should KILL the process immediately
            print("[Shutdown] THIS SHOULD NEVER PRINT", file=sys.stderr, flush=True)

        threading.Thread(target=shutdown_delayed, daemon=True).start()
        print("[Shutdown] Background thread spawned", flush=True)

        return jsonify({
            'message': 'Shutting down',
            'running_jobs_stopped': running_jobs_count
        })

    @app.errorhandler(404)
    def not_found(e):
        """Serve frontend for client-side routing"""
        # Check if this is an API request
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        # Otherwise serve the frontend
        return send_from_directory(app.static_folder, 'index.html')


def setup_logging(config: Config):
    """Setup logging configuration"""
    # Convert log level string to logging constant
    level = getattr(logging, config.log_level, logging.WARNING)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(),
        ]
    )

    # Reduce noise from libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


# For direct execution (development)
if __name__ == '__main__':
    config = Config()
    app = create_app(config)

    print("\n" + "="*60)
    print("OOD-Motus Server Starting")
    print("="*60)
    print(f"URL: {config.get_url()}")
    print(f"Token: {config.token}")
    print(f"Data directory: {config.data_dir}")
    print("="*60 + "\n")

    app.run(
        host=config.host,
        port=config.port,
        debug=False,
    )
