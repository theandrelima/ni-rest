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

Since NI-REST is not yet published to PyPI, install it directly from the Git repository using [uv](https://docs.astral.sh/uv/):

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Redis server (optional, for Celery workers)

### Install with uv

```bash
# Install directly from GitHub
uv pip install git+https://github.com/theandrelima/ni-rest.git

# Or install in development mode for local development
git clone https://github.com/theandrelima/ni-rest.git
cd ni-rest
uv sync
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

**Behavior:**
- **With Celery workers available**: Jobs are queued and executed asynchronously
- **Without workers**: Jobs are executed immediately in the web process
- **Auto-detection**: No manual worker management required

#### `ni-rest status`
Check the status of the Django application and any available Celery workers.

```bash
ni-rest status
```

**Output:**
- Django application configuration status
- Celery worker availability (if any)
- Execution mode information

#### `ni-rest check-env`
Validate environment configuration for both development and production modes.

```bash
ni-rest check-env
```

**Output:**
- Environment variable validation
- Development vs production readiness
- Missing configuration warnings

#### `ni-rest manage`
Run Django management commands through the CLI.

```bash
# Database migrations
ni-rest manage migrate

# Create superuser
ni-rest manage createsuperuser

# Django shell
ni-rest manage shell

# Collect static files
ni-rest manage collectstatic

# Any Django command with arguments
ni-rest manage <command> [args...]
```

## Environment Configuration (.env file)

For local development, create a .env file in the project root directory:

### Basic Development .env File

```env
# Django Configuration
DJANGO_ENV=development
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=your-secret-key-here-make-it-long-and-random

# Database Configuration (optional - defaults to SQLite)
# DATABASE_URL=sqlite:///db.sqlite3
# DATABASE_URL=postgresql://user:password@localhost:5432/nirest
# DATABASE_URL=mysql://user:password@localhost:3306/nirest

# Celery Configuration (optional for development)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=django-db
CELERY_TASK_ALWAYS_EAGER=False

# Network Importer Inventory Settings
# Format: NI_INVENTORY_SETTING_TOKEN_<name>
NI_INVENTORY_SETTING_TOKEN_nautobot_dev=your-nautobot-token-here
NI_INVENTORY_SETTING_TOKEN_netbox_lab=your-netbox-token-here

# Network Importer Network Credentials  
# Format: NI_NET_CREDS_LOGIN_<name> and NI_NET_CREDS_PASSWORD_<name>
NI_NET_CREDS_LOGIN_lab_devices=admin
NI_NET_CREDS_PASSWORD_lab_devices=your-device-password

NI_NET_CREDS_LOGIN_prod_routers=netadmin
NI_NET_CREDS_PASSWORD_prod_routers=your-router-password
```

### Production Environment Variables

For production deployment, set these environment variables (not in .env file):

```env
# Required for Production
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=very-long-random-secret-key-for-production

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/nirest
# Or for MySQL: DATABASE_URL=mysql://user:pass@localhost:3306/nirest

# Celery Configuration
CELERY_BROKER_URL=redis://redis-server:6379/0
CELERY_RESULT_BACKEND=django-db
CELERY_WORKER_CONCURRENCY=8

# Network Importer Credentials (same format as development)
NI_INVENTORY_SETTING_TOKEN_production_nautobot=prod-token
NI_NET_CREDS_LOGIN_production=produser
NI_NET_CREDS_PASSWORD_production=prodpass
```

### Database Configuration Options

NI-REST supports multiple database backends through the `DATABASE_URL` environment variable:

#### SQLite (Default - Development)
```env
# Default if no DATABASE_URL is set
DATABASE_URL=sqlite:///db.sqlite3

# Or absolute path
DATABASE_URL=sqlite:////path/to/your/db.sqlite3
```

#### PostgreSQL (Recommended for Production)
```env
DATABASE_URL=postgresql://username:password@hostname:port/database_name

# Examples:
DATABASE_URL=postgresql://nirest:mypassword@localhost:5432/nirest_db
DATABASE_URL=postgresql://user@localhost/nirest  # No password, default port
```

#### MySQL/MariaDB
```env
DATABASE_URL=mysql://username:password@hostname:port/database_name

# Examples:
DATABASE_URL=mysql://nirest:mypassword@localhost:3306/nirest_db
DATABASE_URL=mysql://user@localhost/nirest  # No password, default port
```

### Environment Variable Naming Conventions

#### Database Configuration
- `DATABASE_URL`: Complete database connection string (optional, defaults to SQLite)

#### Inventory Settings Tokens
```env
NI_INVENTORY_SETTING_TOKEN_<setting_name>=<token_value>
```
- `<setting_name>`: Must match the `name` field in `NetworkImporterInventorySettings` model
- `<token_value>`: API token for the inventory system

#### Network Credentials
```env
NI_NET_CREDS_LOGIN_<cred_name>=<username>
NI_NET_CREDS_PASSWORD_<cred_name>=<password>
```
- `<cred_name>`: Must match the `name` field in `NetworkImporterNetCreds` model
- Both LOGIN and PASSWORD variables must be set for each credential set

### Example Workflow

1. **Development Setup:**
   ```bash
   # Create .env file with development settings
   echo "DJANGO_ENV=development" > .env
   echo "DJANGO_DEBUG=True" >> .env
   echo "DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" >> .env
   
   # Start development server
   ni-rest start --dev
   ```

2. **With Optional Workers:**
   ```bash
   # Terminal 1: Start web server
   ni-rest start --dev
   
   # Terminal 2: Start workers (optional)
   celery -A ni_rest worker --loglevel=info
   ```

3. **Production Deployment:**
   ```bash
   # Set environment variables in your deployment system
   export DJANGO_ENV=production
   export DJANGO_SECRET_KEY=your-production-secret
   export DATABASE_URL=postgresql://user:pass@localhost:5432/nirest
   
   # Start application
   ni-rest start --host 0.0.0.0 --port 80
   ```

## API Usage

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

## Notes

- **Development mode** automatically loads the .env file
- **Production mode** requires environment variables to be set by the deployment system
- **Celery workers are optional** - the application works with or without them
- **Worker detection is automatic** - no manual configuration needed
- **Redis is recommended** for Celery broker but not required for basic functionality
- **SQLite is the default database** - perfect for development and simple deployments
- **PostgreSQL is recommended for production** - set via `DATABASE_URL` environment variable

## License

Apache-2.0
