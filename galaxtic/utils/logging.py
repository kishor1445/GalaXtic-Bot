import logging
from rich.logging import RichHandler
from pathlib import Path

def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RichHandler(
                rich_tracebacks=True,                
            ),
            logging.FileHandler(log_dir / "galaxtic.log"),
        ],
    )

    return logging.getLogger("galaxtic")

logger = setup_logging()

__all__ = ["logger"]
