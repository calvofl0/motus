"""
Main Flask application for OOD-Motuz
Single-user rclone GUI with token authentication
"""
import logging
import os
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS

from .config import Config
from .models import Database
from .rclone.wrapper import RcloneWrapper
from .rclone.exceptions import RcloneNotFoundError

# Import API blueprints
from .api.files import files_bp, init_rclone as init_files_rclone
from .api.jobs import jobs_bp, init_jobs
from .api.stream import stream_bp, init_stream


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
    app.config['MOTUZ_TOKEN'] = config.token
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
        logging.info("rclone initialized successfully")
    except RcloneNotFoundError as e:
        logging.error(f"rclone initialization failed: {e}")
        raise

    # Initialize API modules with dependencies
    init_files_rclone(rclone)
    init_jobs(rclone, db)
    init_stream(rclone, db)

    # Register blueprints
    app.register_blueprint(files_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(stream_bp)

    # Store instances in app context
    app.rclone = rclone
    app.db = db
    app.motuz_config = config

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
