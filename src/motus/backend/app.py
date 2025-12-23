"""
Main Flask application for Motus
Single-user rclone GUI with token authentication
"""
import json
import logging
import os
import shutil
import signal
import sys
import time
import threading
import uuid
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS

from .config import Config
from .models import Database
from .rclone.wrapper import RcloneWrapper
from .rclone.exceptions import RcloneNotFoundError
from .auth import token_required

# Import API blueprints
from .api.files import files_bp, init_files
from .api.jobs import jobs_bp, init_jobs
from .api.stream import stream_bp, init_stream
from .api.remotes import remotes_bp, init_remote_management
from .api.upload import upload_bp, init_upload, cleanup_cache


# Global variables for idle timer and frontend tracking
_registered_frontends = {}  # {frontend_id: last_heartbeat_time}
_frontends_lock = threading.Lock()
_startup_time = None
_idle_timer_thread = None
_idle_timer_stop_event = None
_zero_frontends_grace_start = None  # Time when counter reached zero (for refresh grace period)
_shutting_down = False  # Flag to notify frontends that server is shutting down

# Grace period for frontend disconnections and shutdown coordination (seconds)
# Used when:
# 1. Frontend counter reaches zero (allows F5/refresh to re-register)
# 2. Shutdown initiated (allows all tabs to receive notification via heartbeat)
GRACE_PERIOD = 10


def safe_remove(path):
    """
    Safely remove a file or directory

    Handles both files and directories (recursively)
    """
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except Exception:
        raise  # Re-raise for caller to handle


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

    # Clean up lock socket file (run.py's cleanup_lock_socket won't run due to os._exit)
    lock_socket_path = Path(config.runtime_dir) / 'motus.lock'
    try:
        if lock_socket_path.exists():
            lock_socket_path.unlink()
            logging.debug(f"Removed lock socket file: {lock_socket_path}")
    except Exception as e:
        logging.warning(f"Could not remove lock socket file: {e}")

    # Clean up download cache - remove ALL zips on shutdown
    cleanup_download_cache(config, clean_all=True)

    logging.info("Shutdown complete")
    return len(running_jobs)


def cleanup_connection_info(config: Config):
    """
    Remove stale PID and connection info files from previous crashes

    NOTE: Does NOT remove lock socket - that's managed by run.py and should
    only be removed on graceful shutdown via cleanup_lock_socket()
    """
    runtime_dir = Path(config.runtime_dir)
    pid_file = runtime_dir / 'motus.pid'
    connection_file = runtime_dir / 'connection.json'
    dev_port_file = runtime_dir / 'dev-port.json'

    try:
        if pid_file.exists():
            pid_file.unlink()
            logging.debug(f"Removed stale PID file: {pid_file}")
    except Exception as e:
        logging.warning(f"Could not remove PID file: {e}")

    # DO NOT remove lock socket here - it's actively managed by run.py
    # Removing it here causes the socket to disappear after create_lock_socket()

    try:
        if connection_file.exists():
            connection_file.unlink()
            logging.debug(f"Removed stale connection file: {connection_file}")
    except Exception as e:
        logging.warning(f"Could not remove connection file: {e}")

    try:
        if dev_port_file.exists():
            dev_port_file.unlink()
            logging.debug(f"Removed stale dev port file: {dev_port_file}")
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


def idle_timer_worker(max_idle_time: int, rclone: RcloneWrapper, db: Database, config: Config):
    """
    Background worker to monitor idle time and shutdown if exceeded

    Shutdown conditions:
    1. NEVER shutdown if running jobs exist (backend activity)
    2. If no frontends registered AND max_idle_time passed since startup → shutdown
       (allows time for first frontend to register)
    3. If counter reaches 0 after frontends existed → 10s grace period, then shutdown
       (allows refresh/F5 to re-register before shutdown)
    4. If frontends registered BUT no heartbeat for max_idle_time → shutdown (all offline/crashed)
    """
    global _idle_timer_stop_event, _registered_frontends, _frontends_lock, _startup_time, _zero_frontends_grace_start

    logging.info(f"Idle timer started - will shutdown after {max_idle_time} seconds of inactivity")

    while not _idle_timer_stop_event.is_set():
        time.sleep(10)  # Check every 10 seconds

        # Always keep alive if there are running jobs (backend activity)
        running_jobs = rclone.get_running_jobs()
        if running_jobs:
            continue

        with _frontends_lock:
            frontend_count = len(_registered_frontends)

            # Case 1: No frontends registered
            if frontend_count == 0:
                time_since_startup = time.time() - _startup_time

                # If we never had any frontends, use max_idle_time (startup grace period)
                if _zero_frontends_grace_start is None and time_since_startup >= max_idle_time:
                    logging.info(f"No frontends registered for {time_since_startup:.1f}s >= {max_idle_time}s - shutting down")
                    # Shutdown in separate thread to avoid blocking
                    def shutdown_delayed():
                        perform_shutdown(rclone, db, config)
                        os._exit(0)
                    threading.Thread(target=shutdown_delayed, daemon=True).start()
                    break
                elif _zero_frontends_grace_start is None:
                    logging.debug(f"No frontends registered yet - waiting ({time_since_startup:.1f}s / {max_idle_time}s)")

                # If we had frontends but counter reached zero, use grace period
                elif _zero_frontends_grace_start is not None:
                    time_since_zero = time.time() - _zero_frontends_grace_start
                    if time_since_zero >= GRACE_PERIOD:
                        logging.info(f"Frontend counter at zero for {time_since_zero:.1f}s >= {GRACE_PERIOD}s grace period - shutting down")
                        # Shutdown in separate thread to avoid blocking
                        def shutdown_delayed():
                            perform_shutdown(rclone, db, config)
                            os._exit(0)
                        threading.Thread(target=shutdown_delayed, daemon=True).start()
                        break
                    else:
                        logging.debug(f"Grace period active - counter at zero for {time_since_zero:.1f}s / {GRACE_PERIOD}s")

            # Case 2: Frontends registered
            else:
                # Reset grace period timer if counter is non-zero
                _zero_frontends_grace_start = None

                # Check if all frontends are offline (no recent heartbeats)
                now = time.time()
                most_recent_heartbeat = max(_registered_frontends.values()) if _registered_frontends else 0
                time_since_last_heartbeat = now - most_recent_heartbeat

                if time_since_last_heartbeat >= max_idle_time:
                    logging.info(f"Frontends registered but no heartbeat for {time_since_last_heartbeat:.1f}s >= {max_idle_time}s - shutting down")
                    # Shutdown in separate thread to avoid blocking
                    def shutdown_delayed():
                        perform_shutdown(rclone, db, config)
                        os._exit(0)
                    threading.Thread(target=shutdown_delayed, daemon=True).start()
                    break
                else:
                    logging.debug(f"Idle check: {frontend_count} frontend(s) registered, last heartbeat {time_since_last_heartbeat:.1f}s ago (idle timeout: {max_idle_time}s)")


def start_idle_timer(max_idle_time: int, rclone: RcloneWrapper, db: Database, config: Config):
    """Start the idle timer background thread"""
    global _idle_timer_thread, _idle_timer_stop_event, _startup_time

    if max_idle_time <= 0:
        return  # Idle timer disabled

    _idle_timer_stop_event = threading.Event()
    _startup_time = time.time()  # Initialize startup time

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


def get_instance_status() -> str:
    """
    Get current instance status for lock socket protocol

    Returns:
        "grace_period" - Counter reached zero, waiting for re-registration (F5)
        "running" - Normal operation, frontends registered
        "startup" - No frontends yet, but not in grace period
    """
    global _zero_frontends_grace_start, _registered_frontends, _frontends_lock

    with _frontends_lock:
        if _zero_frontends_grace_start is not None:
            return "grace_period"
        elif len(_registered_frontends) > 0:
            return "running"
        else:
            return "startup"


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
                    # On shutdown: remove all ZIPs (files or directories)
                    safe_remove(zip_path)
                    cleaned += 1
                    logging.info(f"Cleaned up zip file on shutdown: {zip_file}")
                else:
                    # On startup: only remove expired ZIPs
                    file_age = now - os.path.getmtime(zip_path)
                    if file_age > max_age:
                        safe_remove(zip_path)
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
        static_folder='../static',
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

    # Initialize rclone wrapper with two-tier config support
    try:
        logging.info("Initializing rclone wrapper...")
        # Store temporary job logs in cache directory (cleaned up after storing in DB)
        logs_dir = config.log_cache_dir

        # Initialize with readonly config support (from --extra-remotes)
        rclone = RcloneWrapper(
            config.rclone_path,
            config.rclone_config_file,
            logs_dir,
            readonly_config_file=config.extra_remotes_file if config.extra_remotes_file else None,
            cache_dir=config.cache_dir
        )

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
    init_files(rclone, db)
    init_jobs(rclone, db)
    init_stream(rclone, db)
    # Use rclone's user config file and readonly config for two-tier system
    init_remote_management(
        rclone.rclone_config.user_config_file,  # User's master config
        config.remote_templates_file,
        rclone.rclone_path,
        readonly_config_file=config.extra_remotes_file if config.extra_remotes_file else None,
        cache_dir=config.cache_dir
    )
    init_upload(rclone, config.upload_cache_dir, config.max_upload_size)

    # Note: extra_remotes_file is now handled automatically by RcloneConfig's two-tier system
    # Readonly remotes are merged into a temporary config at initialization

    # Validate startup remote (if configured)
    if config.startup_remote:
        try:
            logging.info(f"Validating startup_remote '{config.startup_remote}'")
            rclone.rclone_config.reload()
            configured_remotes = rclone.rclone_config.list_remotes()

            if config.startup_remote not in configured_remotes:
                logging.warning(
                    f"startup_remote '{config.startup_remote}' not found in configured remotes. Ignoring."
                )
                config.startup_remote = None
            else:
                logging.info(f"startup_remote '{config.startup_remote}' validated")
        except Exception as e:
            logging.warning(f"Failed to validate startup_remote '{config.startup_remote}': {e}. Ignoring.")
            config.startup_remote = None

    # Validate absolute_paths mode (implies non-empty local_fs)
    if config.absolute_paths:
        if not config.local_fs or config.local_fs.strip() == '':
            logging.info("absolute_paths mode requires non-empty local_fs, using default: 'Local Filesystem'")
            config.local_fs = 'Local Filesystem'
        logging.info(f"absolute_paths mode enabled with local_fs='{config.local_fs}'")

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
            # Recalculate next job ID based on remaining jobs
            rclone.initialize_job_counter(db)
            logging.info("Recalculated job counter after cleanup")
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
            'startup_remote': config.startup_remote,
            'local_fs': config.local_fs,
            'absolute_paths': config.absolute_paths,
        })

    @app.route('/api/preferences', methods=['GET'])
    @token_required
    def get_preferences():
        """Get user preferences"""
        prefs_file = os.path.join(config.config_dir, 'preferences.json')

        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)
                logging.info(f"Loaded preferences from {prefs_file}")
                return jsonify(prefs)
            except Exception as e:
                logging.error(f"Failed to load preferences: {e}")
        else:
            logging.info(f"No preferences file found at {prefs_file}, returning defaults")

        # Return defaults (absolute_paths not set means use config default)
        return jsonify({
            'view_mode': 'list',
            'show_hidden_files': False,
            'theme': 'auto'
        })

    @app.route('/api/preferences', methods=['POST'])
    @token_required
    def save_preferences():
        """Save user preferences"""
        try:
            data = request.get_json()
            prefs_file = os.path.join(config.config_dir, 'preferences.json')

            with open(prefs_file, 'w') as f:
                json.dump(data, f, indent=2)

            logging.info(f"Saved preferences to {prefs_file}")
            return jsonify({'message': 'Preferences saved'})
        except Exception as e:
            logging.error(f"Failed to save preferences: {e}")
            return jsonify({'error': 'Failed to save preferences'}), 500

    @app.route('/api/frontend/register', methods=['POST'])
    @token_required
    def register_frontend():
        """
        Register a new frontend instance

        Returns a unique frontend_id to be used for heartbeats and unregister
        """
        global _registered_frontends, _frontends_lock, _zero_frontends_grace_start, _shutting_down

        # Reject registration if server is shutting down
        if _shutting_down:
            logging.info("Frontend registration rejected - server is shutting down")
            return jsonify({'error': 'server_shutting_down', 'message': 'Server is shutting down'}), 503

        frontend_id = str(uuid.uuid4())

        with _frontends_lock:
            _registered_frontends[frontend_id] = time.time()

            # If counter increased from 0, cancel grace period (refresh scenario)
            if len(_registered_frontends) == 1 and _zero_frontends_grace_start is not None:
                grace_elapsed = time.time() - _zero_frontends_grace_start
                logging.info(f"Frontend registered during grace period (after {grace_elapsed:.1f}s) - canceling shutdown timer")
                _zero_frontends_grace_start = None

        logging.info(f"Frontend registered: {frontend_id} (total: {len(_registered_frontends)})")

        return jsonify({'frontend_id': frontend_id})

    @app.route('/api/frontend/heartbeat', methods=['POST'])
    @token_required
    def frontend_heartbeat():
        """
        Update heartbeat timestamp for a registered frontend

        Expects JSON: {frontend_id: string}
        Returns: {status: ok, shutting_down: bool}
        """
        global _registered_frontends, _frontends_lock, _shutting_down

        data = request.get_json()
        frontend_id = data.get('frontend_id')

        if not frontend_id:
            return jsonify({'error': 'frontend_id required'}), 400

        with _frontends_lock:
            if frontend_id not in _registered_frontends:
                # Frontend was unregistered or never registered
                return jsonify({'error': 'frontend_id not registered'}), 404

            _registered_frontends[frontend_id] = time.time()

        return jsonify({'status': 'ok', 'shutting_down': _shutting_down})

    @app.route('/api/frontend/count', methods=['GET'])
    @token_required
    def frontend_count():
        """
        Get count of currently registered frontends

        Returns: {count: int}
        """
        global _registered_frontends, _frontends_lock

        with _frontends_lock:
            count = len(_registered_frontends)

        return jsonify({'count': count})

    @app.route('/api/frontend/unregister', methods=['POST'])
    def unregister_frontend():
        """
        Unregister a frontend instance

        Expects JSON: {frontend_id: string, auth_token: string (optional for sendBeacon)}

        Note: This endpoint doesn't use @token_required decorator because sendBeacon
        from beforeunload can't send custom headers. We validate the token from the
        request body if present, or skip auth check (unregister is safe to call
        multiple times and doesn't expose sensitive data).
        """
        global _registered_frontends, _frontends_lock, _zero_frontends_grace_start

        logging.debug(f"[Unregister] Request received - Content-Type: {request.content_type}, Headers: {dict(request.headers)}")
        logging.debug(f"[Unregister] Request data (first 200 bytes): {request.data[:200] if request.data else 'None'}")

        # Validate token from header (normal case) or body (sendBeacon case)
        from .auth import verify_token
        auth_header = request.headers.get('Authorization')
        if auth_header:
            # Normal API call with header
            token = auth_header.replace('token ', '', 1)
            if not verify_token(token):
                logging.warning("[Unregister] Invalid token in Authorization header")
                return jsonify({'error': 'Invalid token'}), 401
        # If no header, allow it through (sendBeacon from beforeunload)
        # Unregister is safe - worst case is duplicate unregister of non-existent frontend

        data = request.get_json()
        if not data:
            logging.warning(f"[Unregister] No JSON data in request - Content-Type was: {request.content_type}")
            return jsonify({'error': 'No JSON data'}), 400

        frontend_id = data.get('frontend_id')

        if not frontend_id:
            logging.warning(f"[Unregister] No frontend_id in JSON data: {data}")
            return jsonify({'error': 'frontend_id required'}), 400

        with _frontends_lock:
            if frontend_id in _registered_frontends:
                del _registered_frontends[frontend_id]
                remaining = len(_registered_frontends)
                logging.info(f"Frontend unregistered: {frontend_id} (remaining: {remaining})")

                # If counter reached zero, start grace period timer (for refresh scenario)
                if remaining == 0:
                    _zero_frontends_grace_start = time.time()
                    logging.info("Frontend counter reached zero - starting 10s grace period")
            else:
                logging.debug(f"Attempt to unregister unknown frontend: {frontend_id}")

        return jsonify({'status': 'ok'})

    @app.route('/api/shutdown', methods=['POST'])
    @token_required
    def shutdown():
        """
        Gracefully shutdown the server

        Sets global shutdown flag to notify all frontends via heartbeat

        Returns count of running jobs that were stopped
        """
        global _shutting_down

        running_jobs_count = len(app.rclone.get_running_jobs())

        # Set shutdown flag so frontends are notified via heartbeat
        _shutting_down = True
        logging.info("Shutdown initiated - all frontends will be notified via heartbeat")

        # Shutdown in background thread to allow response to be sent
        def shutdown_delayed():
            import sys
            print(f"\n[Shutdown] Thread started, waiting {GRACE_PERIOD}s for all frontends to be notified...", file=sys.stderr, flush=True)
            time.sleep(GRACE_PERIOD)  # Give all tabs time to receive shutdown notification via heartbeat
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
    import os
    from pathlib import Path

    # Convert log level string to logging constant
    level = getattr(logging, config.log_level, logging.WARNING)

    # Ensure log file directory exists
    log_file_path = Path(config.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Wipe the log file to start fresh for this session
    try:
        with open(config.log_file, 'w') as f:
            pass  # Truncate file
    except Exception as e:
        print(f"[WARNING] Could not wipe log file {config.log_file}: {e}", file=sys.stderr)

    # Get root logger
    root_logger = logging.getLogger()

    # CRITICAL: basicConfig() does NOTHING if root logger already has handlers
    # Some imports may have already configured logging, so we must force it
    # Clear any existing handlers first
    if root_logger.handlers:
        print(f"[WARNING] Root logger already has {len(root_logger.handlers)} handler(s). Clearing them.", file=sys.stderr)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # Set log level
    root_logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

    # Add file handler
    file_handler = logging.FileHandler(config.log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Add stream handler (stderr)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # Log confirmation that file logging is working
    logging.info(f"Logging configured: level={config.log_level}, file={config.log_file}")

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
