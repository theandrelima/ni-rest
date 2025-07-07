# API Usage Guide

### Table of Contents
1. [Authentication](#authentication)
2. [Interactive API Documentation](#interactive-api-documentation)
3. [Core Workflow](#core-workflow)
   - [Endpoint: `POST /api/execute/`](#endpoint-post-apiexecute)
   - [Endpoint: `GET /api/jobs/{job_id}/`](#endpoint-get-apijobsjob_id)
   - [Endpoint: `GET /api/jobs/{job_id}/logs/`](#endpoint-get-apijobsjob_idlogs)
4. [Listing and Filtering](#listing-and-filtering)
   - [Endpoint: `GET /api/jobs/`](#endpoint-get-apijobs)

---

## Authentication

All API endpoints require token-based authentication. You must include an `Authorization` header with your API token in every request.

**Header Format:**
```
Authorization: Token your-api-token-here
```

See the [Quickstart Guide](./02-quickstart.md#step-4-get-an-api-token) for instructions on how to generate a token.

## Interactive API Documentation

The easiest way to explore the API is through the built-in interactive documentation, which provides a full OpenAPI (Swagger) specification.

Once the server is running, navigate to: **`http://<host>:<port>/api/docs/`**

*(Note: In development mode, this defaults to `http://127.0.0.1:8000/api/docs/`)*

From this UI, you can:
-   View all available endpoints, their parameters, and expected responses.
-   Authorize your session by clicking the "Authorize" button and entering `Token your-api-token-here`.
-   Execute API calls directly from your browser.

## Core Workflow

A typical interaction with NI-REST involves three steps: executing a job, checking its status, and viewing its logs.

### Endpoint: `POST /api/execute/`

This is the main endpoint used to start a new `network-importer` job.

**Request Body:**

```json
{
  "site": "your_site_code",
  "mode": "check",
  "settings": {
    "inventory": {
      "name": "your_inventory_setting_name"
    },
    "network": {
      "credentials_name": "your_credential_name"
    }
  }
}
```

-   `site`: The site code to be processed by `network-importer`.
-   `mode`: Can be `check` (for a dry run) or `apply` (to make changes).
-   `settings.inventory.name`: The name of the inventory setting (e.g., `nautobot_prod`), which corresponds to the `NI_INVENTORY_SETTING_TOKEN_<name>` environment variable.
-   `settings.network.credentials_name`: The name of the device credentials (e.g., `cisco_lab`), which corresponds to the `NI_NET_CREDS_*_<name>` environment variables.

**Response:**
-   If workers are available, you'll get an HTTP `202 Accepted` with the job ID.
-   If no workers are available, the job will run immediately, and you'll get an HTTP `200 OK` with the final job result.

### Endpoint: `GET /api/jobs/{job_id}/`

Retrieves the detailed status and metadata for a specific job.

**Example Response:**
```json
{
    "id": "a1b2c3d4-e5f6-...",
    "site_code": "your_site_code",
    "mode": "check",
    "status": "completed",
    "success": true,
    "has_errors": false,
    "created_at": "2025-07-07T12:00:00Z",
    "started_at": "2025-07-07T12:00:01Z",
    "completed_at": "2025-07-07T12:00:30Z",
    "celery_task_id": "f6e5d4c3-b2a1-...",
    "logs_count": 50,
    "error_logs_count": 0
}
```

### Endpoint: `GET /api/jobs/{job_id}/logs/`

Retrieves the detailed, line-by-line logs for a specific job.

## Listing and Filtering

### Endpoint: `GET /api/jobs/`

Lists all jobs stored in the database. This endpoint supports filtering and ordering.

**Query Parameters:**
-   `status`: Filter by job status (e.g., `?status=failed`).
-   `mode`: Filter by execution mode (e.g., `?mode=apply`).
-   `site_code`: Filter by site code.
-   `ordering`: Order the results (e.g., `?ordering=-created_at`).

**Example:**
To find the most recent failed jobs:
```bash
curl -X GET "http://<host>:<port>/api/jobs/?status=failed&ordering=-created_at" \
  -H "Authorization: Token your-api-token-here"
```

---
<div align="center">
<a href="./04-cli-usage.md">&larr; Previous: CLI Usage</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="../README.md">Home</a>