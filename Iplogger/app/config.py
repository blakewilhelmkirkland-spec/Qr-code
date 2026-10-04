from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite+aiosqlite:///./data/iplogger.db", alias="DATABASE_URL")
    trusted_proxies: str = Field(default="127.0.0.1/32,::1/128", alias="TRUSTED_PROXIES")
    geoip_db: str = Field(default="", alias="GEOIP_DB")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    admin_token: str = Field(default="change-me-please", alias="ADMIN_TOKEN")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("rate_limit_per_minute")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be > 0")
        return v

    @property
    def trusted_proxy_list(self) -> List[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()