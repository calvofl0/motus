# Motus

A simplified, single-user web application for file transfers using rclone with a modern Vue.js interface, designed for integration with Open OnDemand (OOD). Based on the [Motus](https://github.com/FredHutch/motuz) project (MIT License), but with a streamlined, token-based authentication backend suitable for OOD deployment.

## Features

- **Modern Vue.js Interface**: Responsive, keyboard-driven UI with Easy and Expert modes
- **Simple Token Authentication**: Jupyter-style token authentication (auto-generated or configurable)
- **rclone Remote Support**: Graphical remote management with wizard-based configuration
- **rclone Backend**: Supports all rclone backends (S3, SFTP, Azure, Google Cloud, local filesystem, etc.)
- **Async File Transfers**: Background copy/move operations with real-time progress tracking
- **REST API**: Clean REST API for file operations and job management
- **Server-Sent Events**: Real-time progress updates via SSE
- **Single-User Design**: No complex authentication or multi-tenancy
- **OOD-Ready**: Easy integration with Open OnDemand

## Architecture

### Backend (Python/Flask)
- **Flask** web framework
- **SQLite** for job persistence
- **rclone** wrapper for file operations
- **Threading** for background transfers (no Celery/RabbitMQ needed)
- **Token authentication** (like Jupyter)

### Frontend (Vue.js 3)
- **Vue 3** with Composition API
- **Pinia** for state management
- **Vite** for development and building
- **Responsive design** with keyboard navigation
- **Easy Mode**: Simplified interface for basic copy/move operations
- **Expert Mode**: Advanced dual-pane file browser with contextual menus

## Requirements

- Python 3.10+
- Node.js 18+ and npm (for building the frontend)
- rclone ([installation instructions](https://rclone.org/downloads/))
- pip

## Installation

### Quick Install (Production)

1. **Install rclone**:

```bash
# macOS
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash

# Or download from https://rclone.org/downloads/
```

2. **Install Motus**:

```bash
# Clone repository
git clone <repository-url> motus
cd motus

# Install with pip (builds Vue frontend automatically)
pip install .
```

The pip installation will automatically:
- Install Python dependencies
- Install npm dependencies (requires Node.js)
- Build the Vue.js frontend
- Set up the `motus` command

3. **Run Motus**:

```bash
# Run with default settings
motus

# Or use run.py directly
python run.py
```

The server will start and display:
- Access URL with token
- Token value
- Data directory location

### Development Installation

For development work on Motus:

```bash
# Clone repository
git clone <repository-url> motus
cd motus

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend-vue
npm install
cd ..

# Build frontend (production)
cd frontend-vue
npm run build
cd ..

# Or run in development mode with hot-reload
python dev-vue.py
```

## Usage

### Quick Start

```bash
# Run with default settings
motus
# Or: python run.py

# The server will start and display:
# - Access URL with token
# - Token value
# - Data directory location
```

Example output:
```
======================================================================
  Motus et bouche cousue — A Web-based File Transfer Interface
======================================================================

  Access URL (with token):
    http://127.0.0.1:8888?token=abc123...

  Access Token (auto-generated):
    abc123def456...

  Data directory: /home/user/.motus
  Log file: /home/user/.motus/motus.log
  Log level: WARNING

======================================================================
```

### Development Mode

For frontend development with hot-reload:

```bash
# Start development server (starts backend if needed)
python dev-vue.py

# Options:
python dev-vue.py --port 3000              # Vue dev server port
python dev-vue.py --no-browser             # Don't open browser
python dev-vue.py --backend-args "--log-level DEBUG"  # Pass args to backend
```

The development server:
- Automatically starts the backend if not running
- Runs Vite dev server with hot-reload on port 3000
- Proxies API requests to the backend
- Auto-shuts down when backend stops
- Opens browser with authentication token

### User Interface Modes

Motus provides two interface modes:

**Easy Mode** (default):
- Simple, wizard-like interface
- Step-by-step file transfer process
- Perfect for basic copy/move operations
- Minimal learning curve

**Expert Mode**:
- Dual-pane file browser
- Keyboard navigation (arrow keys, Enter, ESC)
- Contextual menus (right-click or Shift+F10)
- Advanced features: aliases, custom remotes
- Keyboard shortcuts (Ctrl+C to copy, etc.)

Toggle between modes using the button in the header (if enabled with `--allow-expert-mode`).

### Using rclone Remotes

Configure remotes using the graphical UI or standard rclone workflow:

#### Via UI (Recommended)

1. Click **Manage Remotes** in the navigation bar
2. Click **+** to add a new remote
3. Choose from templates or create custom configuration
4. For OAuth remotes (Google Drive, OneDrive), follow the authentication flow

#### Via Command Line

```bash
# Configure a remote (interactive)
rclone config

# List configured remotes
rclone listremotes
```

Use remotes in the UI with `remote_name:/path` syntax:

```bash
# Examples:
myS3:/bucket/folder         # Browse S3 bucket
mySFTP:/remote/file.txt     # Access SFTP file
/tmp/local/file             # Local filesystem

# Copy operations:
myS3:/bucket/data.csv  →  /tmp/downloads/       # S3 to local
/tmp/file.txt  →  myS3:/bucket/backup/          # Local to S3
myS3:/data/  →  mySFTP:/backup/                 # S3 to SFTP
```

**Configuration Priority**: `RCLONE_CONFIG` env var > `~/.motus/config.yml` > rclone default

```bash
# Use custom rclone config
export RCLONE_CONFIG=/path/to/rclone.conf
motus

# Or in ~/.motus/config.yml:
# rclone_config_file: /path/to/rclone.conf
```

### Managing Remotes via UI

The graphical remote management interface allows you to:
- View all configured remotes with their types
- Delete existing remotes (click the `-` button)
- Add new remotes from templates (click **Add from Template**)
- Create custom remotes via Wizard or Manual configuration
- Handle OAuth authentication flow automatically
- Create alias remotes from folder context menu

#### Using Remote Templates

1. Create a remote templates file:
   ```bash
   cp remote_templates.conf.example remote_templates.conf
   ```

2. Configure Motus to use the templates:
   ```bash
   # Via command line
   motus --remote-templates remote_templates.conf

   # Via environment variable
   export MOTUS_REMOTE_TEMPLATES=/path/to/remote_templates.conf
   motus

   # Or in ~/.motus/config.yml:
   # remote_templates_file: /path/to/remote_templates.conf
   ```

3. In the web interface, click **Manage Remotes** → **Add from Template**

#### Creating Custom Templates

Templates use a simple INI-style format with template variables:

```ini
# Template name in square brackets
[MyS3Storage]
type = s3
provider = Other
no_check_bucket = true
# Template variables use {{ Variable Name }} syntax
access_key_id = {{ Access Key ID }}
secret_access_key = {{ Secret Access Key }}
endpoint = https://s3.example.com
```

When adding a remote from this template, users will be prompted for:
- Remote Name
- Access Key ID
- Secret Access Key

### Configuration Options

#### Command Line Arguments

```bash
motus --help

# Common options:
motus --port 5000                        # Use specific port
motus --token mysecrettoken              # Use specific token
motus --data-dir /path/to/data           # Custom data directory
motus --log-level INFO                   # Set log level
motus --no-browser                       # Don't open browser
motus --expert-mode                      # Start in Expert mode
motus --allow-expert-mode                # Show mode toggle in UI
motus --remote-templates templates.conf  # Remote templates file
motus --max-idle-time 3600               # Auto-quit after 1 hour idle
motus --auto-cleanup-db                  # Clean DB at startup
motus --max-upload-size 1G               # Limit upload size
```

#### Environment Variables

```bash
export MOTUS_PORT=5000
export MOTUS_TOKEN=mysecrettoken
export MOTUS_DATA_DIR=/path/to/data
export MOTUS_LOG_LEVEL=INFO
export MOTUS_HOST=0.0.0.0                # Bind to all interfaces
export MOTUS_DEFAULT_MODE=expert         # Start in Expert mode
export MOTUS_ALLOW_EXPERT_MODE=true      # Show mode toggle
export MOTUS_REMOTE_TEMPLATES=/path/to/templates.conf
export MOTUS_MAX_IDLE_TIME=3600
export MOTUS_AUTO_CLEANUP_DB=true
export MOTUS_MAX_UPLOAD_SIZE=1G

motus
```

#### Configuration File

Create `~/.motus/config.yml`:

```yaml
port: 5000
data_dir: /path/to/data
log_level: INFO
host: 127.0.0.1
default_mode: expert
allow_expert_mode: true
remote_templates_file: /path/to/templates.conf
max_idle_time: 3600
auto_cleanup_db: true
max_upload_size: 1073741824  # 1GB in bytes
```

**Priority**: CLI arguments > Environment variables > Config file > Defaults

### Port Allocation

Like Jupyter, Motus automatically finds an available port if the default (8888) is in use:

```bash
motus  # Tries 8888, then 8889, 8890, ... up to 8888+100
```

### Multi-Instance Protection

Motus prevents multiple instances from running on the same data directory:

```bash
# First instance
motus --data-dir /tmp/motus-data

# Second instance with same data dir will show connection info
# and open browser to existing instance instead of starting new one
motus --data-dir /tmp/motus-data

# To run multiple instances, use different data directories
motus --data-dir /tmp/motus-1
motus --data-dir /tmp/motus-2
```

## Building the Frontend

The Vue.js frontend is automatically built during `pip install`. To rebuild manually:

```bash
cd frontend-vue
npm install      # Install dependencies (if not done)
npm run build    # Build for production (outputs to ../frontend-dist/)
```

For development with hot-reload:

```bash
python dev-vue.py  # Starts Vite dev server on port 3000
```

## API Documentation

### Authentication

All API endpoints require authentication via token:

**Methods**:
1. Query parameter: `?token=your_token`
2. Header: `Authorization: token your_token`
3. Cookie: `motus_token=your_token`

### Key Endpoints

#### Health Check
```http
GET /api/health
```

#### Configuration
```http
GET /api/config

Response:
{
  "base_url": "",
  "version": "1.0.0",
  "default_mode": "easy",
  "allow_expert_mode": false,
  "max_upload_size": 0,
  "max_idle_time": 0
}
```

#### List Remotes
```http
GET /api/remotes

Response:
{
  "remotes": [
    {"name": "myS3", "type": "s3", "is_oauth": false},
    {"name": "gdrive", "type": "drive", "is_oauth": true}
  ],
  "count": 2
}
```

#### List Files
```http
POST /api/files/ls
Content-Type: application/json

{
  "path": "/path/to/list"  // Local: /tmp or Remote: myS3:/bucket
}

Response:
{
  "files": [
    {
      "name": "file.txt",
      "size": 1024,
      "modified": "2024-01-01T00:00:00Z",
      "is_dir": false,
      "mime_type": "text/plain"
    }
  ]
}
```

#### Start Copy Job
```http
POST /api/jobs/copy
Content-Type: application/json

{
  "src_path": "myS3:/bucket/file.txt",
  "dst_path": "/tmp/backup/",
  "copy_links": false
}

Response:
{
  "job_id": 123,
  "message": "Copy job started"
}
```

#### Get Job Status
```http
GET /api/jobs/{job_id}

Response:
{
  "job_id": 123,
  "operation": "copy",
  "status": "running",
  "progress": 45,
  "text": "...",
  "finished": false
}
```

#### Stream Job Progress (SSE)
```http
GET /api/stream/jobs/{job_id}
Content-Type: text/event-stream

# Returns real-time updates
data: {"progress": 45, "text": "...", "finished": false}
```

For complete API documentation, see the backend source code in `backend/api/`.

## Open OnDemand Integration

### 1. Install Motus

```bash
cd ~
git clone <repository-url> motus
cd motus

# Install in virtual environment
python3 -m venv venv
source venv/bin/activate
pip install .
```

### 2. Create OOD App Directory

```bash
cd ~/ondemand/dev
mkdir motus
cd motus
```

### 3. Create manifest.yml

```yaml
---
name: Motus File Transfer
description: Web-based file transfer interface using rclone
category: Files
subcategory: Utilities
role: batch_connect
```

### 4. Create form.yml

```yaml
---
cluster: "your_cluster"
attributes:
  bc_num_hours:
    value: 2
  bc_num_slots:
    value: 1
  node_type:
    widget: select
    options:
      - "standard"
```

### 5. Create template/script.sh.erb

```bash
#!/bin/bash

# Load Python module (adjust for your system)
module load python/3.10

# Activate virtual environment
source <%= ENV['HOME'] %>/motus/venv/bin/activate

# Start Motus
cd <%= ENV['HOME'] %>/motus
python run.py \
  --port ${port} \
  --host 0.0.0.0 \
  --token <%= password %> \
  --no-browser \
  --data-dir <%= ENV['HOME'] %>/.motus
```

### 6. Create template/connection.yml.erb

```yaml
---
port: <%= port %>
password: <%= password %>
```

## Development

### Project Structure

```
motus/
├── backend/
│   ├── api/
│   │   ├── files.py          # File operations endpoints
│   │   ├── jobs.py           # Job management endpoints
│   │   ├── remotes.py        # Remote management endpoints
│   │   └── stream.py         # SSE progress streaming
│   ├── rclone/
│   │   ├── wrapper.py        # rclone command wrapper
│   │   ├── job_queue.py      # Background job queue
│   │   └── exceptions.py     # Custom exceptions
│   ├── app.py                # Flask application
│   ├── config.py             # Configuration management
│   ├── auth.py               # Token authentication
│   └── models.py             # SQLite database models
├── frontend-vue/             # Vue.js source code
│   ├── src/
│   │   ├── components/       # Vue components
│   │   ├── views/            # Main views (Easy/Expert modes)
│   │   ├── store/            # Pinia store
│   │   └── App.vue           # Root component
│   ├── package.json          # npm dependencies
│   └── vite.config.js        # Vite configuration
├── frontend-dist/            # Built Vue.js app (generated)
├── motus/                    # CLI entry point
│   ├── __init__.py
│   └── cli.py                # CLI wrapper
├── run.py                    # Production startup script
├── dev-vue.py                # Development helper
├── build_frontend.py         # Build hook for pip install
├── pyproject.toml            # Python package configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

### Development Workflow

1. **Backend changes**:
   ```bash
   # Edit files in backend/
   # Restart run.py or dev-vue.py to see changes
   python run.py --log-level DEBUG
   ```

2. **Frontend changes**:
   ```bash
   # Start dev server with hot-reload
   python dev-vue.py

   # Edit files in frontend-vue/src/
   # Changes appear immediately in browser
   ```

3. **Build for production**:
   ```bash
   cd frontend-vue
   npm run build
   cd ..

   # Test production build
   python run.py
   ```

4. **Test installation**:
   ```bash
   # Build and install locally
   pip install -e .

   # Test CLI
   motus --help
   ```

### Running Tests

```bash
# Python backend tests
pytest

# Frontend tests (if available)
cd frontend-vue
npm test
```

## Troubleshooting

### rclone not found

```bash
# Check if rclone is installed
rclone version

# If not, install it:
# https://rclone.org/downloads/
```

### Node.js/npm not found

```bash
# Check if Node.js is installed
node --version
npm --version

# Install Node.js:
# macOS: brew install node
# Ubuntu/Debian: sudo apt install nodejs npm
# Windows: Download from https://nodejs.org/
```

### Port already in use

The app automatically finds an available port. Check the startup banner for the actual port used.

### Permission denied on file operations

Ensure the user running Motus has appropriate filesystem permissions.

### Database locked

Only one instance should run per data directory. Check for other running instances:

```bash
ps aux | grep "run.py"
```

Or use the built-in instance detection - if another instance is running, Motus will show its connection info instead of starting a new one.

### Frontend not building

```bash
# Clean and rebuild
cd frontend-vue
rm -rf node_modules package-lock.json
npm install
npm run build
```

## Security

See [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md) for detailed security analysis and recommendations.

Key security features:
- Token-based authentication (similar to Jupyter)
- Single-user design (no multi-tenancy complexity)
- Local-only binding by default (127.0.0.1)
- No persistent sessions
- Input validation on all endpoints

## License

This project is based on [Motus](https://github.com/FredHutch/motuz) (MIT License) and maintains the same MIT license.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Based on [Motus](https://github.com/FredHutch/motuz) by Fred Hutchinson Cancer Research Center
- Uses [rclone](https://rclone.org/) for file operations
- Designed for [Open OnDemand](https://openondemand.org/)
- Built with [Vue.js](https://vuejs.org/) and [Flask](https://flask.palletsprojects.com/)

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [rclone documentation](https://rclone.org/docs/)
- Review [Open OnDemand documentation](https://osc.github.io/ood-documentation/latest/)
