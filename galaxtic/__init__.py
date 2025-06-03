from .config import Settings
from .utils.logging import logger

settings = Settings()

__all__ = ["settings", "logger"]
