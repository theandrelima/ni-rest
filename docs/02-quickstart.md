# Quickstart Guide

### Table of Contents
1. [Goal](#goal)
2. [Step 1: Configure Your Environment](#step-1-configure-your-environment)
3. [Step 2: Initialize the Database](#step-2-initialize-the-database)
4. [Step 3: Start the Server](#step-3-start-the-server)
5. [Step 4: Get an API Token](#step-4-get-an-api-token)
6. [Step 5: Make Your First API Call](#step-5-make-your-first-api-call)

---

## Goal

This guide will walk you through setting up a local NI-REST server for development in under 5 minutes.

## Step 1: Configure Your Environment

NI-REST uses a `.env` file for easy local development. Create a file named `.env` in the root of your project.

1.  **Create the `.env` file:**
    ```bash
    touch .env
    ```

2.  **Add a `DJANGO_SECRET_KEY`**. At a minimal, this is the only variable required to start the server. You can generate one easily:
    ```bash
    # This command generates a key and appends it to your .env file
    python -c 'from django.core.management.utils import get_random_secret_key; print(f"DJANGO_SECRET_KEY={get_random_secret_key()}")' >> .env
    ```

Your `.env` file will now contain something like this:
```env
DJANGO_SECRET_KEY=a_very_long_and_random_string_generated_here
```
*For this quickstart, we will use the default SQLite database, so no `DATABASE_URL` is needed.*

## Step 2: Initialize the Database

The `ni-rest` CLI wraps Django's `manage.py` script, making it easy to run database migrations and create users.

1.  **Apply Database Migrations:** This creates the necessary tables in your SQLite database.
    ```bash
    ni-rest manage migrate
    ```

2.  **Create a Superuser:** This user will have access to the Django admin UI and can be used to generate API tokens.
    ```bash
    ni-rest manage createsuperuser
    ```
    Follow the prompts to set a username, email, and password.

## Step 3: Start the Server

Use the `ni-rest start` command with the `--dev` flag. This tells the server to run in development mode, which enables debugging and automatically loads your `.env` file.

```bash
ni-rest start --dev
```

You will see output indicating the server has started. By default, in development mode, the server runs at `http://127.0.0.1:8000`.

- **Server URL:** `http://<host>:<port>/`
- **Admin UI:** `http://<host>:<port>/admin/`
- **API Docs:** `http://<host>:<port>/api/docs/`

## Step 4: Get an API Token

To interact with the API, you need an authentication token.

1.  Navigate to the **Admin UI** at `http://<host>:<port>/admin/` (e.g., `http://127.0.0.1:8000/admin/`).
2.  Log in with the superuser credentials you created in Step 2.
3.  On the admin dashboard, find the "AUTHTOKEN" section and click "+ Add" next to "Tokens".
4.  Select your user from the dropdown menu and click "SAVE".
5.  The admin will display the generated token. **Copy this token now**.

## Step 5: Make Your First API Call

You can now use this token to make authenticated requests. Let's check the API root endpoint using `curl`. Since we started the server in dev mode without custom options, we'll use the default address.

Replace `your-api-token-here` with the token you just copied.

```bash
curl -X GET http://127.0.0.1:8000/api/ \
  -H "Authorization: Token your-api-token-here"
```

If successful, you will receive a JSON response listing the available API endpoints and the current worker status. Congratulations, your NI-REST server is fully operational!

---
<div align="center">
<a href="./01-installation.md">&larr; Previous: Installation</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="../README.md">Home</a>
&nbsp;&nbsp;|&nbsp;&nbsp;
<a href="./03-configuration.md">Next: Configuration &rarr;</a>
</div>