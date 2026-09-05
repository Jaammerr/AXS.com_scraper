import asyncio

from datetime import datetime
from enum import Enum
from pathlib import Path
from random import randint
from typing import Optional
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from core.browser import BrowserManager
from core.exceptions import (
    AXSAntiBotBlockedError,
    AXSRestrictedError,
    CloudflareBlockedError,
    CloudflareManualChallengeError,
    ScraperTimeoutError,
)


class PageState(Enum):
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    CLOUDFLARE_BLOCKED = "cloudflare_blocked"
    AXS_RESTRICTED = "axs_restricted"
    AXS_BOT_BLOCKED = "axs_bot_blocked"
    LOADING = "loading"
    READY = "ready"


class AXSScraper:
    def __init__(
        self,
        browser_manager: BrowserManager,
        screenshots_path: Path,
    ) -> None:
        self.browser_manager = browser_manager
        self.screenshots_path = screenshots_path

        self.success_path = screenshots_path / "success"
        self.failed_path = screenshots_path / "failed"

        self.success_path.mkdir(parents=True, exist_ok=True)
        self.failed_path.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        event_url: str,
        proxy: Optional[str] = None,
        proxy_ip: Optional[str] = None,
    ) -> Path:
        page = await self.browser_manager.start(proxy=proxy, proxy_ip=proxy_ip)
        save_storage = False

        try:
            await page.wait_for_timeout(randint(1000, 3000))
            await self._open_event(page, event_url)
            await self._wait_until_ready(page, timeout=60, challenge_timeout=20)
            await self._wait_map_loaded(page, timeout=30)
            await self._wait_page_loaded(page)

            screenshot = await self._save_screenshot(page)
            save_storage = True
            logger.success(f"Event page loaded successfully | Screenshot path: {screenshot}")
            return screenshot
        except Exception:
            try:
                await self._save_screenshot(page, failed=True)
            except Exception as exc:
                logger.warning(f"Failed to save error screenshot: {exc}")
            raise
        finally:
            await self.browser_manager.close(save_state=save_storage)

    @staticmethod
    async def _open_event(page: Page, event_url: str) -> None:
        logger.info(f"Opening event page: {event_url}")
        await page.goto(event_url, wait_until="domcontentloaded", timeout=60_000)

    async def _wait_until_ready(
        self,
        page: Page,
        timeout: int = 60,
        challenge_timeout: int = 20,
    ) -> None:
        logger.info("Waiting for final page state...")

        loop = asyncio.get_running_loop()
        started_at = loop.time()
        challenge_started_at: float | None = None
        challenge_active = False
        challenge_count = 0
        last_state: PageState | None = None

        while loop.time() - started_at < timeout:
            try:
                state = await self._detect_state(page)

                if state != last_state:
                    logger.info(f"Page state: {state.value}")

                if state == PageState.AXS_RESTRICTED:
                    raise AXSRestrictedError("AXS restricted the current session.")

                if state == PageState.AXS_BOT_BLOCKED:
                    raise AXSAntiBotBlockedError("AXS anti-bot blocked access.")

                if state == PageState.CLOUDFLARE_BLOCKED:
                    raise CloudflareBlockedError("Cloudflare blocked access.")

                if state == PageState.READY:
                    logger.success("Event page is ready")
                    return

                if state == PageState.CLOUDFLARE_CHALLENGE:
                    if not challenge_active:
                        challenge_active = True
                        challenge_count += 1
                        challenge_started_at = loop.time()
                        logger.info(f"Cloudflare challenge #{challenge_count} detected")
                    elif challenge_started_at is not None and loop.time() - challenge_started_at >= challenge_timeout:
                        raise CloudflareManualChallengeError(f"Cloudflare challenge #{challenge_count} requires manual interaction.")

                elif challenge_active:
                    challenge_active = False
                    challenge_started_at = None

                last_state = state

            except (
                CloudflareBlockedError,
                CloudflareManualChallengeError,
                AXSAntiBotBlockedError,
                AXSRestrictedError,
            ):
                raise
            except Exception as exc:
                if self._is_navigation_error(str(exc).lower()):
                    await asyncio.sleep(1)
                    continue
                raise

            await asyncio.sleep(1)

        raise ScraperTimeoutError(f"Page did not reach a final state after {timeout} seconds.")

    async def _detect_state(self, page: Page) -> PageState:
        try:
            title = (await page.title()).lower().strip()
        except Exception:
            return PageState.LOADING

        try:
            body = (await page.locator("body").inner_text(timeout=2_000)).lower()
        except Exception:
            body = ""

        if self._is_axs_restricted(title, body):
            return PageState.AXS_RESTRICTED

        if self._is_axs_bot_blocked(title, body):
            return PageState.AXS_BOT_BLOCKED

        if self._is_cloudflare_blocked(title, body):
            return PageState.CLOUDFLARE_BLOCKED

        if self._is_event_page_ready(page, body):
            return PageState.READY

        if await self._is_cloudflare_challenge(page, title, body):
            return PageState.CLOUDFLARE_CHALLENGE

        return PageState.LOADING

    async def _is_cloudflare_challenge(self, page: Page, title: str, body: str) -> bool:
        title_markers = (
            "verification in progress",
            "just a moment",
            "трохи зачекайте",
        )

        if any(marker in title for marker in title_markers):
            return True

        body_markers = (
            "verify you are a real fan",
            "ensuring a fair fan experience",
            "verification successful",
            "перевірка пройшла успішно",
        )

        if any(marker in body for marker in body_markers):
            return True

        return await self._has_turnstile(page)

    @staticmethod
    async def _has_turnstile(page: Page) -> bool:
        try:
            if await page.locator("[name='cf-turnstile-response']").count():
                return True
        except Exception:
            pass

        try:
            return any("challenges.cloudflare.com" in frame.url for frame in page.frames)
        except Exception:
            return False

    @staticmethod
    def _is_axs_restricted(title: str, body: str) -> bool:
        if "restricted access" in title:
            return True

        markers = (
            "we are sorry, your access has been restricted",
            "your access was restricted when you tried to visit the website",
            "the website you tried to access has been configured to block access",
        )
        return any(marker in body for marker in markers)

    @staticmethod
    def _is_axs_bot_blocked(title: str, body: str) -> bool:
        title_markers = (
            "something doesn't look right",
            "something doesn’t look right",
            "oh no!",
            "oh no",
            "are you a real fan?",
            "are you a real fan",
        )

        if title in title_markers:
            return True

        body_lines = {line.strip() for line in body.splitlines() if line.strip()}
        if {"are you a real fan?", "why has this happened?"}.issubset(body_lines):
            return True

        markers = (
            "we actively prevent automated bots from accessing our site",
            "something went wrong. please try logging in through another device",
            "let us know what you were doing when this page came up",
            "plus your ip and request id found at the bottom of this page",
        )
        return any(marker in body for marker in markers)

    @staticmethod
    def _is_cloudflare_blocked(title: str, body: str) -> bool:
        markers = (
            "sorry, you have been blocked",
            "access denied",
            "error 1020",
            "cloudflare ray id",
        )
        return any(marker in title or marker in body for marker in markers)

    @staticmethod
    def _is_event_page_ready(page: Page, body: str) -> bool:
        url = page.url.lower()

        if "tix.axs.com" not in url or "/shop/search" not in url:
            return False

        markers = (
            "event date",
            "price range",
            "pick your tickets",
            "great tickets available",
        )
        return any(marker in body for marker in markers)

    async def _wait_map_loaded(self, page: Page, timeout: int = 30) -> None:
        logger.info("Waiting for ticket map...")

        loop = asyncio.get_running_loop()
        started_at = loop.time()
        clear_checks = 0

        while loop.time() - started_at < timeout:
            try:
                title = (await page.title()).lower()
            except Exception:
                title = ""

            try:
                body = (await page.locator("body").inner_text(timeout=2_000)).lower()
            except Exception:
                await asyncio.sleep(1)
                continue

            if self._is_axs_restricted(title, body):
                raise AXSRestrictedError("AXS restricted access while loading the event page.")

            if self._is_axs_bot_blocked(title, body):
                raise AXSAntiBotBlockedError("AXS anti-bot blocked access while loading the event page.")

            if self._is_cloudflare_blocked(title, body):
                raise CloudflareBlockedError("Cloudflare blocked access while loading the event page.")

            if "loading map..." in body:
                clear_checks = 0
            else:
                clear_checks += 1
                if clear_checks >= 3:
                    logger.success("Ticket map loaded")
                    return

            await asyncio.sleep(1)

        raise ScraperTimeoutError(f"Ticket map did not load after {timeout} seconds.")

    @staticmethod
    async def _wait_page_loaded(page: Page) -> None:
        try:
            await page.wait_for_load_state("load", timeout=15_000)
        except PlaywrightTimeoutError:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            pass

    async def _save_screenshot(self, page: Page, failed: bool = False) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = self.failed_path if failed else self.success_path
        screenshot_path = folder / f"{timestamp}.png"

        await page.screenshot(path=str(screenshot_path), full_page=True)
        return screenshot_path

    @staticmethod
    def _is_navigation_error(message: str) -> bool:
        markers = (
            "execution context was destroyed",
            "frame was detached",
            "navigating",
            "navigation interrupted",
        )
        return any(marker in message for marker in markers)
