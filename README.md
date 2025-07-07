# NI-REST

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**NI-REST** transforms the `network-importer` library into a robust, scalable REST API service. It allows you to run network import and automation jobs via HTTP, track their progress in real-time, and manage all configuration through a clean web interface and environment variables.

The service features a powerful CLI for easy management and automatically adapts its execution strategy, running jobs asynchronously with Celery workers when available, or synchronously for simpler setups.

---

## 📚 Full Documentation

This README provides a brief overview. For detailed guides on installation, configuration, and usage, please see the **[Full Documentation](./docs/00-introduction.md)**.

## Quick Start

For those who want to get started immediately:

1.  **Install the package:**
    ```bash
    pip install network-importer-rest
    ```

2.  **Configure your environment.** Create a `.env` file in your project root:
    ```env
    # .env
    DJANGO_SECRET_KEY='a-long-random-string-here'
    # For a simple start, NI-REST will create a local SQLite database automatically.
    ```

3.  **Initialize and start the server:**
    ```bash
    # Initialize the database
    ni-rest manage migrate
    ni-rest manage createsuperuser

    # Start the server in development mode
    ni-rest start --dev
    ```

4.  **Access the service:**
    -   **API Docs:** `http://<host>:<port>/api/docs/`
    -   **Admin UI:** `http://<host>:<port>/admin/`

    *(Note: In development mode, this defaults to `http://127.0.0.1:8000`)*
