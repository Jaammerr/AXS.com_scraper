import os
import sys

from datetime import datetime
from pathlib import Path

from loguru import logger


def setup_multiprocess_logging(is_main: bool = False) -> None:
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )

    logger.add(sys.stdout, format=log_format, enqueue=True, colorize=True, level="DEBUG")

    if is_main:
        log_file = log_path / f"main_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    else:
        log_file = log_path / f"process_{os.getpid()}.log"

    logger.add(
        str(log_file),
        format=log_format,
        rotation="75 MB",
        retention="3 days",
        compression="zip",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        level="INFO",
    )


def setup_logs(is_main: bool = False) -> None:
    setup_multiprocess_logging(is_main)
