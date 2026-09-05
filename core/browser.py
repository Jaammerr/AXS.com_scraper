import asyncio

from pathlib import Path
from typing import Optional

from cloakbrowser import launch_context_async
from loguru import logger
from playwright.async_api import BrowserContext, Page


class BrowserManager:
    def __init__(
        self,
        license_key: str,
        browser_version: Optional[str] = None,
        headless: bool = False,
        storage_path: Path = Path("storage"),
    ) -> None:
        self.license_key = license_key
        self.headless = headless
        self.browser_version = browser_version
        self.storage_path = storage_path

        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.proxy: Optional[str] = None
        self.proxy_ip: Optional[str] = None
        self.current_storage_path: Optional[Path] = None

        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def start(
        self,
        proxy: Optional[str] = None,
        proxy_ip: Optional[str] = None,
    ) -> Page:
        if self.context:
            raise RuntimeError("Browser is already running.")

        if proxy and not proxy_ip:
            raise ValueError("Proxy IP is required when proxy mode is used.")

        if proxy_ip and not proxy:
            raise ValueError("Proxy URL is required when proxy IP is provided.")

        storage_file = self._get_storage_path(proxy_ip)
        has_storage = storage_file.exists()

        if proxy:
            logger.info("Starting browser")
        else:
            logger.info("Starting browser without proxy..")

        if has_storage:
            logger.debug("Restoring browser storage state")

        try:
            context = await launch_context_async(
                headless=self.headless,
                proxy=proxy,
                geoip=bool(proxy),
                humanize=True,
                human_preset="careful",
                storage_state=str(storage_file) if has_storage else None,
                viewport={
                    "width": 1920,
                    "height": 1080,
                },
                browser_version=self.browser_version,
                license_key=self.license_key,
            )

            self.context = context
            self.proxy = proxy
            self.proxy_ip = proxy_ip
            self.current_storage_path = storage_file

            page = await context.new_page()
            self.page = page

            logger.success("Browser started")
            return page

        except Exception as exc:
            logger.error(f"Browser start failed: {exc}")
            await self.close(save_state=False)
            raise

    async def restart(
        self,
        proxy: Optional[str] = None,
        proxy_ip: Optional[str] = None,
    ) -> Page:
        logger.info("Restarting browser")
        await self.close()
        return await self.start(proxy=proxy, proxy_ip=proxy_ip)

    async def new_page(self) -> Page:
        context = self.context

        if context is None:
            raise RuntimeError("Browser is not running.")

        page = await context.new_page()
        self.page = page
        return page

    async def save_storage(self) -> None:
        context = self.context
        storage_file = self.current_storage_path

        if context is None or storage_file is None:
            return

        try:
            await context.storage_state(path=str(storage_file))
            logger.debug("Browser storage state saved")
        except Exception as exc:
            logger.warning(f"Browser storage state save failed: {exc}")

    async def close(self, save_state: bool = True) -> None:
        context = self.context

        if context is None:
            return

        if save_state:
            await self.save_storage()

        try:
            await asyncio.wait_for(
                context.close(),
                timeout=10,
            )
        except Exception as exc:
            logger.warning(f"Browser close failed: {exc}")

        self.context = None
        self.page = None
        self.proxy = None
        self.proxy_ip = None
        self.current_storage_path = None

        logger.info("Browser closed")

    def _get_storage_path(self, proxy_ip: Optional[str]) -> Path:
        if not proxy_ip:
            return self.storage_path / "direct.json"

        safe_ip = proxy_ip.replace(":", "_")
        return self.storage_path / f"{safe_ip}.json"
