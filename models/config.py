from pydantic import BaseModel, Field


class ApplicationSettings(BaseModel):
    event_page: str
    use_proxy: bool
    proxy_check_concurrency: int = Field(gt=0)
    proxy_file: str = "config/data/proxies.txt"


class CloakBrowserSettings(BaseModel):
    headless: bool
    version: str | None = None
    license_key: str


class Config(BaseModel):
    application_settings: ApplicationSettings
    cloak_browser_settings: CloakBrowserSettings
