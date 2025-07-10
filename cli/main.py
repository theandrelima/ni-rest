#!/usr/bin/env python3
"""
NI-REST CLI - Command line interface for Network Importer REST API

This CLI starts the Django server which automatically detects worker availability.
"""

import os
import sys
import psutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ni_rest.core.db_utils import get_database_config


app = typer.Typer(
    name="ni-rest",
    help="Network Importer REST API - Auto-detects worker availability",
    add_completion=False
)

console = Console()

def setup_django_environment():
    """Setup Django environment for direct management command execution"""
    try:
        # Add the project root to Python path for development
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Set Django settings module
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ni_rest.core.settings')
        
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
        
        # For runserver, use subprocess to maintain proper process hierarchy
        if command == 'runserver':
            manage_py_path = Path(__file__).parent.parent / 'ni_rest' / 'manage.py'
            cmd = [sys.executable, str(manage_py_path), 'runserver'] + list(args)
            
            # This allows Django's auto-reloader to work properly
            result = subprocess.run(cmd)
            return result.returncode == 0
        else:
            # For other commands, use the existing approach
            from django.core.management import execute_from_command_line
            argv = ['manage.py', command] + list(args)
            execute_from_command_line(argv)
            return True
            
    except SystemExit as e:
        return True
    except Exception as e:
        console.print(f"❌ Command failed: {e}", style="red")
        return False

def find_django_processes():
    """Find running Django processes"""
    django_processes = []
    current_pid = os.getpid() # Get the PID of the current 'ni-rest stop' process

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'environ']):
            try:
                # Skip the current process itself
                if proc.pid == current_pid:
                    continue

                cmdline = proc.info['cmdline']
                if not cmdline:
                    continue
                
                cmdline_str = ' '.join(cmdline)
                
                # Check for Django runserver in command line
                is_runserver = 'runserver' in cmdline_str
                is_python = 'python' in cmdline_str.lower()
                
                # Check environment for RUN_MAIN (Django auto-reloader)
                is_django_reloader = False
                try:
                    env = proc.info.get('environ', {})
                    if env and 'RUN_MAIN' in env:
                        is_django_reloader = True
                except (psutil.AccessDenied, AttributeError):
                    pass
                
                # A process is a Django server if:
                # 1. It's a python process running the 'runserver' command, OR
                # 2. It's a python process spawned by the auto-reloader.
                is_django_process = (is_runserver and is_python) or (is_python and is_django_reloader)
                
                if is_django_process:
                    django_processes.append(proc)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        console.print(f"⚠️  Error finding processes: {e}", style="yellow")
    
    return django_processes



def check_broker_connection() -> bool:
    """Check if the message broker is available"""
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    console.print(f"📡 Celery broker: {broker_url}", style="blue")

    try:
        if broker_url.startswith('redis://'):
            return _check_redis_broker(broker_url)
        elif broker_url.startswith('memory://'):
            console.print("✅ Memory broker (always available)", style="green")
            return True
        else:
            console.print(f"❌ Unsupported broker: Only Redis is supported. Found '{broker_url.split('://')[0]}'.", style="red")
            return False
    except Exception as e:
        console.print(f"❌ Error checking broker: {e}", style="red")
        return False

def _check_redis_broker(broker_url: str) -> bool:
    """Check Redis broker availability"""
    try:
        import redis
        
        # Parse Redis URL
        # Format: redis://[:password@]host[:port][/db]
        url_parts = broker_url.replace('redis://', '').split('/')
        host_port_auth = url_parts[0]
        db = int(url_parts[1]) if len(url_parts) > 1 and url_parts[1] else 0
        
        # Parse auth and host:port
        if '@' in host_port_auth:
            auth, host_port = host_port_auth.rsplit('@', 1)
            password = auth.split(':', 1)[1] if ':' in auth else auth
        else:
            password = None
            host_port = host_port_auth
        
        # Parse host and port
        if ':' in host_port:
            host, port = host_port.split(':', 1)
            port = int(port)
        else:
            host = host_port
            port = 6379
        
        # Try to connect
        r = redis.Redis(host=host, port=port, db=db, password=password, socket_connect_timeout=3)
        r.ping()
        console.print(f"✅ Redis broker available at {host}:{port}", style="green")
        return True
        
    except ImportError:
        console.print("❌ Redis client not installed (pip install redis)", style="red")
        return False
    except redis.ConnectionError:
        console.print(f"❌ Redis broker not available at {broker_url}", style="red")
        return False
    except Exception as e:
        console.print(f"❌ Redis broker check failed: {e}", style="red")
        return False

def check_celery_workers(broker_available: bool = None) -> bool:
    """Check if Celery workers are available"""
    # Use provided broker status or check it ourselves
    if broker_available is None:
        broker_available = check_broker_connection()
    
    if not broker_available:
        console.print("ℹ️  No broker available (immediate execution mode)", style="blue")
        return False
    
    try:
        # Try to import celery and check broker connection
        from celery import Celery
        
        # Create temporary Celery app to check connection
        celery_app = Celery('ni_rest_check')
        celery_app.config_from_object('ni_rest.core.celery')  # Updated path
        
        # Try to inspect active workers
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            console.print("✅ Celery workers are available (async execution)", style="green")
            console.print(f"   Active workers: {list(active_workers.keys())}", style="dim")
            return True
        else:
            console.print("ℹ️  No active Celery workers (immediate execution mode)", style="blue")
            return False
            
    except ImportError:
        console.print("ℹ️  Celery not available (immediate execution mode)", style="blue")
        return False
    except Exception as e:
        console.print("ℹ️  Celery workers not configured (immediate execution mode)", style="blue")
        return False

def validate_environment(dev_mode: bool = False) -> bool:
    """
    Validate that required environment variables are set.
    
    Args:
        dev_mode: If True, allows missing env vars (development mode)
        
    Returns:
        True if environment is valid
    """
    # Required for Django
    django_secret = os.getenv('DJANGO_SECRET_KEY')
    if not django_secret and not dev_mode:
        console.print("❌ DJANGO_SECRET_KEY is required in production mode", style="red")
        return False
    elif not django_secret and dev_mode:
        console.print("⚠️  DJANGO_SECRET_KEY not set - using development fallback", style="yellow")
    else:
        console.print("✅ DJANGO_SECRET_KEY configured", style="green")
    
    # Check database configuration by calling the same utility Django uses
    try:
        db_config = get_database_config()['default']
        db_engine = db_config.get('ENGINE', '')
        
        if 'sqlite' in db_engine:
            db_path = db_config.get('NAME', 'N/A')
            console.print(f"💾 Database: SQLite at [bold cyan]{db_path}[/bold cyan]", style="blue")
        elif 'postgresql' in db_engine:
            db_host = db_config.get('HOST', 'unknown')
            db_name = db_config.get('NAME', 'unknown')
            console.print(f"💾 Database: PostgreSQL ([bold cyan]{db_name}[/bold cyan] at {db_host})", style="blue")
        elif 'mysql' in db_engine:
            db_host = db_config.get('HOST', 'unknown')
            db_name = db_config.get('NAME', 'unknown')
            console.print(f"💾 Database: MySQL ([bold cyan]{db_name}[/bold cyan] at {db_host})", style="blue")
        else:
            engine_name = db_engine.split('.')[-1] if db_engine else 'N/A'
            console.print(f"💾 Database: Custom ([bold cyan]{engine_name}[/bold cyan])", style="blue")
            
    except Exception as e:
        console.print(f"❌ Could not determine database configuration: {e}", style="red")
        return False
    
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
    """
    
    # Check if we're being executed by Django's auto-reloader
    is_reloader_process = os.environ.get('RUN_MAIN') == 'true'
    
    try:
        # Set Django environment variables
        if dev:
            os.environ['DJANGO_ENV'] = 'development'
            os.environ['DJANGO_DEBUG'] = 'True'
        else:
            os.environ['DJANGO_ENV'] = 'production' 
            os.environ['DJANGO_DEBUG'] = 'False'
        
        # Only show banner and validation in the initial process
        if not is_reloader_process:
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
            
            console.print("🔧 Environment configured for {} mode".format(mode_text.lower()), style=color)
            
            # Validate environment
            console.print("\n🔍 Validating environment...", style="yellow")
            if not validate_environment(dev):
                console.print("\n❌ Environment validation failed", style="red")
                console.print("Fix the issues above and try again", style="dim")
                raise typer.Exit(1)
            
            # Check broker and workers
            broker_available = check_broker_connection()
            workers_available = check_celery_workers(broker_available)
            
            # Show final startup info
            console.print(f"\n📡 Server will be available at: http://{host}:{port}/", style="bold")
            console.print(f"👨‍💻 Admin interface: http://{host}:{port}/admin/", style="dim")
            console.print(f"🤖 API endpoints: http://{host}:{port}/api/", style="dim")
            console.print(f"📚 API documentation: http://{host}:{port}/api/docs/", style="dim")
            
            if broker_available and not workers_available:
                console.print("\n💡 Broker available - start Celery workers for async execution:", style="cyan")
                console.print("   celery -A ni_rest worker --loglevel=info", style="dim")
            elif not broker_available:
                console.print("\n⚠️  No message broker - jobs will execute immediately", style="yellow")
            
            console.print("\n🏁 Starting server...\n", style="bold green")
        
        # Start the Django development server (this runs in both processes)
        run_django_command("runserver", f"{host}:{port}")
        
    except KeyboardInterrupt:
        if not is_reloader_process:
            console.print("\n\n⏹️  Server stopped by user", style="yellow")
    except Exception as e:
        if not is_reloader_process:
            console.print(f"\n❌ Server failed to start: {e}", style="red")
        raise typer.Exit(1)

@app.command()
def stop(
    force: bool = typer.Option(
        False,
        "--force",
        help="Force kill processes if graceful shutdown fails"
    ),
    port: int = typer.Option(
        None,
        "--port",
        help="Stop server running on specific port"
    )
):
    """
    Stop running NI-REST API server(s).
    
    Examples:
        ni-rest stop                    # Stop all Django servers
        ni-rest stop --port 8000        # Stop server on port 8000
        ni-rest stop --force            # Force kill if needed
    """
    
    console.print(Panel.fit(
        "[bold]Stopping NI-REST API Server[/bold]",
        title="⏹️  Server Shutdown",
        border_style="yellow"
    ))
    
    # Find Django processes
    django_processes = find_django_processes()
    
    if not django_processes:
        console.print("ℹ️  No running Django servers found", style="blue")
        return
    
    # Filter by port if specified
    if port:
        filtered_processes = []
        for proc in django_processes:
            try:
                cmdline = ' '.join(proc.info['cmdline'])
                if f":{port}" in cmdline or f" {port}" in cmdline:
                    filtered_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not filtered_processes:
            console.print(f"ℹ️  No Django server found running on port {port}", style="blue")
            return
        
        django_processes = filtered_processes
    
    console.print(f"🔍 Found {len(django_processes)} Django server process(es) to stop", style="blue")
    
    stopped_count = 0
    failed_count = 0
    
    for proc in django_processes:
        try:
            pid = proc.pid
            cmdline = ' '.join(proc.info['cmdline'])
            
            # Identify process type for clearer output
            proc_type = "Watcher (Parent)"
            try:
                env = proc.environ()
                if env and 'RUN_MAIN' in env:
                    proc_type = "Server (Reloader Child)"
            except (psutil.AccessDenied, psutil.Error):
                proc_type = "Unknown"

            console.print(f"🛑 Stopping process {pid} ({proc_type})", style="dim")
            
            # Try graceful shutdown first
            try:
                proc.terminate()  # Send SIGTERM
                proc.wait(timeout=5)  # Wait up to 5 seconds
                console.print(f"✅ Process {pid} stopped gracefully", style="green")
                stopped_count += 1
            except psutil.TimeoutExpired:
                if force:
                    console.print(f"⚠️  Process {pid} didn't stop gracefully, force killing...", style="yellow")
                    proc.kill()  # Send SIGKILL
                    proc.wait(timeout=3)
                    console.print(f"✅ Process {pid} force killed", style="green")
                    stopped_count += 1
                else:
                    console.print(f"❌ Process {pid} didn't stop gracefully (use --force to kill)", style="red")
                    failed_count += 1
            
        except psutil.NoSuchProcess:
            # This is expected if the parent terminates the child
            console.print(f"ℹ️  Process {pid} already stopped", style="blue")
            stopped_count += 1
        except psutil.AccessDenied:
            console.print(f"❌ Access denied to stop process {pid}", style="red")
            failed_count += 1
        except Exception as e:
            console.print(f"❌ Error stopping process {pid}: {e}", style="red")
            failed_count += 1
    
    # Summary
    console.print(f"\n📊 Summary: {stopped_count} stopped, {failed_count} failed", style="bold")
    
    if failed_count > 0:
        console.print("💡 Try using --force to kill unresponsive processes", style="cyan")
        raise typer.Exit(1)
    else:
        console.print("✅ All servers stopped successfully", style="green")

@app.command()
def status():
    """Show status of the application and any available workers."""
    
    console.print(Panel.fit(
        "[bold]NI-REST Application Status[/bold]",
        title="🚥 Status Check",
        border_style="blue"
    ))
    
    # Check for running Django processes
    django_processes = find_django_processes()
    if django_processes:
        console.print(f"🚀 Found {len(django_processes)} running Django server(s):", style="green")
        for proc in django_processes:
            try:
                console.print(f"   • PID {proc.pid}", style="dim")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    else:
        console.print("⏹️  No running Django servers found", style="yellow")
    
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
    
    # Check broker and workers
    check_celery_workers()
    
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

@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def manage(
    ctx: typer.Context,
    command: str = typer.Argument(..., help="Django management command to run"),
):
    """
    Run Django management commands.
    
    Examples:
        ni-rest manage migrate
        ni-rest manage createsuperuser  
        ni-rest manage collectstatic --noinput
        ni-rest manage shell
    """
    # Build command arguments
    cmd_args = [command] + ctx.args

    console.print(f"🔧 Running: manage.py {' '.join(cmd_args)}", style="blue")

    if not run_django_command(*cmd_args):
        console.print("❌ Command failed", style="red")
        raise typer.Exit(1)

def main():
    """Entry point function - only this should be called by the script entry point"""
    app()

if __name__ == "__main__":
    main()
