"""File and path utilities"""

import os
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, create if necessary"""
    path = Path(path).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, max_length: int = 50) -> str:
    """Create a safe filename from arbitrary string"""
    import re
    
    # Replace unsafe characters
    safe = re.sub(r'[^\w\s\-.]', '_', name)
    
    # Replace multiple spaces/underscores with single underscore
    safe = re.sub(r'[\s_]+', '_', safe)
    
    # Remove leading/trailing underscores
    safe = safe.strip('_')
    
    # Truncate if too long
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip('_')
    
    return safe or "untitled"


def get_user_data_dir() -> Path:
    """Get user data directory for Nova"""
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', '~'))
    else:  # Unix-like
        base = Path(os.environ.get('XDG_DATA_HOME', '~/.local/share'))
    
    return ensure_dir(base / 'nova')


def get_user_config_dir() -> Path:
    """Get user config directory for Nova"""
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', '~'))
    else:  # Unix-like
        base = Path(os.environ.get('XDG_CONFIG_HOME', '~/.config'))
    
    return ensure_dir(base / 'nova')