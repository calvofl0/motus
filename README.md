<div align="center">
    <img src="frontend/public/img/logo.png" width="100" height="100">
    <h1>Motus</h1>
    <p>
        <b>A simple, single-user web application for large scale data movements between on-premise and cloud. Inspired by the <a href="https://github.com/FredHutch/motuz" target="_blank">Motuz</a> project.</b>
    </p>
    <br>
</div>

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Quick Start](#quick-start)
  - [Development Mode](#development-mode)
  - [User Interface Modes](#user-interface-modes)
  - [Using rclone Remotes](#using-rclone-remotes)
  - [Managing Remotes via UI](#managing-remotes-via-ui)
- [Configuration Options](#configuration-options)
  - [Command Line Arguments](#command-line-arguments)
  - [Environment Variables](#environment-variables)
  - [Configuration File](#configuration-file)
  - [XDG Base Directory Support](#xdg-base-directory-support)
  - [Cache Directory Structure](#cache-directory-structure)
  - [Port Allocation](#port-allocation)
  - [Multi-Instance Protection](#multi-instance-protection)
- [Building the Frontend](#building-the-frontend)
- [API Documentation](#api-documentation)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Development Workflow](#development-workflow)
  - [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [Support](#support)

## Features

- **Modern Vue.js Interface**: Responsive, keyboard-driven UI with Easy and Expert modes
- **Simple Token Authentication**: Jupyter-style token authentication (auto-generated or configurable)
- **rclone Remote Support**: Graphical remote management with wizard-based configuration
- **rclone Backend**: Supports all rclone backends (S3, SFTP, Azure, Google Cloud, local filesystem, etc.)
- **Async File Transfers**: Background copy/move operations with real-time progress tracking
- **File Download**: Download files/folders to your laptop with automatic ZIP compression for large transfers
- **Drag-and-Drop Upload**: Upload files and folders directly from your desktop browser
- **REST API**: Clean REST API for file operations and job management
- **Server-Sent Events**: Real-time progress updates via SSE
- **Single-User Design**: No complex authentication or multi-tenancy
- **Reverse Proxy Support**: Works seamlessly behind reverse proxies with custom base paths

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
- **Easy Mode**: Advanced dual-pane file browser with contextual menus
- **Expert Mode**: Simplified interface for basic operations

## Requirements

- Python 3.8+
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
cd frontend
npm install
cd ..

# Build frontend (production)
cd frontend
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
- Dual-pane file browser
- Keyboard navigation (arrow keys, Enter, ESC)
- Contextual menus (right-click or Shift+F10)
- Advanced features: aliases, custom remotes
- Keyboard shortcuts (Ctrl+C to copy, etc.)

**Expert Mode**:
- Simple, streamlined interface
- Direct access to authentication and remote operations
- Basic file operations
- Manual command-line style workflow
- Minimal GUI overhead

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

#### Merging Remotes at Startup

You can merge remotes from another rclone config file at startup using `--add-remotes`. This is useful for:
- Sharing common remotes across multiple users
- Maintaining a separate config file with standard remotes
- Pre-configuring remotes for your team

```bash
# Add remotes from another config file at startup
motus --add-remotes /path/to/shared-remotes.conf

# Via environment variable
export MOTUS_ADD_REMOTES=/path/to/shared-remotes.conf
motus

# Or in ~/.motus/config.yml:
# add_remotes_file: /path/to/shared-remotes.conf
```

**Behavior:**
- Only remotes that don't already exist are added (merged into your local rclone config)
- Existing remotes are never overwritten
- Happens once at startup
- Merged remotes become part of your local rclone config and can be modified
- The source file specified by `--add-remotes` remains read-only and unchanged

#### Startup Remote and Local Filesystem Configuration

You can customize which remote is shown by default at startup and how the local filesystem appears in the UI.

##### Startup Remote (`--startup-remote` or `-s`)

Set the default remote to show on both panes when the application starts:

```bash
# Set startup remote
motus -s my_s3_bucket

# Via environment variable
export MOTUS_STARTUP_REMOTE=my_s3_bucket
motus

# Or in ~/.motus/config.yml:
# startup_remote: my_s3_bucket
```

**Behavior:**
- Can be **any remote** (not restricted to local filesystem)
- If the remote doesn't exist, falls back to local filesystem with `/`
- Both panes start on this remote at the root path (`/`)

##### Local Filesystem Entry (`--local-fs` or `-l`, `--hide-local-fs` or `-H`)

Control how the "Local Filesystem" entry appears in the remote dropdown:

```bash
# Customize the label
motus -l "My Computer"

# Hide with default label (legacy approach)
motus -l ""

# Hide with custom label (shows "My Server" if forced visible by absolute-paths)
motus -l "My Server" -H

# Via environment variables
export MOTUS_LOCAL_FS="My Server"
export MOTUS_HIDE_LOCAL_FS=true
motus

# Or in ~/.motus/config.yml:
# local_fs: "My Server"
# hide_local_fs: true
```

**Options:**
- `--local-fs` / `-l`: Sets the display name for local filesystem (default: "Local Filesystem")
- `--hide-local-fs` / `-H`: Hides local filesystem from dropdown initially (can be overridden)

**Behavior:**
- Local filesystem can be forced to show when:
  - No `--startup-remote` is set (requires browsing local filesystem)
  - `--absolute-paths` is enabled (needed for navigating outside aliases)
  - Configured `--startup-remote` fails to browse
- When forced to show, uses the name from `--local-fs`
- Default: Local filesystem shown with name "Local Filesystem"

**Example Use Cases:**

1. **Hide local filesystem, use remote as default:**
   ```bash
   motus -s my_remote -H
   # Local filesystem hidden unless absolute-paths toggled on
   ```

2. **Hide with custom name (shows if absolute-paths enabled):**
   ```bash
   motus -l "This Server" -H --startup-remote my_s3
   # Hidden initially, but shows as "This Server" if user enables absolute paths
   ```

3. **Custom label, always visible:**
   ```bash
   motus -l "This Server"
   # "This Server" appears in dropdown (default behavior)
   ```

4. **Hide local filesystem (legacy syntax):**
   ```bash
   motus -l ""
   # Equivalent to: motus -H
   ```

#### Absolute Paths Mode (`--absolute-paths`)

Enable absolute filesystem path display for local aliases with automatic remote switching:

```bash
# Enable absolute paths mode
motus --absolute-paths

# Via environment variable
export MOTUS_ABSOLUTE_PATHS=true
motus

# Or in ~/.motus/config.yml:
# absolute_paths: true
```

**Behavior:**

When enabled, this mode provides an enhanced experience for working with local filesystem aliases:

1. **Absolute Path Display:** Path input shows full absolute paths (e.g., `/home/user/documents/file.txt`) instead of relative paths
2. **Automatic Remote Switching:** The remote dropdown automatically switches based on the current path:
   - Navigating to `/home/user/documents` with a `docs` alias → switches to `docs`
   - Navigating outside alias boundaries → switches to "Local Filesystem"
   - Uses longest prefix match when multiple aliases could apply
3. **Direct Path Operations:** File operations use absolute paths directly for local aliases
4. **Requires Local Filesystem:** Automatically ensures `--local-fs` is non-empty (defaults to "Local Filesystem")

**Example Scenario:**

```bash
# Setup: Create aliases in rclone config
[docs]
type = alias
remote = /home/user/documents

[projects]
type = alias
remote = /home/user/documents/my-projects

# Start Motus with absolute paths
motus --absolute-paths
```

**Navigation Behavior:**
- Start at `/` with "Local Filesystem" selected
- Navigate to `/home/user/documents` → Dropdown switches to `docs`
- Navigate to `/home/user/documents/my-projects` → Dropdown switches to `projects` (more specific)
- Navigate up to `/home/user` → Dropdown switches back to "Local Filesystem"
- Type `/home/user/documents/report.pdf` and press Enter → Auto-switches to `docs`

**Benefits:**
- Seamless navigation across filesystem and aliases
- Clear indication of current location with absolute paths
- No need to manually switch remotes when crossing alias boundaries
- Consistent experience with standard filesystem tools

### Managing Remotes via UI

The graphical remote management interface allows you to:
- View all configured remotes with their types
- Delete existing remotes
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

# Common options (short variants available for some):
motus -p 5000                                     # Use specific port (--port)
motus --token mysecrettoken                       # Use specific token
motus -d /path/to/data                            # Custom data directory (--data-dir)
motus --cache-dir /path/to/cache                  # Custom cache directory (default: {data_dir}/cache)
motus -c config.yml                               # Path to config file (--config)
motus --log-level INFO                            # Set log level
motus --log-file /path/to/logfile.log             # Custom log file location (default: {cache_dir}/motus.log)
motus -v                                          # Verbose mode (INFO level, --log-level takes precedence)
motus -vv                                         # Very verbose mode (DEBUG level)
motus --no-browser                                # Don't open browser
motus --expert-mode                               # Start in Expert mode (auto-enables --allow-expert-mode)
motus -e                                          # Show mode toggle in UI (--allow-expert-mode)
motus --remote-templates templates.conf           # Remote templates file
motus -r /path/to/rclone.conf                     # Merge remotes from another config file (--add-remotes)
motus -s my_remote                                # Set startup remote (--startup-remote)
motus -l "My Server"                              # Customize local filesystem name (--local-fs)
motus -H                                          # Hide local filesystem entry (--hide-local-fs)
motus --absolute-paths                            # Enable absolute paths mode for local aliases
motus --max-idle-time 3600                        # Auto-quit after 1 hour idle
motus --auto-cleanup-db                           # Clean DB at startup
motus --max-upload-size 1G                        # Limit upload size
motus -m 5G                                       # Maximum download size allowed (--max-download-size, default: 0/unlimited)
motus --max-uncompressed-download-size 100M       # ZIP threshold for downloads (default: 100M)
```

#### Environment Variables

```bash
export MOTUS_PORT=5000
export MOTUS_TOKEN=mysecrettoken
export MOTUS_DATA_DIR=/path/to/data                      # Legacy mode: all files in one directory
export MOTUS_CONFIG_DIR=/path/to/config                  # Override config directory (preferences.json)
export MOTUS_CACHE_DIR=/path/to/cache                    # Override cache directory
export MOTUS_RUNTIME_DIR=/path/to/runtime                # Override runtime directory (PID, connection files)
export MOTUS_LOG_LEVEL=INFO
export MOTUS_LOG_FILE=/path/to/logfile.log               # Override log file location (default: {cache_dir}/motus.log)
export MOTUS_HOST=0.0.0.0                                # Bind to all interfaces
export MOTUS_DEFAULT_MODE=expert                         # Start in Expert mode
export MOTUS_ALLOW_EXPERT_MODE=true                      # Show mode toggle
export MOTUS_REMOTE_TEMPLATES=/path/to/templates.conf    # Or relative: templates.conf (resolves to config_dir/templates.conf)
export MOTUS_EXTRA_REMOTES=/path/to/rclone.conf          # Or relative: remotes.conf (resolves to config_dir/remotes.conf)
export MOTUS_STARTUP_REMOTE=my_remote                    # Default remote at startup
export MOTUS_LOCAL_FS="My Server"                        # Local filesystem label (default: "Local Filesystem")
export MOTUS_HIDE_LOCAL_FS=true                          # Hide local filesystem entry (default: false)
export MOTUS_ABSOLUTE_PATHS=true                         # Enable absolute paths mode for local aliases
export MOTUS_MAX_IDLE_TIME=3600
export MOTUS_AUTO_CLEANUP_DB=true
export MOTUS_MAX_UPLOAD_SIZE=1G
export MOTUS_MAX_DOWNLOAD_SIZE=5G                        # Maximum download size allowed (0=unlimited)
export MOTUS_MAX_UNCOMPRESSED_DOWNLOAD_SIZE=100M         # ZIP threshold for downloads

motus
```

#### Configuration File

Create a config file and specify it with `--config` or `-c`:

```yaml
# Directory configuration
data_dir: /path/to/data                         # Legacy mode: all files in one directory
config_dir: /custom/config                      # Override config directory (preferences.json)
cache_dir: /fast/ssd/cache                      # Override cache directory
runtime_dir: /custom/runtime                    # Override runtime directory (PID, connection files)

# Server configuration
port: 5000
host: 127.0.0.1
log_level: INFO
log_file: /path/to/logfile.log                 # Custom log file location (default: {cache_dir}/motus.log)

# UI configuration
default_mode: expert
allow_expert_mode: true

# Remote configuration (relative paths resolved against config_dir)
remote_templates_file: templates.conf           # Absolute or relative to config_dir
extra_remotes_file: team-remotes.conf           # Absolute or relative to config_dir
startup_remote: my_remote                       # Default remote at startup
local_fs: "My Server"                           # Local filesystem label (default: "Local Filesystem")
hide_local_fs: false                            # Hide local filesystem entry (default: false)
absolute_paths: true                            # Enable absolute paths mode for local aliases

# Limits and behavior
max_idle_time: 3600
auto_cleanup_db: true                           # Supports flexible time formats (see below)
max_upload_size: "1G"                           # 1GB (also accepts bytes: 1073741824, or 0 for unlimited)
max_download_size: "5G"                         # 5GB (also accepts bytes: 5368709120, or 0 for unlimited)
max_uncompressed_download_size: "100M"          # 100MB (also accepts bytes: 104857600)
download_cache_max_age: 3600                    # ZIP file retention (seconds, default: 1 hour)
```

**Auto-Cleanup Database**: The `auto_cleanup_db` option automatically deletes **completed jobs only** (failed/interrupted jobs are always preserved). Supports flexible time formats:
- `false`, `no`, `0`: Disabled (default)
- `true`, `yes`, `1`: Delete all completed jobs at startup
- **ISO timestamps**: `2006-08-14T02:34:56+01:00` or `2006-08-14` - Delete completed jobs finished before this date
- **Relative times**: Flexible format with optional spaces between number and unit
  - **Compact format**: `5h`, `30min`, `45s`, `2d`, `3mo`, `1y`
  - **Spaced format**: `1 day`, `3 days`, `5 hours`, `1 month`, `3 months`, `2 years`
  - **Supported units**:
    - Seconds: `s`, `sec`, `second`, `seconds`
    - Minutes: `m`, `min`, `minute`, `minutes`
    - Hours: `h`, `hr`, `hour`, `hours`
    - Days: `d`, `day`, `days`
    - Months: `mo`, `mon`, `month`, `months` (approximated as 30 days)
    - Years: `y`, `yr`, `year`, `years` (approximated as 365 days)

Examples:
```yaml
auto_cleanup_db: true              # Delete all completed jobs
auto_cleanup_db: 7d                # Delete jobs older than 7 days (compact)
auto_cleanup_db: 7 days            # Delete jobs older than 7 days (spaced)
auto_cleanup_db: 2024-01-01        # Delete jobs before Jan 1, 2024
auto_cleanup_db: 24h               # Delete jobs older than 24 hours (compact)
auto_cleanup_db: 1 day             # Delete jobs older than 1 day (spaced)
auto_cleanup_db: 3 months          # Delete jobs older than 3 months (~90 days)
auto_cleanup_db: 1 year            # Delete jobs older than 1 year (~365 days)
```

**Note**:
- Cleanup happens once at server startup
- Only completed jobs are deleted (failed/interrupted jobs are preserved)
- Relative paths for `remote_templates_file` and `extra_remotes_file` are resolved against the config directory (`config_dir`), making it easy to keep configuration files together.

**Priority**: CLI arguments > MOTUS_* environment variables > Config file > XDG_* environment variables > Defaults

#### XDG Base Directory Support

Motus follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) for organizing files and directories on Linux systems.

**XDG Mode (default)**:
When no `--data-dir`, `MOTUS_DATA_DIR`, or `data_dir` in config file is set, Motus uses XDG directories:

```
~/.config/motus/               (XDG_CONFIG_HOME/motus)
├── preferences.json           # User UI preferences (theme, view mode, etc.)
└── remote_templates.conf      # Optional: remote templates

~/.local/share/motus/          (XDG_DATA_HOME/motus)
└── motus.db                   # Job history and database

~/.cache/motus/                (XDG_CACHE_HOME/motus)
├── download/                  # Temporary ZIP files for downloads
├── upload/                    # Staging area for uploads
├── log/                       # Temporary job logs
└── motus.log                  # Application log

/run/user/{uid}/motus/         (XDG_RUNTIME_DIR/motus)
├── motus.pid                  # Process ID file
└── connection.json            # Dev server connection info
```

**Legacy Mode**:
When `--data-dir` is set (via CLI, `MOTUS_DATA_DIR` env var, or config file), everything goes to that directory by default:

```
{data_dir}/
├── motus.db                   # Job history
├── motus.pid                  # Process ID file
├── connection.json            # Connection info
├── preferences.json           # User preferences
├── remote_templates.conf      # Optional: remote templates
└── cache/                     # Cache directory (can be overridden with MOTUS_CACHE_DIR)
    ├── download/
    ├── upload/
    ├── log/
    └── motus.log
```

**Overriding Individual Directories**:

Each directory can be overridden independently, even in legacy mode:

```bash
# Override cache location (most common)
export MOTUS_CACHE_DIR=/fast/ssd/cache
motus

# Override config directory (where preferences.json is stored)
export MOTUS_CONFIG_DIR=/custom/config
motus

# Override runtime directory (where connection.json and PID files go)
export MOTUS_RUNTIME_DIR=/custom/runtime
motus

# Mix and match: XDG for most things, custom cache
motus --cache-dir /fast/ssd/cache
```

Available override environment variables:
- `MOTUS_CONFIG_DIR`: Override config directory (XDG: `~/.config/motus`, Legacy: `{data_dir}`)
- `MOTUS_CACHE_DIR`: Override cache directory (XDG: `~/.cache/motus`, Legacy: `{data_dir}/cache`)
- `MOTUS_RUNTIME_DIR`: Override runtime directory (XDG: `/run/user/{uid}/motus`, Legacy: `{data_dir}`)

You can also set these in the config file (specified with `--config`):

```yaml
config_dir: /custom/config
cache_dir: /fast/ssd/cache
runtime_dir: /custom/runtime
```

**Priority order for directory locations**:
- Config directory: `MOTUS_CONFIG_DIR` > `config_dir` in config file > XDG_CONFIG_HOME/motus (or data_dir in legacy mode)
- Cache directory: `--cache-dir` (CLI) > `MOTUS_CACHE_DIR` > `cache_dir` in config file > XDG_CACHE_HOME/motus (or data_dir/cache in legacy mode)
- Runtime directory: `MOTUS_RUNTIME_DIR` > `runtime_dir` in config file > XDG_RUNTIME_DIR/motus (or data_dir in legacy mode)

**XDG Environment Variables** (respected when in XDG mode):

These are typically **already set by your system** (by systemd-logind, PAM, or your login manager). You usually don't need to set them manually. They're shown here for reference:

```bash
# These are usually already set to these values:
XDG_CONFIG_HOME=~/.config              # Motus uses: $XDG_CONFIG_HOME/motus
XDG_DATA_HOME=~/.local/share           # Motus uses: $XDG_DATA_HOME/motus
XDG_CACHE_HOME=~/.cache                # Motus uses: $XDG_CACHE_HOME/motus
XDG_RUNTIME_DIR=/run/user/$UID         # Motus uses: $XDG_RUNTIME_DIR/motus
                                       # ($UID is your numeric user ID, e.g., /run/user/1000)

# If XDG_RUNTIME_DIR is not set, Motus falls back to /tmp/motus-{uid}
```

**Defaults if XDG variables are not set**:
- Config: `~/.config/motus`
- Data: `~/.local/share/motus`
- Cache: `~/.cache/motus`
- Runtime: `/run/user/{uid}/motus` (or `/tmp/motus-{uid}` if XDG_RUNTIME_DIR not set)

**Choosing Between XDG and Legacy Mode**:
- **XDG Mode** (recommended for Linux): Clean separation of config/data/cache/runtime, follows Linux standards
- **Legacy Mode** (`--data-dir`): Everything in one place by default, simple for custom deployments or compatibility

**Relative Paths in Configuration**:

When using `--remote-templates` or `--extra-remotes` (or their corresponding config file or env var options), relative paths are resolved against the config directory:

```bash
# Relative path - resolved as ~/.config/motus/my-templates.conf (in XDG mode)
motus --remote-templates my-templates.conf

# Or in config file (~/.motus/config.yml or specified with --config):
# remote_templates_file: my-templates.conf
# extra_remotes_file: team-remotes.conf

# Absolute paths work as expected
motus --remote-templates /absolute/path/to/templates.conf
```

This makes it easy to keep template files alongside your preferences without specifying full paths.

### Cache Directory Structure

Motus uses a cache directory for temporary files:

```
{cache_dir}/
├── download/          # Temporary ZIP files for downloads (auto-cleaned after download or on shutdown)
├── upload/            # Staging area for uploads (auto-cleaned after job completion)
└── log/               # Temporary job log files (auto-cleaned after storing in database)
```

By default, `cache_dir` is `{data_dir}/cache`. You can customize it with `--cache-dir` or `MOTUS_CACHE_DIR`.

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
cd frontend
npm install      # Install dependencies (if not done)
npm run build    # Build for production (outputs to ../src/motus/static/)
```

For development with hot-reload:

```bash
python dev-vue.py  # Starts Vite dev server on port 3000
```

### Node.js/npm Dependencies

**Important**: Node.js and npm are **build-time dependencies only**, not runtime dependencies.

- **Runtime**: Only Python is required. The built frontend is static files served by Flask.
- **Build-time**: npm is required to build the Vue.js frontend during `pip install`.

### Distributing Pre-built Packages

To distribute Motus without requiring npm at installation time, you can create a pre-built package:

1. **Build the frontend first**:
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

2. **Create a source distribution** (includes built frontend):
   ```bash
   python -m build --sdist
   # Creates: dist/motus-X.Y.Z.tar.gz
   ```

3. **Or create a wheel** (binary distribution):
   ```bash
   python -m build --wheel
   # Creates: dist/motus-X.Y.Z-py3-none-any.whl
   ```

4. **Install the pre-built package**:
   ```bash
   # From wheel (fastest, no build needed):
   pip install dist/motus-X.Y.Z-py3-none-any.whl

   # From source tarball (includes built frontend):
   pip install dist/motus-X.Y.Z.tar.gz
   ```

The `pyproject.toml` configuration ensures that `src/motus/static/` (the built frontend) is included in the package, so end users don't need Node.js or npm installed.

**Note**: If distributing the source tarball, the build hook in `build_frontend.py` will still attempt to build the frontend if `src/motus/static/` doesn't exist. To avoid this, always include the pre-built frontend in your distribution.

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

## Development

### Project Structure

```
motus/
├── src/
│   └── motus/                # Main Python package
│       ├── __init__.py
│       ├── cli.py            # CLI entry point
│       ├── backend/          # Backend package
│       │   ├── api/
│       │   │   ├── files.py      # File operations endpoints
│       │   │   ├── jobs.py       # Job management endpoints
│       │   │   ├── remotes.py    # Remote management endpoints
│       │   │   └── stream.py     # SSE progress streaming
│       │   ├── rclone/
│       │   │   ├── wrapper.py    # rclone command wrapper
│       │   │   ├── job_queue.py  # Background job queue
│       │   │   └── exceptions.py # Custom exceptions
│       │   ├── app.py            # Flask application
│       │   ├── config.py         # Configuration management
│       │   ├── auth.py           # Token authentication
│       │   └── models.py         # SQLite database models
│       └── static/           # Built Vue.js app (generated)
├── frontend/                 # Vue.js source code
│   ├── src/
│   │   ├── components/       # Vue components
│   │   ├── views/            # Main views (Easy/Expert modes)
│   │   ├── store/            # Pinia store
│   │   └── App.vue           # Root component
│   ├── package.json          # npm dependencies
│   └── vite.config.js        # Vite configuration
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
   # Edit files in src/motus/backend/
   # Restart run.py or dev-vue.py to see changes
   python run.py --log-level DEBUG
   ```

2. **Frontend changes**:
   ```bash
   # Start dev server with hot-reload
   python dev-vue.py

   # Edit files in frontend/src/
   # Changes appear immediately in browser
   ```

3. **Build for production**:
   ```bash
   cd frontend
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
cd frontend
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
cd frontend
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

This project is inspired by [Motuz](https://github.com/FredHutch/motuz) (MIT License) and maintains the same MIT license.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Inspired by [Motuz](https://github.com/FredHutch/motuz) by Fred Hutchinson Cancer Research Center
- Uses [rclone](https://rclone.org/) for file operations
- Built with [Vue.js](https://vuejs.org/) and [Flask](https://flask.palletsprojects.com/)

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [rclone documentation](https://rclone.org/docs/)
