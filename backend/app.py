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

        # Mark them as interrupted in database
        for job_id in running_jobs:
            try:
                db.update_job(job_id, status='interrupted',
                              error_text='Job interrupted by server shutdown')
            except Exception as e:
                logging.error(f"Error marking job {job_id} as interrupted: {e}")

    # Clean up connection info files
    cleanup_connection_info(config)

    logging.info("Shutdown complete")
    return len(running_jobs)


def cleanup_connection_info(config: Config):
    """Remove PID and connection info files"""
    data_dir = Path(config.data_dir)
    pid_file = data_dir / 'motus.pid'
    connection_file = data_dir / 'connection.json'

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


def setup_signal_handlers(rclone: RcloneWrapper, db: Database, config: Config):
    """Setup signal handlers for graceful shutdown"""
    def shutdown_handler(signum, frame):
        """Handle SIGTERM/SIGINT for graceful shutdown"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logging.info(f"\n{sig_name} received, shutting down gracefully...")

        perform_shutdown(rclone, db, config)
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    logging.info("Signal handlers registered for graceful shutdown")


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

    app = Flask(
        __name__,
        static_folder='../frontend',
        static_url_path='',
    )

    # Flask config
    app.config['SECRET_KEY'] = config.secret_key
    app.config['MOTUS_TOKEN'] = config.token
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

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
        rclone = RcloneWrapper(config.rclone_path, config.rclone_config_file)
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

    # Initialize API modules with dependencies
    init_files_rclone(rclone)
    init_jobs(rclone, db)
    init_stream(rclone, db)
    # Use rclone's discovered config file path (not the config's, which may be None)
    init_remote_management(rclone.rclone_config_file, config.remote_templates_file)

    # Register blueprints
    app.register_blueprint(files_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(stream_bp)
    app.register_blueprint(remotes_bp)

    # Store instances in app context
    app.rclone = rclone
    app.db = db
    app.motuz_config = config

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(rclone, db, config)

    # Add routes
    register_routes(app, config)

    logging.info("Flask application created successfully")

    return app


def register_routes(app: Flask, config: Config):
    """Register additional routes"""

    @app.route('/')
    def index():
        """Serve frontend"""
        return send_from_directory(app.static_folder, 'index.html')

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
        return jsonify({
            'base_url': config.base_url,
            'version': '1.0.0',
            'default_mode': config.default_mode,
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
            time.sleep(0.5)  # Give time for response to be sent
            perform_shutdown(app.rclone, app.db, app.motuz_config)
            os._exit(0)  # Force exit

        threading.Thread(target=shutdown_delayed, daemon=True).start()

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
    print("OOD-Motuz Server Starting")
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
