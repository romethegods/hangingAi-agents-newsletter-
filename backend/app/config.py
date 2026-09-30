"""All configuration comes from environment variables, so the same image runs
on a laptop, Railway, or a Google Cloud VM without code changes."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hanging:hanging@localhost:5432/hanging"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # Public API rate limits, per client IP.
    rate_limit_enabled: bool = True
    rate_limit_per_minute: float = 120
    rate_limit_burst: int = 60
    rate_limit_search_per_minute: float = 30  # full-text search is the most expensive query
    rate_limit_search_burst: int = 10
    # Direct callers from these networks skip limits: our own web server calls the API
    # over the private Docker network. Public traffic arrives via Caddy with the real
    # client IP (X-Forwarded-For), so it is limited.
    rate_limit_exempt_networks: list[str] = [
        "127.0.0.0/8",
        "::1/128",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]

    # Scraper
    browser_headless: bool = True
    browser_sandbox: bool = True  # must be False when Chrome runs as root in a container
    browser_executable: str | None = None
    browser_max_tabs: int = 3
    scrape_min_interval_seconds: float = 2.0  # per domain, raised by robots.txt Crawl-delay

    # LLM enrichment (M2)
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-4-5-20251001"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        # Railway / Cloud SQL hand out plain postgres:// URLs.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
