import logging
#from phenomate_core.get_logging import shared_logger
shared_logger = logging.getLogger('celery')

def get_version() -> str:
    """
    Returns the version of the package or an empty string (if available methods do not obtain the string).
    
    """
    try:
        from importlib.metadata import version
        return version("phenomate-core")
    except ImportError:
        shared_logger.warning(f"Cannot get __version__ string: {e}")
        
    try:
        import tomlib  # in Python 3.11+
        from pathlib import Path
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        
        with pyproject_path.open("rb") as f:
            data = tomlib.load(f)
        return data["project"]["version"]

    except ImportError:
        shared_logger.warning(f"Cannot get __version__ string: {e}")
        
    return ""