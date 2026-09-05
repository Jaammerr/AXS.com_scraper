from dataclasses import dataclass
from better_proxy import Proxy


@dataclass(slots=True)
class ProxyCheckResult:
    proxy: Proxy
    is_valid: bool
    ip: str | None = None
    error: str | None = None
