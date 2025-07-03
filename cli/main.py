#!/usr/bin/env python3
"""
NI-REST CLI - Command line interface for Network Importer REST API

This CLI starts the Django server which automatically detects worker availability.
"""

import os
import sys
from pathlib import Path

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

def setup_django_environment():
    """Setup Django environment for direct management command execution"""
    try:
        import ni_rest
        ni_rest_path = Path(ni_rest.__file__).parent
        
        # Add the parent directory to Python path so Django can find the modules
        python_path = str(ni_rest_path.parent)
        if python_path not in sys.path:
            sys.path.insert(0, python_path)
        
        # Set Django settings module
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ni_rest.settings')
        
        # Configure Django
        import django
        django.setup()
        
        return True
    except ImportError as e:
        console.print(f"❌ Failed to import Django modules: {e}", style="red")
        return False
    except Exception as e:
        console.print(f"❌ Failed to setup Django: {e}", style="red")
        return False

def run_django_command(command: str, *args) -> bool:
    """Run a Django management command directly"""
    try:
        if not setup_django_environment():
            return False
            
        from django.core.management import execute_from_command_line
        
        # Build command line arguments
        argv = ['manage.py', command] + list(args)
        
        # Execute the command
        execute_from_command_line(argv)
        return True
        
    except SystemExit as e:
        # Django commands often call sys.exit(), which is normal
        return e.code == 0
    except Exception as e:
        console.print(f"❌ Command failed: {e}", style="red")
        return False

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

def check_celery_workers() -> bool:
    """Check if Celery workers are available"""
    try:
        # Try to import celery and check broker connection
        from celery import Celery
        
        # Get broker URL from environment
        broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        
        # Create temporary Celery app to check connection
        app = Celery('ni_rest_check')
        app.config_from_object('ni_rest.celery')
        
        # Try to inspect active workers
        inspect = app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            console.print("✅ Celery workers are available (async execution)", style="green")
            console.print(f"Active workers: {list(active_workers.keys())}", style="dim")
            return True
        else:
            console.print("ℹ️  No dedicated Celery workers (immediate execution mode)", style="blue")
            return False
            
    except ImportError:
        console.print("ℹ️  Celery not available (immediate execution mode)", style="blue")
        return False
    except Exception as e:
        console.print("ℹ️  Celery not configured (immediate execution mode)", style="blue")
        return False

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
    
    # Show final startup info
    console.print(f"\n📡 Server will be available at: http://{host}:{port}/", style="bold")
    console.print(f"👨‍💻 Admin interface: http://{host}:{port}/admin/", style="dim")
    console.print(f"🤖 API endpoints: http://{host}:{port}/api/", style="dim")
    console.print(f"📚 API documentation: http://{host}:{port}/api/docs/", style="dim")
    
    console.print("\n💡 Optional: Start Celery workers for async execution:", style="cyan")
    console.print("   celery -A ni_rest worker --loglevel=info", style="dim")
    console.print("   (Server works with or without workers)", style="dim")
    
    console.print("\n🏁 Starting server...\n", style="bold green")
    
    # Start the Django development server directly
    try:
        if not run_django_command("runserver", f"{host}:{port}"):
            console.print("❌ Failed to start server", style="red")
            raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n\n⏹️  Server stopped by user", style="yellow")
    except Exception as e:
        console.print(f"\n❌ Server failed to start: {e}", style="red")
        raise typer.Exit(1)

@app.command()
def status():
    """Show status of the application and any available workers."""
    
    console.print(Panel.fit(
        "[bold]NI-REST Application Status[/bold]",
        title="🚥 Status Check",
        border_style="blue"
    ))
    
    # Check Django application
    if run_django_command("check"):
        console.print("✅ Django application configuration is valid", style="green")
    else:
        console.print("❌ Django application has configuration issues", style="red")
    
    # Check worker status
    check_celery_workers()

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
    args: list[str] | None = typer.Argument(None, help="Additional arguments")
):
    """
    Run Django management commands.
    
    Examples:
        ni-rest manage migrate
        ni-rest manage createsuperuser  
        ni-rest manage collectstatic
        ni-rest manage shell
    """
    
    # Build command arguments
    cmd_args = [command]
    if args:
        cmd_args.extend(args)
    
    console.print(f"🔧 Running: manage.py {' '.join(cmd_args)}", style="blue")
    
    if not run_django_command(*cmd_args):
        console.print("❌ Command failed", style="red")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()