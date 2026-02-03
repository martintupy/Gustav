from pathlib import Path

from loguru import logger

LOG_DIR = Path.home() / ".config" / "ghai" / "logs"


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        LOG_DIR / "ghai.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    )
