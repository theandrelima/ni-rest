# Configuration Reference

### Table of Contents
1. [Configuration Methods](#configuration-methods)
   - [Development Mode (`.env`)](#development-mode-env)
   - [Production Mode (Environment Variables)](#production-mode-environment-variables)
2. [Application Settings](#application-settings)
   - [`DJANGO_SECRET_KEY`](#django_secret_key)
   - [`DJANGO_DEBUG`](#django_debug)
3. [Database Configuration](#database-configuration)
   - [`DATABASE_URL`](#database_url)
   - [`DATABASE_PATH`](#database_path)
4. [Celery (Async Worker) Configuration](#celery-async-worker-configuration)
   - [`CELERY_BROKER_URL`](#celery_broker_url)
5. [Network Importer Credentials](#network-importer-credentials)
   - [Inventory Tokens](#inventory-tokens)
   - [Device Credentials](#device-credentials)

---

## Configuration Methods

NI-REST is configured entirely through environment variables, following modern application design principles.

### Development Mode (`.env`)

When you run `ni-rest start --dev`, the application will automatically load environment variables from a `.env` file in your project's root directory. This is the recommended method for local development.

**Example `.env` file:**
```env
# This file is only loaded in development mode
DJANGO_SECRET_KEY=your-dev-secret-key
DATABASE_URL=sqlite:///db.sqlite3
CELERY_BROKER_URL=redis://localhost:6379/0
NI_INVENTORY_SETTING_TOKEN_nautobot_dev=aaaabbbbccccddddeeeeffff
```

### Production Mode (Environment Variables)

When you run `ni-rest start` (without `--dev`), the application **completely ignores** any `.env` file. All configuration **must** be provided as actual environment variables. This is a security best practice that prevents development settings from leaking into production.

```bash
# Example of setting environment variables for production
export DJANGO_SECRET_KEY="your-production-secret-key"
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
export CELERY_BROKER_URL="redis://redis-prod:6379/0"
export NI_INVENTORY_SETTING_TOKEN_nautobot_prod="xxxxxyyyyyzzzzzaaaabbbb"

# Now start the server
ni-rest start
```

## Application Settings

#### `DJANGO_SECRET_KEY`
-   **Required in Production**
-   A long, unique, and unpredictable value used for cryptographic signing.
-   If not set in development, a temporary, insecure key will be used.

#### `DJANGO_DEBUG`
-   Controls Django's debug mode.
-   Set to `True` for development to get detailed error pages.
-   **Must be `False` in production.**
-   The `ni-rest start --dev` command automatically sets this to `True`.

## Database Configuration

NI-REST uses the `dj-database-url` library for flexible database configuration.

#### `DATABASE_URL`
-   **The primary method for configuring the database.**
-   A single URL string that defines the connection.
-   **If this variable is not set, NI-REST defaults to a local SQLite database.**

**Examples:**
```env
# PostgreSQL (Recommended for Production)
DATABASE_URL=postgresql://user:password@host:port/dbname

# MySQL / MariaDB
DATABASE_URL=mysql://user:password@host:port/dbname

# SQLite
DATABASE_URL=sqlite:///path/to/your/db.sqlite3
```

#### `DATABASE_PATH`
-   A convenience variable for specifying a **SQLite database path only**.
-   Use this if you don't want to write a full `sqlite://` URL.
-   This is overridden by `DATABASE_URL` if both are set.

**Default SQLite Behavior (if no database variables are set):**
-   **In Development:** Creates `db.sqlite3` in the current directory.
-   **In Production:** Creates `db.sqlite3` in a system-appropriate data directory (e.g., `~/.local/share/ni-rest/`).

## Celery (Async Worker) Configuration

#### `CELERY_BROKER_URL`
-   Defines the connection to your message broker (e.g., Redis).
-   If not set, defaults to `redis://localhost:6379/0`.
-   If NI-REST cannot connect to this broker, it will fall back to synchronous execution mode.

## Network Importer Credentials

Credentials for `network-importer` are also loaded from environment variables.

### Inventory Tokens
These are API tokens for your Source of Truth (e.g., Nautobot, NetBox).
-   **Format**: `NI_INVENTORY_SETTING_TOKEN_<setting_name>`
-   The `<setting_name>` part is what you will use in your API calls.

**Example:**
```env
# Token for a Nautobot instance named 'nautobot_prod'
NI_INVENTORY_SETTING_TOKEN_nautobot_prod=your-nautobot-api-token
```

### Device Credentials
These are the login credentials for connecting to network devices.
-   **Format**: `NI_NET_CREDS_LOGIN_<cred_name>` and `NI_NET_CREDS_PASSWORD_<cred_name>`
-   The `<cred_name>` part is what you will use in your API calls.

**Example:**
```env
# Credentials for a set of lab devices named 'cisco_lab'
NI_NET_CREDS_LOGIN_cisco_lab=admin
NI_NET_CREDS_PASSWORD_cisco_lab=a_secure_password
```

---
<div align="center">
<a href="./02-quickstart.md">&larr; Previous: Quickstart Guide</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="../README.md">Home</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="./04-cli-usage.md">Next: CLI Usage &rarr;</a>
</div>