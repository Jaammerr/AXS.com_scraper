from pathlib import Path
from utils import ConfigLoader, ProxyChecker, ProxyManager


config_loader = ConfigLoader()
config = config_loader.load()

proxy_checker = ProxyChecker(
    timeout=10,
    check_concurrency=(
        config.application_settings.proxy_check_concurrency
    ),
)

proxy_file = Path(
    config.application_settings.proxy_file
)

if not proxy_file.is_absolute():
    proxy_file = config_loader.base_path / proxy_file

proxy_manager = ProxyManager(
    check_uniqueness=False,
    proxy_file=proxy_file,
    proxy_checker=proxy_checker,
)
