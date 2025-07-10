"""Database configuration utilities for ni-rest."""

import os
from pathlib import Path
import dj_database_url

def get_database_config() -> dict[str, dict[str, any]]:
    db_cfg = dj_database_url.config(
        default=f"sqlite:///{_get_default_sqlite_path()}"
    )
    if isinstance(db_cfg, dict) and 'default' in db_cfg:
        # Already a full DATABASES dict
        return db_cfg
    return {'default': db_cfg}

def _get_default_sqlite_path() -> Path:
    """
    Determine the best default location for the SQLite database.
    
    This is only used as a fallback if DATABASE_URL is not set.
    
    Returns:
        A Path object pointing to the default SQLite database file.
    """
    # Allow explicit override even for the default path
    db_path = os.getenv('DATABASE_PATH')
    if db_path:
        return Path(db_path)
    
    django_env = os.getenv('DJANGO_ENV', 'development')
    
    # In development, the default is the current working directory.
    if django_env == 'development':
        return Path.cwd() / 'db.sqlite3'
    
    # In production, the default is a system-appropriate data directory.
    if os.name == 'nt':
        data_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        data_dir = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    
    app_data_dir = data_dir / 'ni-rest'
    app_data_dir.mkdir(parents=True, exist_ok=True)
    
    return app_data_dir / 'db.sqlite3'
