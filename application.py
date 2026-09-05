import asyncio

from pathlib import Path
from loguru import logger

from core.browser import BrowserManager
from core.exceptions import ScraperBlockedError
from core.scraper import AXSScraper

from dependencies import config, proxy_manager
from utils.base import mask_proxy


class ApplicationManager:
    def __init__(self) -> None:
        self.tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        if not config.application_settings.use_proxy:
            logger.info("Proxy mode disabled")
            return

        if not await proxy_manager.initialize():
            raise RuntimeError("Proxy mode is enabled, but no valid proxies are available.")

        self.tasks.append(asyncio.create_task(proxy_manager.watch_proxy_file()))

    async def run(self) -> None:
        logger.info("Application started")

        if config.application_settings.use_proxy:
            await self._run_with_proxy()
        else:
            await self._run_without_proxy()

    async def _run_without_proxy(self) -> None:
        logger.info("Scraping attempt #1 started without proxy")
        scraper = self._create_scraper()

        try:
            await scraper.run(event_url=config.application_settings.event_page)
        except ScraperBlockedError as exc:
            logger.error(f"Scraping attempt #1 blocked: {exc}")
            raise
        except Exception as exc:
            logger.error(f"Scraping attempt #1 failed: {exc}")
            raise

    async def _run_with_proxy(self) -> None:
        previous_proxy: str | None = None
        attempt = 0

        while True:
            proxy_data = await proxy_manager.get_proxy(
                exclude={previous_proxy} if previous_proxy else None,
                wait_if_empty=False,
            )

            if proxy_data is None:
                raise RuntimeError(f"No proxies available after {attempt} attempts.")

            proxy, proxy_ip = proxy_data
            attempt += 1

            logger.info(f"Scraping attempt #{attempt} started with proxy {mask_proxy(proxy)}")
            scraper = self._create_scraper()

            try:
                await scraper.run(
                    event_url=config.application_settings.event_page,
                    proxy=proxy,
                    proxy_ip=proxy_ip,
                )
            except ScraperBlockedError as exc:
                logger.error(f"Scraping attempt #{attempt} blocked: {exc}")
                await proxy_manager.remove_proxy(proxy)

                logger.info("Proxy removed from runtime pool. Retrying with another available proxy..")
                await asyncio.sleep(1)
                continue

            except Exception as exc:
                logger.warning(f"Scraping attempt #{attempt} failed: {exc}")
                await proxy_manager.release_proxy(proxy)
                previous_proxy = proxy

                logger.info("Retrying with another available proxy..")
                await asyncio.sleep(1)
                continue

            await proxy_manager.release_proxy(proxy)
            logger.success(f"Scraping completed successfully on attempt #{attempt}")
            return

    @staticmethod
    def _create_scraper() -> AXSScraper:
        headless = config.cloak_browser_settings.headless
        browser_version = config.cloak_browser_settings.version
        license_key = config.cloak_browser_settings.license_key

        return AXSScraper(
            browser_manager=BrowserManager(
                license_key=license_key,
                browser_version=browser_version,
                headless=headless,
            ),
            screenshots_path=Path("screenshots"),
        )

    async def shutdown(self) -> None:
        if not self.tasks:
            return

        logger.info("Stopping background tasks")

        try:
            for task in self.tasks:
                task.cancel()

            await asyncio.gather(
                *self.tasks,
                return_exceptions=True,
            )
        except Exception as e:
            logger.warning(f"Background tasks can't be cancelled: {e}")

        self.tasks.clear()
        logger.info("Background tasks stopped")
