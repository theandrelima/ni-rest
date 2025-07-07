# Introduction to NI-REST

### Table of Contents
1. [What is NI-REST?](#what-is-ni-rest)
2. [Key Features](#key-features)
3. [How It Works](#how-it-works)
   - [Technology Stack](#technology-stack)
   - [Execution Modes](#execution-modes)
4. [Core Concepts](#core-concepts)
   - [Jobs](#jobs)
   - [Configuration](#configuration)

---

## What is NI-REST?

**NI-REST** is a web service that wraps the powerful `network-importer` library, exposing its functionality through a modern REST API. It bridges the gap between command-line network automation and scalable, API-driven infrastructure.

Instead of running `network-importer` manually from a terminal, you can trigger network discovery, configuration checks, and deployments by sending simple HTTP requests. This makes it easy to integrate network automation into CI/CD pipelines, custom web portals, or any other application that can speak HTTP.

## Key Features

-   **API-Driven Automation**: Execute `network-importer` tasks via a clean REST API instead of the command line.
-   **Real-Time Job Tracking**: Every operation is a "Job" stored in the database. Monitor its status, view logs, and see results through dedicated API endpoints.
-   **Dual Execution Modes**: Automatically adapts to run jobs asynchronously with Celery or synchronously for simpler setups.
-   **Flexible Configuration**: Configure the entire service via standard environment variables.
-   **Powerful CLI**: A user-friendly command-line interface (`ni-rest`) simplifies server management.
-   **Built-in Admin UI**: Use the standard Django admin interface to view job history and manage settings.

## How It Works

### Technology Stack
NI-REST is built on a foundation of robust and widely-used Python technologies:
-   **Django & Django REST Framework**: Provide the core web framework, database ORM, and API structure.
-   **Celery**: A distributed task queue used for running jobs asynchronously.
-   **Typer**: A modern library for building the user-friendly `ni-rest` command-line interface.
-   **dj-database-url**: A utility for parsing database connection URLs, enabling flexible database configuration.

### Execution Modes
NI-REST intelligently adapts to its environment when a job is executed.

1.  **Async Mode (Production Recommended)**: If a Celery message broker (like Redis) is configured and workers are running, the API immediately queues the job and returns an HTTP `202 Accepted` response. The job runs in the background, ensuring the API remains responsive.

2.  **Immediate Mode (Simple/Development)**: If no Celery workers are detected, NI-REST executes the job synchronously within the same web process. The HTTP response is returned only after the job is complete. This allows for a simple, zero-dependency setup for local development or small-scale use.

## Core Concepts

### Jobs

The central element in NI-REST is the **Job**. A Job represents a single execution of `network-importer`. When you make a request to the `/api/execute/` endpoint, a `NetworkImporterJob` record is created in the database. This record tracks everything about the operation:
-   The user who initiated it.
-   The target site and execution mode (`check` or `apply`).
-   The current status (`queued`, `running`, `completed`, `failed`).
-   Timestamps for creation, start, and completion.
-   A detailed, timestamped log of all output from `network-importer`.

### Configuration

NI-REST follows the "12-Factor App" methodology, favoring environment variables for all configuration. This makes it easy to deploy in containers and modern cloud environments. For local development, it also supports a `.env` file for convenience.

---
<div align="right">
<a href="./01-installation.md">Next: Installation &rarr;</a>
</div>