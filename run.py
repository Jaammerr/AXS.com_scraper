import asyncio
import sys

from multiprocessing import freeze_support
from loguru import logger

from application import ApplicationManager
from utils import setup_logs


async def main() -> None:
    app = ApplicationManager()

    try:
        await app.initialize()
        await app.run()
    finally:
        await app.shutdown()


def run() -> int:
    freeze_support()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    setup_logs(is_main=True)

    try:
        asyncio.run(main())
        return 0
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        return 130
    except Exception as exc:
        logger.error(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(run())
