import asyncio
import aiohttp

from aiohttp_socks import ProxyConnector
from better_proxy import Proxy

from models import ProxyCheckResult


class ProxyChecker:
    def __init__(self, check_concurrency: int, timeout: float = 10) -> None:
        self.check_concurrency = check_concurrency
        self.timeout = timeout
        self._sem = asyncio.Semaphore(check_concurrency)

    async def check(self, proxy: Proxy) -> ProxyCheckResult:
        try:
            connector = ProxyConnector.from_url(proxy.as_url)
            timeout = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get("https://api.ipify.org?format=json") as response:
                    response.raise_for_status()
                    data = await response.json()

            ip = data.get("ip")
            if not ip:
                return ProxyCheckResult(proxy=proxy, is_valid=False, error="Proxy IP was not returned")

            return ProxyCheckResult(proxy=proxy, is_valid=True, ip=ip)
        except Exception as exc:
            return ProxyCheckResult(proxy=proxy, is_valid=False, error=str(exc))

    async def check_many(self, proxies: list[Proxy]) -> list[ProxyCheckResult]:
        async def check_one(proxy: Proxy) -> ProxyCheckResult:
            async with self._sem:
                return await self.check(proxy)

        return await asyncio.gather(*(check_one(proxy) for proxy in proxies))
