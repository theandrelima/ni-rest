# CLI Usage Guide

### Table of Contents
1. [Introduction](#introduction)
2. [Core Commands](#core-commands)
   - [`ni-rest start`](#ni-rest-start)
   - [`ni-rest stop`](#ni-rest-stop)
   - [`ni-rest status`](#ni-rest-status)
3. [Utility Commands](#utility-commands)
   - [`ni-rest check-env`](#ni-rest-check-env)
   - [`ni-rest manage`](#ni-rest-manage)

---

## Introduction

The `ni-rest` command-line interface is the primary tool for managing the application lifecycle. It's a wrapper around standard Django and server commands, designed to be simple and intuitive.

## Core Commands

These commands are used to start, stop, and check the status of the NI-REST server.

### `ni-rest start`

Starts the web server. This is the most important command.

**Usage:**
```bash
ni-rest start [OPTIONS]
```

**Key Options:**
-   `--dev`: Runs the server in **development mode**. This enables debug features and, most importantly, loads configuration from a `.env` file.
-   `--host <ip>`: The IP address for the server to listen on. Defaults to `127.0.0.1`. Use `0.0.0.0` to make it accessible from other machines.
-   `--port <number>`: The port to listen on. Defaults to `8000`.

**Examples:**
```bash
# Start for local development
ni-rest start --dev

# Start for production, accessible on the network
ni-rest start --host 0.0.0.0 --port 8080
```

### `ni-rest stop`

Stops any running NI-REST server processes. It intelligently finds the processes started by `ni-rest start` and terminates them gracefully.

**Usage:**
```bash
ni-rest stop
```

### `ni-rest status`

Provides a quick status check of the application. It reports:
-   Whether the server process is running.
-   The validity of the Django application configuration.
-   The availability of a message broker and Celery workers.

**Usage:**
```bash
ni-rest status
```

## Utility Commands

These commands help with setup, configuration, and maintenance.

### `ni-rest check-env`

Validates your environment configuration for both development and production modes without starting the server. This is extremely useful for debugging configuration issues.

It checks for:
-   The presence of `DJANGO_SECRET_KEY`.
-   A valid database configuration.
-   The existence of `network-importer` credential variables.

**Usage:**
```bash
ni-rest check-env
```

### `ni-rest manage`

A direct pass-through to Django's `manage.py` script. This allows you to run any standard Django management command.

**Usage:**
```bash
ni-rest manage <django-command> [arguments...]
```

**Common Examples:**
```bash
# Apply database migrations
ni-rest manage migrate

# Create an admin user
ni-rest manage createsuperuser

# Open a Django shell for debugging
ni-rest manage shell

# Collect static files for production
ni-rest manage collectstatic
```

---
<div align="center">
<a href="./03-configuration.md">&larr; Previous: Configuration</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="../README.md">Home</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="./05-api-usage.md">Next: API Usage &rarr;</a>
</div>