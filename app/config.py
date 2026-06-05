from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.url import normalize_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    database_url: str
    review_group_id: int = 0
    return_group_id: int = 0
    admin_ids: str = ""
    setup_mode: bool = True
    tz: str = "Asia/Tashkent"
    daily_report_hour: int = 18
    daily_report_minute: int = 0

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, v: object) -> str:
        return normalize_database_url(str(v or ""))

    def admin_id_set(self) -> set[int]:
        out: set[int] = set()
        for part in self.admin_ids.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                out.add(int(part))
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
