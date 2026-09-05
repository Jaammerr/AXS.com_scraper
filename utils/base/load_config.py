import os
import yaml

from pathlib import Path
from typing import Any
from models import Config


class ConfigurationError(Exception):
    pass


class ConfigLoader:
    REQUIRED_PARAMS = {
        "application_settings",
        "cloak_browser_settings",
    }

    ENV_MAPPING = {
        "AXS_EVENT_PAGE": ("application_settings", "event_page"),
        "AXS_USE_PROXY": ("application_settings", "use_proxy"),
        "AXS_PROXY_CHECK_CONCURRENCY": (
            "application_settings",
            "proxy_check_concurrency",
        ),
        "AXS_PROXY_FILE": ("application_settings", "proxy_file"),
        "CLOAKBROWSER_HEADLESS": (
            "cloak_browser_settings",
            "headless",
        ),
        "CLOAKBROWSER_VERSION": (
            "cloak_browser_settings",
            "version",
        ),
        "CLOAKBROWSER_LICENSE_KEY": (
            "cloak_browser_settings",
            "license_key",
        ),
    }

    def __init__(
        self,
        base_path: str | Path | None = None,
    ) -> None:
        self.base_path = Path(base_path or os.getcwd())
        self.config_path = self.base_path / "config"
        self.data_path = self.config_path / "data"
        self.settings_path = self.config_path / "settings.yaml"

    def load(self) -> Config:
        params = self._load_yaml()
        self._apply_env(params)

        application_settings = params.get(
            "application_settings",
            {},
        )

        cloak_browser_settings = params.get(
            "cloak_browser_settings",
            {}
        )

        if not cloak_browser_settings.get("license_key"):
            raise ConfigurationError("license_key is required. ")

        if not application_settings.get("event_page"):
            raise ConfigurationError("Event page URL is not specified.")

        try:
            return Config(**params)

        except Exception as exc:
            raise ConfigurationError(
                f"Invalid configuration: {exc}"
            ) from exc

    def _load_yaml(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            raise ConfigurationError(
                f"Config file not found: {self.settings_path}"
            )

        try:
            content = self.settings_path.read_text(
                encoding="utf-8"
            )

            params = yaml.safe_load(content)

        except OSError as exc:
            raise ConfigurationError(
                f"Failed to read config: {exc}"
            ) from exc

        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Invalid YAML: {exc}"
            ) from exc

        if not isinstance(params, dict):
            raise ConfigurationError(
                "Config must contain a YAML object."
            )

        missing = self.REQUIRED_PARAMS - params.keys()

        if missing:
            raise ConfigurationError(
                f"Missing required fields: "
                f"{', '.join(sorted(missing))}"
            )

        return params

    def _apply_env(
        self,
        params: dict[str, Any],
    ) -> None:
        for env_name, path in self.ENV_MAPPING.items():
            value = os.getenv(env_name)

            if value is None:
                continue

            section, field = path
            params.setdefault(section, {})[field] = value
            