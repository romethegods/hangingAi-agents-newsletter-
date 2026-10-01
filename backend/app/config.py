"""All configuration comes from environment variables, so the same image runs
on a laptop, Railway, or a Google Cloud VM without code changes."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hanging:hanging@localhost:5432/hanging"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # Accounts & the daily brief
    site_url: str = "http://localhost:3000"  # links in emails point here
    # Signs unsubscribe links. MUST be a long random value in production.
    secret_key: str = DEV_SECRET
    login_link_minutes: int = 20
    session_days: int = 30
    guest_session_days: int = 365  # guests have no email to sign back in with, so keep them longer
    # Accounts allowed to use /moderate (must have added this email).
    admin_emails: list[str] = []
    # "outbox" writes .eml files to outbox_dir (development); "smtp" sends for real.
    email_backend: str = "outbox"
    outbox_dir: str = "outbox"
    email_from: str = "HangingAi <brief@hangingai.com>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None

    # Public API rate limits, per client IP.
    rate_limit_enabled: bool = True
    rate_limit_per_minute: float = 120
    rate_limit_burst: int = 60
    rate_limit_search_per_minute: float = 30  # full-text search is the most expensive query
    rate_limit_search_burst: int = 10
    # Sign-in emails: per client, low, since each request sends mail.
    rate_limit_auth_per_minute: float = 5
    rate_limit_auth_burst: int = 5
    # Community writes, per visitor. Guest creation is hourly: it mints identities.
    rate_limit_guest_per_hour: float = 10
    rate_limit_write_per_minute: float = 6
    rate_limit_write_burst: int = 3
    rate_limit_vote_per_minute: float = 60
    rate_limit_vote_burst: int = 30
    rate_limit_arena_per_minute: float = 6  # each battle calls two models
    rate_limit_arena_burst: int = 3
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

    # LLMs (Arena now, enrichment in M2)
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-4-5"
    hf_token: str | None = None  # Hugging Face inference router, for the open models

    # Arena: blind side-by-side model battles
    arena_dev_models: bool | None = None  # free local stand-ins; default: on for localhost only
    arena_disabled_models: list[str] = []
    arena_battles_per_day: int = 20  # per visitor
    arena_daily_budget_usd: float = 5.0  # hard stop for the whole site
    arena_max_prompt_chars: int = 2000
    arena_max_output_tokens: int = 1024  # per answer; keeps battles quick and cheap

    @model_validator(mode="after")
    def _dev_models_on_localhost_only(self) -> "Settings":
        if self.arena_dev_models is None:
            self.arena_dev_models = "localhost" in self.site_url or "127.0.0.1" in self.site_url
        return self

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        # Unsubscribe links are HMAC-signed; an empty or well-known key makes them forgeable.
        if self.site_url.startswith("https://") and self.secret_key in ("", DEV_SECRET):
            raise ValueError("SECRET_KEY must be set to a long random value in production")
        return self

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
