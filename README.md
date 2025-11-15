# OOD-Motuz

A simplified, single-user web application for file transfers using rclone, designed for integration with Open OnDemand (OOD). Based on the [Motuz](https://github.com/FredHutch/motuz) project (MIT License), but with a streamlined, no-authentication backend suitable for OOD deployment.

## Features

- **Simple Token Authentication**: Jupyter-style token authentication (auto-generated or configurable)
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

### Frontend
- Simple HTML/JS demo interface (included)
- Can be replaced with full Motuz React frontend (instructions below)

## Requirements

- Python 3.10+
- rclone ([installation instructions](https://rclone.org/downloads/))
- pip

## Installation

### 1. Install rclone

```bash
# macOS
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash

# Or download from https://rclone.org/downloads/
```

### 2. Clone and Setup

```bash
git clone <repository-url> ood-motuz
cd ood-motuz

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Quick Start

```bash
# Run with default settings
python run.py

# The server will start and display:
# - Access URL with token
# - Token value
# - Data directory location
```

Example output:
```
======================================================================
  OOD-Motuz - Web-based File Transfer Interface
======================================================================

  Access URL (with token):
    http://127.0.0.1:8888?token=abc123...

  Access Token (auto-generated):
    abc123def456...

  Data directory: /home/user/.motuz
  Log file: /home/user/.motuz/motuz.log
  Log level: WARNING

======================================================================
```

### Configuration Options

#### Command Line Arguments

```bash
python run.py --help

# Common options:
python run.py --port 5000                    # Use specific port
python run.py --token mysecrettoken          # Use specific token
python run.py --data-dir /path/to/data       # Custom data directory
python run.py --log-level INFO               # Set log level
python run.py --no-browser                   # Don't open browser
```

#### Environment Variables

```bash
export MOTUZ_PORT=5000
export MOTUZ_TOKEN=mysecrettoken
export MOTUZ_DATA_DIR=/path/to/data
export MOTUZ_LOG_LEVEL=INFO
export MOTUZ_HOST=0.0.0.0  # Bind to all interfaces

python run.py
```

#### Configuration File

Create `~/.motuz/config.yml`:

```yaml
port: 5000
data_dir: /path/to/data
log_level: INFO
host: 127.0.0.1
```

**Priority**: CLI arguments > Environment variables > Config file > Defaults

### Port Allocation

Like Jupyter, OOD-Motuz automatically finds an available port if the default (8888) is in use:

```bash
python run.py  # Tries 8888, then 8889, 8890, ... up to 8888+100
```

## API Documentation

### Authentication

All API endpoints require authentication via token:

**Methods**:
1. Query parameter: `?token=your_token`
2. Header: `Authorization: token your_token`
3. Cookie: `motuz_token=your_token`

### Endpoints

#### Health Check
```http
GET /api/health
```

#### List Files
```http
POST /api/files/ls
Content-Type: application/json

{
  "path": "/path/to/list",
  "remote_config": {  // Optional, for remote storage
    "type": "s3",
    "region": "us-west-2",
    "access_key_id": "...",
    "secret_access_key": "..."
  }
}
```

#### Create Directory
```http
POST /api/files/mkdir
Content-Type: application/json

{
  "path": "/path/to/new/directory",
  "remote_config": {...}  // Optional
}
```

#### Delete File/Directory
```http
POST /api/files/delete
Content-Type: application/json

{
  "path": "/path/to/delete",
  "remote_config": {...}  // Optional
}
```

#### Start Copy Job
```http
POST /api/jobs/copy
Content-Type: application/json

{
  "src_path": "/source/path",
  "dst_path": "/destination/path",
  "src_config": {...},  // Optional, for remote source
  "dst_config": {...},  // Optional, for remote destination
  "copy_links": false   // Optional, follow symlinks
}

Response:
{
  "job_id": 123,
  "message": "Copy job started"
}
```

#### Start Move Job
```http
POST /api/jobs/move
Content-Type: application/json

{
  "src_path": "/source/path",
  "dst_path": "/destination/path"
  // ... same as copy
}
```

#### Get Job Status
```http
GET /api/jobs/{job_id}

Response:
{
  "job_id": 123,
  "operation": "copy",
  "status": "running",  // pending, running, completed, failed, cancelled
  "progress": 45,       // 0-100
  "text": "...",        // rclone output
  "error_text": "...",
  "finished": false,
  "exit_status": -1
}
```

#### Stop Job
```http
POST /api/jobs/{job_id}/stop
```

#### List All Jobs
```http
GET /api/jobs?status=running&limit=100&offset=0
```

#### Stream Job Progress (SSE)
```http
GET /api/stream/jobs/{job_id}
Content-Type: text/event-stream

# Returns real-time updates every 2 seconds
data: {"progress": 45, "text": "...", "finished": false}
```

### Remote Configuration Examples

#### S3 (AWS)
```json
{
  "type": "s3",
  "region": "us-west-2",
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}
```

#### S3-Compatible (MinIO, etc.)
```json
{
  "type": "s3",
  "endpoint": "https://minio.example.com",
  "access_key_id": "...",
  "secret_access_key": "..."
}
```

#### SFTP
```json
{
  "type": "sftp",
  "host": "example.com",
  "port": "22",
  "user": "username",
  "pass": "password"
}
```

#### Azure Blob
```json
{
  "type": "azureblob",
  "account": "myaccount",
  "key": "base64key=="
}
```

## Open OnDemand Integration

### 1. Create OOD App Directory

```bash
cd ~/ondemand/dev
mkdir motuz
cd motuz
```

### 2. Create manifest.yml

```yaml
---
name: Motuz File Transfer
description: Web-based file transfer interface using rclone
category: Files
subcategory: Utilities
role: batch_connect
```

### 3. Create form.yml

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

### 4. Create template/script.sh.erb

```bash
#!/bin/bash

# Load Python module (adjust for your system)
module load python/3.10

# Activate virtual environment
source <%= ENV['HOME'] %>/ood-motuz/venv/bin/activate

# Start OOD-Motuz
cd <%= ENV['HOME'] %>/ood-motuz
python run.py \
  --port ${port} \
  --host 0.0.0.0 \
  --token <%= password %> \
  --no-browser
```

### 5. Update connection.yml.erb

```yaml
---
port: <%= port %>
password: <%= password %>
```

## Development

### Running in Development Mode

```bash
# With verbose logging
python run.py --log-level DEBUG --allow-cors

# Custom port and token
python run.py --port 5000 --token devtoken123
```

### Project Structure

```
ood-motuz/
├── backend/
│   ├── api/
│   │   ├── files.py       # File operations endpoints
│   │   ├── jobs.py        # Job management endpoints
│   │   └── stream.py      # SSE progress streaming
│   ├── rclone/
│   │   ├── wrapper.py     # rclone command wrapper
│   │   ├── job_queue.py   # Background job queue
│   │   └── exceptions.py  # Custom exceptions
│   ├── app.py             # Flask application
│   ├── config.py          # Configuration management
│   ├── auth.py            # Token authentication
│   └── models.py          # SQLite database models
├── frontend/
│   └── index.html         # Demo frontend
├── run.py                 # Startup script
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Upgrading to Full Motuz Frontend

The current frontend is a simple demo. To use the full Motuz React frontend:

### 1. Install Node.js

```bash
# macOS
brew install node

# Linux (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 2. Install Frontend Dependencies

```bash
cd ood-motuz
npm install
```

### 3. Update Webpack Configuration

Edit `frontend/webpack/webpack.common.js` to update paths:

```javascript
// Update paths to work with our structure
```

### 4. Build Frontend

```bash
# Development build with watch
npm run watch

# Production build
npm run build
```

### 5. Adapt API Calls

The Motuz frontend expects different API endpoints. You'll need to:

1. Update `frontend/js/actions/*.jsx` to match our API structure
2. Simplify/remove authentication flows in `frontend/js/reducers/authReducer.jsx`
3. Update `frontend/js/managers/apiManager.jsx` for our endpoints

**Note**: This is a more involved process. The demo frontend is sufficient for basic usage and testing.

## Troubleshooting

### rclone not found

```bash
# Check if rclone is installed
rclone version

# If not, install it:
# https://rclone.org/downloads/
```

### Port already in use

The app automatically finds an available port. Check the startup banner for the actual port used.

### Permission denied on file operations

Ensure the user running OOD-Motuz has appropriate filesystem permissions.

### Database locked

Only one instance should run per data directory. Check for other running instances:

```bash
ps aux | grep "run.py"
```

## License

This project is based on [Motuz](https://github.com/FredHutch/motuz) (MIT License) and maintains the same MIT license.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Based on [Motuz](https://github.com/FredHutch/motuz) by Fred Hutchinson Cancer Research Center
- Uses [rclone](https://rclone.org/) for file operations
- Designed for [Open OnDemand](https://openondemand.org/)

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [rclone documentation](https://rclone.org/docs/)
- Review [Open OnDemand documentation](https://osc.github.io/ood-documentation/latest/)
