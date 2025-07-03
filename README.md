# NI-REST

A REST API wrapper around [network-importer](https://github.com/networktocode/network-importer) that provides HTTP endpoints for executing network imports with job tracking and logging.

## What is NI-REST?

NI-REST transforms the network-importer CLI tool into a web service, allowing you to:

- **Execute network imports via HTTP API** instead of command line
- **Track job status** with real-time progress monitoring
- **View detailed logs** for each import operation
- **Queue jobs** for asynchronous execution (optional Celery workers)
- **Manage credentials** through Django models and environment variables
- **Scale horizontally** by adding worker processes as needed

The service automatically detects if Celery workers are available:
- **With workers**: Jobs are queued and executed asynchronously for better performance
- **Without workers**: Jobs execute immediately in the web process for simplicity

## Installation

### Prerequisites

- Python 3.11 or higher
- Redis server (optional, for Celery workers)

### Install from PyPI

The package is available on PyPI and can be installed with your preferred Python package manager:

```bash
# Install with pip
pip install network-importer-rest

# Or install with poetry
poetry add network-importer-rest

# Or install with uv
uv pip install network-importer-rest
```

### Install from Source

This project is managed with [uv](https://docs.astral.sh/uv/) for dependency management and packaging.

#### Quick Install from GitHub

```bash
# Install directly from GitHub with pip
pip install git+https://github.com/theandrelima/ni-rest.git

# Or with uv
uv pip install git+https://github.com/theandrelima/ni-rest.git
```

#### Development Setup with uv

For local development and contributing:

```bash
# Clone the repository
git clone https://github.com/theandrelima/ni-rest.git
cd ni-rest

# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv

# Create virtual environment and install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Verify installation
ni-rest --help
```

### Verify Installation

```bash
# Check that the CLI is available
ni-rest --help

# Validate environment
ni-rest check-env
```

## Quick Start

1. **Set up environment variables** (see Environment Configuration below)

2. **Initialize the database:**
   ```bash
   ni-rest manage migrate
   ni-rest manage createsuperuser
   ```

3. **Start the server:**
   ```bash
   # Development mode
   ni-rest start --dev
   
   # Production mode
   ni-rest start
   ```

4. **Access the application:**
   - API: http://localhost:8000/api/
   - Admin: http://localhost:8000/admin/
   - API Docs: http://localhost:8000/api/docs/

## NI-REST CLI Commands

The `ni-rest` CLI provides simple commands to manage the Django application with automatic Celery worker detection.

### Available Commands

#### `ni-rest start`
Start the NI-REST API server with automatic worker detection.

```bash
# Development mode (loads .env file, enables debug)
ni-rest start --dev

# Production mode  
ni-rest start

# Custom host and port
ni-rest start --host 0.0.0.0 --port 8080

# Development with custom port
ni-rest start --dev --port 3000
```

**Options:**
- `--dev`: Enable development mode (loads .env file, enables Django debug)
- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 8000)

**Environment Behavior:**
- **Development mode (`--dev`)**: Automatically loads `.env` file if present
- **Production mode (default)**: Ignores `.env` file completely - environment variables must be set externally
- **CLI is authoritative**: CLI flags override any existing environment variables

#### `ni-rest status`
Check the status of the Django application and any available Celery workers.

```bash
ni-rest status
```

#### `ni-rest check-env`
Validate environment configuration for both development and production modes.

```bash
ni-rest check-env
```

#### `ni-rest manage`
Run Django management commands through the CLI.

```bash
# Database migrations
ni-rest manage migrate

# Create superuser
ni-rest manage createsuperuser

# Django shell
ni-rest manage shell

# Any Django command with arguments
ni-rest manage <command> [args...]
```

## Environment Configuration

NI-REST uses different environment configuration strategies depending on how it's started:

### 🔧 Development Mode: `.env` File Support

When using `ni-rest start --dev`, the application automatically loads a `.env` file from the project root:

```env
# .env file for local development only
# This file is IGNORED in production mode

# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here-make-it-long-and-random

# Database Configuration (optional - defaults to SQLite)
DATABASE_URL=sqlite:///db.sqlite3
# DATABASE_URL=postgresql://user:password@localhost:5432/nirest

# Celery Configuration (optional for development)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=django-db

# Network Importer Inventory Settings
NI_INVENTORY_SETTING_TOKEN_nautobot_dev=your-nautobot-token-here
NI_INVENTORY_SETTING_TOKEN_netbox_lab=your-netbox-token-here

# Network Importer Network Credentials  
NI_NET_CREDS_LOGIN_lab_devices=admin
NI_NET_CREDS_PASSWORD_lab_devices=your-device-password
```

### 🚀 Production Mode: Environment Variables Only

When using `ni-rest start` (production mode), `.env` files are **completely ignored**. All configuration must come from environment variables. Make sure whatever pipeline engine you use takes care of that.

### Database Configuration Options

#### SQLite (Default - Development)
```env
DATABASE_URL=sqlite:///db.sqlite3
```

#### PostgreSQL (Recommended for Production)
```env
DATABASE_URL=postgresql://username:password@hostname:port/database_name
```

#### MySQL/MariaDB
```env
DATABASE_URL=mysql://username:password@hostname:port/database_name
```

### Environment Variable Naming Conventions

#### Inventory Settings Tokens
```env
NI_INVENTORY_SETTING_TOKEN_<setting_name>=<token_value>
```

#### Network Credentials
```env
NI_NET_CREDS_LOGIN_<cred_name>=<username>
NI_NET_CREDS_PASSWORD_<cred_name>=<password>
```

### Example Workflows

#### 1. Local Development
```bash
# Create .env file with development settings
cat > .env << EOF
DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
NI_INVENTORY_SETTING_TOKEN_nautobot_dev=dev-token-here
NI_NET_CREDS_LOGIN_lab_devices=admin
NI_NET_CREDS_PASSWORD_lab_devices=admin123
EOF

# Start development server (automatically loads .env)
ni-rest start --dev
```

#### 2. Production Deployment
```bash
# Set environment variables externally (never use .env in production)
export DJANGO_SECRET_KEY="your-super-secure-production-secret-key"
export DATABASE_URL="postgresql://nirest:secure_password@db.company.com:5432/nirest"
export NI_INVENTORY_SETTING_TOKEN_production="your-production-nautobot-token"

# Start application (ignores any .env file)
ni-rest start --host 0.0.0.0 --port 8000
```

## API Usage

### Interactive Documentation

Visit the interactive API documentation:
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/

### Execute Network Import

```bash
# Apply mode (make changes)
curl -X POST http://localhost:8000/api/execute/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-api-token" \
  -d '{
    "site": "lab01",
    "mode": "apply",
    "settings": {
      "inventory": {"name": "nautobot_dev"},
      "network": {"credentials_name": "lab_devices"}
    }
  }'

# Check mode (dry run)
curl -X POST http://localhost:8000/api/execute/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-api-token" \
  -d '{
    "site": "lab01", 
    "mode": "check",
    "settings": {
      "inventory": {"name": "nautobot_dev"},
      "network": {"credentials_name": "lab_devices"}
    }
  }'
```

### Monitor Job Status

```bash
# List all jobs
curl -H "Authorization: Token your-api-token" \
  http://localhost:8000/api/jobs/

# Get specific job details
curl -H "Authorization: Token your-api-token" \
  http://localhost:8000/api/jobs/{job-id}/

# Get job logs
curl -H "Authorization: Token your-api-token" \
  http://localhost:8000/api/jobs/{job-id}/logs/
```

## Key Features Summary

- **🔧 Developer-friendly**: Development mode with automatic `.env` loading
- **🚀 Production-ready**: Production mode ignores `.env` files for security
- **⚡ Flexible execution**: Works with or without Celery workers
- **📚 Interactive docs**: Swagger UI and ReDoc for API exploration
- **🎯 Container-ready**: Designed for Docker and Kubernetes deployments
- **🔄 Auto-detection**: Automatically detects worker availability
- **📊 Job tracking**: Comprehensive status monitoring and logging

## License

Apache-2.0