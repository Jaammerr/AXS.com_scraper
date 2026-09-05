from urllib.parse import urlsplit


def mask_proxy(proxy: str) -> str:
    try:
        parsed = urlsplit(proxy)

        host = parsed.hostname or "unknown"
        port = f":{parsed.port}" if parsed.port else ""
        scheme = parsed.scheme or "proxy"

        if not parsed.username:
            return f"{scheme}://{host}{port}"

        username = parsed.username

        return f"{scheme}://{username}:***@{host}{port}"

    except Exception:
        return "proxy://***"
