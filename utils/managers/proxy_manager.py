import asyncio

from collections import deque
from pathlib import Path

from better_proxy import Proxy
from loguru import logger

from utils.checkers import ProxyChecker


class ProxyManager:
    def __init__(
        self,
        proxy_file: str | Path,
        proxy_checker: ProxyChecker,
        check_uniqueness: bool = True,
    ) -> None:
        self.proxy_file = Path(proxy_file)
        self.proxy_checker = proxy_checker
        self.check_uniqueness = check_uniqueness

        self.proxies: deque[Proxy] = deque()
        self.active_proxies: set[Proxy] = set()
        self.configured_proxies: set[Proxy] = set()
        self.proxy_ips: dict[Proxy, str] = {}

        self.lock = asyncio.Lock()
        self._last_modified: int | None = None

    def _read_proxies(self) -> list[Proxy]:
        if not self.proxy_file.exists():
            raise FileNotFoundError(f"Proxy file not found: {self.proxy_file}")

        lines = self.proxy_file.read_text(encoding="utf-8").splitlines()
        proxies: list[Proxy] = []

        for line in lines:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if not line.startswith(("http://", "https://", "socks5://")):
                continue

            try:
                proxies.append(Proxy.from_str(line))
            except Exception:
                continue

        return proxies

    async def reload_proxies(self) -> bool:
        try:
            proxies = self._read_proxies()
        except Exception as exc:
            logger.error(f"Failed to read proxy file: {exc}")
            return False

        if not proxies:
            logger.error("Proxy file contains no valid proxies; keeping current pool")
            return False

        logger.info(f"Checking {len(proxies)} proxies...")

        try:
            results = await self.proxy_checker.check_many(proxies)
        except Exception as exc:
            logger.error(f"Proxy validation failed: {exc}")
            return False

        valid_results = [result for result in results if result.is_valid and result.ip]

        if not valid_results:
            logger.error("No working proxies found; keeping current pool")
            return False

        valid_proxies = [result.proxy for result in valid_results]

        async with self.lock:
            self.configured_proxies = set(valid_proxies)
            self.proxy_ips = {result.proxy: result.ip for result in valid_results if result.ip}
            self.proxies = deque(proxy for proxy in valid_proxies if proxy not in self.active_proxies)

        logger.success(f"Proxy pool updated: {len(valid_proxies)}/{len(proxies)} valid | {len(self.proxies)} available")
        return True

    async def get_proxy(
        self,
        exclude: set[Proxy | str] | None = None,
        wait_if_empty: bool = True,
    ) -> tuple[str, str] | None:
        excluded = {self._ensure_proxy(proxy) for proxy in (exclude or set())}

        while True:
            async with self.lock:
                pool_size = len(self.proxies)

                for _ in range(pool_size):
                    proxy = self.proxies.popleft()

                    if proxy in excluded:
                        self.proxies.append(proxy)
                        continue

                    if self.check_uniqueness and proxy in self.active_proxies:
                        continue

                    proxy_ip = self.proxy_ips.get(proxy)
                    if not proxy_ip:
                        continue

                    if self.check_uniqueness:
                        self.active_proxies.add(proxy)

                    return proxy.as_url, proxy_ip

            if not wait_if_empty:
                return None

            logger.warning("No available proxies; waiting for proxy pool...")
            await asyncio.sleep(5)

    async def release_proxy(self, proxy: Proxy | str) -> None:
        proxy = self._ensure_proxy(proxy)

        async with self.lock:
            self.active_proxies.discard(proxy)

            if proxy in self.configured_proxies and proxy not in self.proxies:
                self.proxies.append(proxy)

    async def remove_proxy(self, proxy: Proxy | str) -> bool:
        proxy = self._ensure_proxy(proxy)

        async with self.lock:
            removed = False

            try:
                self.proxies.remove(proxy)
                removed = True
            except ValueError:
                pass

            if proxy in self.active_proxies:
                self.active_proxies.remove(proxy)
                removed = True

            if proxy in self.configured_proxies:
                self.configured_proxies.remove(proxy)
                removed = True

            if proxy in self.proxy_ips:
                self.proxy_ips.pop(proxy)
                removed = True

            return removed

    async def watch_proxy_file(self, interval: float = 2.0) -> None:
        logger.info("Proxy file watcher started")

        while True:
            try:
                modified = self.proxy_file.stat().st_mtime_ns

                if self._last_modified is None:
                    self._last_modified = modified
                elif modified != self._last_modified:
                    logger.info("Proxy file changed, reloading proxy pool...")
                    await asyncio.sleep(0.5)
                    if await self.reload_proxies():
                        self._last_modified = self.proxy_file.stat().st_mtime_ns
                    else:
                        logger.warning("Proxy pool reload failed; watcher will retry")

            except FileNotFoundError:
                logger.error(f"Proxy file not found: {self.proxy_file}")
            except asyncio.CancelledError:
                logger.info("Proxy file watcher stopped")
                raise
            except Exception as exc:
                logger.exception(f"Proxy file watcher failed: {exc}")

            await asyncio.sleep(interval)

    async def initialize(self) -> bool:
        if not await self.reload_proxies():
            return False

        try:
            self._last_modified = self.proxy_file.stat().st_mtime_ns
        except OSError:
            pass

        return True

    @staticmethod
    def _ensure_proxy(proxy: Proxy | str) -> Proxy:
        if isinstance(proxy, Proxy):
            return proxy

        return Proxy.from_str(proxy)
