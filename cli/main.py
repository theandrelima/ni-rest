#!/usr/bin/env python3
"""
NI-REST CLI - Command line interface for Network Importer REST API

This CLI starts the Django server which automatically detects worker availability.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="ni-rest",
    help="Network Importer REST API - Auto-detects worker availability",
    add_completion=False
)

console = Console()

def get_project_root() -> Path:
    """Find the project root directory containing manage.py"""
    current = Path(__file__).resolve()
    
    # Look for manage.py in current directory and parents
    for path in [current.parent] + list(current.parents):
        manage_py = path / "manage.py"
        if manage_py.exists():
            return path
    
    # Fallback: assume we're in cli package, go up one level
    return current.parent.parent

def validate_environment(dev_mode: bool = False) -> bool:
    """
    Validate that required environment variables are set.
    
    Args:
        dev_mode: If True, allows missing env vars (development mode)
        
    Returns:
        True if environment is valid
    """
    console.print("\n🔍 Validating environment...", style="yellow")
    
    # Required for Django
    django_secret = os.getenv('DJANGO_SECRET_KEY')
    if not django_secret and not dev_mode:
        console.print("❌ DJANGO_SECRET_KEY is required in production mode", style="red")
        return False
    elif not django_secret and dev_mode:
        console.print("⚠️  DJANGO_SECRET_KEY not set - using development fallback", style="yellow")
    else:
        console.print("✅ DJANGO_SECRET_KEY configured", style="green")
    
    # Check database configuration
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        if database_url.startswith('sqlite://'):
            console.print(f"💾 Database: SQLite ({database_url})", style="blue")
        elif database_url.startswith('postgresql://'):
            console.print(f"💾 Database: PostgreSQL", style="blue")
        elif database_url.startswith('mysql://'):
            console.print(f"💾 Database: MySQL", style="blue")
        else:
            console.print(f"💾 Database: Custom ({database_url.split('://')[0]})", style="blue")
    else:
        console.print("💾 Database: SQLite (default)", style="blue")
    
    # Check Celery broker
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    console.print(f"📡 Celery broker: {broker_url}", style="blue")
    
    # Check for any NI credential environment variables
    ni_vars = [key for key in os.environ.keys() if key.startswith(('NI_INVENTORY_SETTING_', 'NI_NET_CREDS_'))]
    
    if ni_vars:
        console.print(f"✅ Found {len(ni_vars)} NI credential environment variables", style="green")
        if dev_mode:
            console.print("📋 Development mode - showing configured credentials:", style="blue")
            for var in sorted(ni_vars):
                # Don't show actual values, just confirm they exist
                console.print(f"   • {var} = {'*' * 8}", style="dim")
    else:
        if dev_mode:
            console.print("⚠️  No NI credential environment variables found", style="yellow")
            console.print("   This is OK for development - you can set dummy values", style="dim")
        else:
            console.print("❌ No NI credential environment variables found", style="red")
            console.print("   Set NI_INVENTORY_SETTING_TOKEN_* and NI_NET_CREDS_* variables", style="dim")
            return False
    
    return True

def set_environment_for_mode(dev_mode: bool) -> None:
    """Set environment variables based on deployment mode - CLI is authoritative"""
    if dev_mode:
        # Development mode - allow .env to be loaded, but CLI overrides
        os.environ['DJANGO_ENV'] = 'development'
        os.environ['DJANGO_DEBUG'] = 'True'
        console.print("🔧 Environment configured for development mode", style="blue")
        console.print("   (CLI overrides any existing DJANGO_ENV/DJANGO_DEBUG)", style="dim")
    else:
        # Production mode - CLI is authoritative, ignore any existing values
        os.environ['DJANGO_ENV'] = 'production' 
        os.environ['DJANGO_DEBUG'] = 'False'
        console.print("🚀 Environment configured for production mode", style="green")
        console.print("   (CLI overrides any existing DJANGO_ENV/DJANGO_DEBUG)", style="dim")
        
        # Warn if .env file exists in production mode
        project_root = get_project_root()
        env_file = project_root / '.env'
        if env_file.exists():
            console.print("⚠️  .env file found but ignored in production mode", style="yellow")

@app.command()
def start(
    dev: bool = typer.Option(
        False,
        "--dev",
        help="Start in development mode (enables debug, uses .env file)"
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind to"
    ),
    port: int = typer.Option(
        8000,
        "--port", 
        help="Port to bind to"
    )
):
    """
    Start the NI-REST API server.
    
    The server automatically detects if Celery workers are available:
    - With workers: Jobs are queued and executed asynchronously
    - Without workers: Jobs are executed immediately in the web process
    
    Examples:
        ni-rest start --dev                    # Development mode
        ni-rest start                          # Production mode  
        ni-rest start --host 0.0.0.0 --port 8080  # Custom host/port
    """
    
    # Show startup banner
    mode_text = "DEVELOPMENT" if dev else "PRODUCTION"
    color = "blue" if dev else "green"
    
    console.print(Panel.fit(
        f"[bold]NI-REST API Server[/bold]\n"
        f"Mode: [bold {color}]{mode_text}[/bold {color}]\n"
        f"Host: {host}:{port}\n"
        f"[green]Auto-detects worker availability[/green]\n"
        f"[dim]Jobs execute async with workers, synchronously without workers[/dim]",
        title="🚀 Starting Server",
        border_style=color
    ))
    
    # Set environment variables
    set_environment_for_mode(dev)
    
    # Validate environment
    if not validate_environment(dev):
        console.print("\n❌ Environment validation failed", style="red")
        console.print("Fix the issues above and try again", style="dim")
        raise typer.Exit(1)
    
    # Get project root
    project_root = get_project_root()
    manage_py = project_root / "manage.py"
    
    if not manage_py.exists():
        console.print(f"❌ manage.py not found in {project_root}", style="red")
        raise typer.Exit(1)
    
    console.print(f"📁 Project root: {project_root}", style="dim")
    
    # Prepare Django command
    cmd = [sys.executable, "manage.py", "runserver", f"{host}:{port}"]
    if not dev:
        cmd.append("--noreload")  # Disable auto-reload in production
    
        # Show final startup info
    console.print(f"\n📡 Server will be available at: http://{host}:{port}/", style="bold")
    console.print(f"👨‍💻 Admin interface: http://{host}:{port}/admin/", style="dim")
    console.print(f"🤖 API endpoints: http://{host}:{port}/api/", style="dim")
    console.print(f"📚 API documentation: http://{host}:{port}/api/docs/", style="dim")
    
    console.print("\n💡 Optional: Start Celery workers for async execution:", style="cyan")
    console.print("   celery -A ni_rest worker --loglevel=info", style="dim")
    console.print("   (Server works with or without workers)", style="dim")
    
    console.print("\n🏁 Starting server...\n", style="bold green")
    
    try:
        # Change to project directory and run command
        subprocess.run(cmd, cwd=project_root, check=True)
    except KeyboardInterrupt:
        console.print("\n\n⏹️  Server stopped by user", style="yellow")
    except subprocess.CalledProcessError as e:
        console.print(f"\n❌ Server failed to start: {e}", style="red")
        raise typer.Exit(1)

@app.command()
def status():
    """Show status of the application and any available workers."""
    
    project_root = get_project_root()
    
    console.print(Panel.fit(
        "[bold]NI-REST Application Status[/bold]",
        title="🚥 Status Check",
        border_style="blue"
    ))
    
    # Check if we can import Django (server is configured)
    try:
        cmd = [sys.executable, "manage.py", "check"]
        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
        if result.returncode == 0:
            console.print("✅ Django application configuration is valid", style="green")
        else:
            console.print("❌ Django application has configuration issues", style="red")
            if result.stderr:
                console.print(f"Error details: {result.stderr}", style="dim")
            if result.stdout:
                console.print(f"Output: {result.stdout}", style="dim")
    except Exception as e:
        console.print(f"❌ Error checking Django: {e}", style="red")
    
    # Check worker status (optional)
    try:
        cmd = ["celery", "-A", "ni_rest", "inspect", "active"]
        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and "ERROR" not in result.stderr:
            console.print("✅ Celery workers are available (async execution)", style="green")
            if result.stdout.strip():
                console.print("Worker details:", style="dim")
                console.print(result.stdout, style="dim")
        else:
            console.print("ℹ️  No dedicated Celery workers (immediate execution mode)", style="blue")
    except subprocess.TimeoutExpired:
        console.print("ℹ️  No Celery broker connection (immediate execution mode)", style="blue")
    except FileNotFoundError:
        console.print("ℹ️  Celery not available (immediate execution mode)", style="blue")
    except Exception as e:
        console.print("ℹ️  Celery not configured (immediate execution mode)", style="blue")

@app.command()
def check_env():
    """Check environment configuration without starting services."""
    
    console.print(Panel.fit(
        "[bold]Environment Configuration Check[/bold]",
        title="🔍 NI-REST Environment",
        border_style="blue"
    ))
    
    # Check both modes
    console.print("\n[bold blue]Development Mode Check:[/bold blue]")
    dev_valid = validate_environment(dev_mode=True)
    
    console.print("\n[bold green]Production Mode Check:[/bold green]")  
    prod_valid = validate_environment(dev_mode=False)
    
    # Summary table
    table = Table(title="Environment Summary")
    table.add_column("Mode", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Notes")
    
    table.add_row(
        "Development", 
        "✅ Ready" if dev_valid else "❌ Issues",
        "Uses .env file, allows missing credentials"
    )
    table.add_row(
        "Production", 
        "✅ Ready" if prod_valid else "❌ Issues",
        "Requires all environment variables"
    )
    
    console.print(table)
    
    if not prod_valid:
        console.print("\n[yellow]To prepare for production:[/yellow]")
        console.print("1. Set DJANGO_SECRET_KEY environment variable")
        console.print("2. Set DATABASE_URL for production database")
        console.print("3. Set NI_INVENTORY_SETTING_TOKEN_* variables")
        console.print("4. Set NI_NET_CREDS_LOGIN_* and NI_NET_CREDS_PASSWORD_* variables")
        console.print("5. Configure Redis/RabbitMQ for Celery")

@app.command()
def manage(
    command: str = typer.Argument(..., help="Django management command to run"),
    args: Optional[list[str]] = typer.Argument(None, help="Additional arguments")
):
    """
    Run Django management commands.
    
    Examples:
        ni-rest manage migrate
        ni-rest manage createsuperuser  
        ni-rest manage collectstatic
        ni-rest manage shell
    """
    project_root = get_project_root()
    manage_py = project_root / "manage.py"
    
    if not manage_py.exists():
        console.print(f"❌ manage.py not found in {project_root}", style="red")
        raise typer.Exit(1)
    
    # Build command
    cmd = [sys.executable, "manage.py", command]
    if args:
        cmd.extend(args)
    
    console.print(f"🔧 Running: {' '.join(cmd)}", style="blue")
    
    try:
        subprocess.run(cmd, cwd=project_root, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Command failed: {e}", style="red")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()