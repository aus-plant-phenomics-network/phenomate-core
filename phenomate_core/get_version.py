import logging
from typing import Callable

# from phenomate_core.get_logging import shared_logger
shared_logger = logging.getLogger("celery")


def get_version() -> str:
    """Returns the version of the package or an empty string (if available methods do not obtain the string)."""
    try:
        from importlib.metadata import version

        return version("phenomate-core")
    except ImportError as e:
        shared_logger.warning(f"Cannot get __version__ string: {e}")

    try:
        from pathlib import Path

        import tomlib  # in Python 3.11+

        pyproject_path = Path(__file__).parent / "pyproject.toml"

        with pyproject_path.open("rb") as f:
            data = tomlib.load(f)
        return data["project"]["version"]

    except ImportError as e:
        shared_logger.warning(f"Cannot get __version__ string: {e}")

    return ""


def get_task_logger(name: str) -> logging.Logger:
    try:
        from celery.utils.log import get_task_logger as _gtl  # local import
        get_celery_logger: Callable[[str], logging.Logger] = _gtl  # type: ignore[assignment]
        return get_celery_logger(name)
    except Exception:
        return logging.getLogger(name)