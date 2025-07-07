# Installation Guide

### Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
   - [From PyPI (Recommended)](#from-pypi-recommended)
   - [From Source (For Development)](#from-source-for-development)
3. [Verifying the Installation](#verifying-the-installation)

---

## Prerequisites

-   **Python**: 3.11 or higher.
-   **Database**:
    -   For development, no external database is needed. NI-REST will automatically create a `db.sqlite3` file.
    -   For production, a running **PostgreSQL** or **MySQL** server is highly recommended.
-   **Message Broker (Optional)**: A running **Redis** server is required if you want to use asynchronous task execution with Celery.

## Installation Methods

### From PyPI (Recommended)

The easiest way to install NI-REST is from the Python Package Index (PyPI) using `pip` or any other modern package manager.

```bash
# Using pip
pip install network-importer-rest

# Using uv
uv pip install network-importer-rest

# Using poetry
potry add network-importer-rest
```

This will install the `ni-rest` CLI tool and all required Python dependencies.

### From Source (For Development)

If you plan to contribute to NI-REST or need the latest unreleased changes, you can install it from the source repository.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/theandrelima/ni-rest.git
    cd ni-rest
    ```

2.  **Create a virtual environment and install dependencies.** This project uses `uv` for fast dependency management.
    ```bash
    # Install uv if you don't have it
    pip install uv

    # Create a virtual environment and install all dependencies
    uv sync
    ```

3.  **Activate the virtual environment:**
    ```bash
    # On macOS/Linux
    source .venv/bin/activate

    # On Windows
    .venv\Scripts\activate
    ```

## Verifying the Installation

After installation, the `ni-rest` command-line tool should be available in your shell. You can verify this by checking its help message.

```bash
ni-rest --help
```

You should see a list of available commands like `start`, `stop`, `status`, and `manage`. This confirms that the installation was successful.

---
<div align="center">
<a href="./00-introduction.md">&larr; Previous: Introduction</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="../README.md">Home</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="./02-quickstart.md">Next: Quickstart Guide &rarr;</a>
</div>