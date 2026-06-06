from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.url import normalize_database_url, resolve_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    database_url: str = ""
    review_group_id: int = 0
    return_group_id: int = 0
    admin_ids: str = ""
    setup_mode: bool = True
    tz: str = "Asia/Tashkent"
    daily_report_hour: int = 18
    daily_report_minute: int = 0
    pending_refresh_seconds: int = 60

    @model_validator(mode="before")
    @classmethod
    def _fill_database_url(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        raw = str(data.get("database_url") or "").strip()
        if not raw:
            resolved = resolve_database_url()
            if resolved:
                data["database_url"] = resolved
        return data

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, v: object) -> str:
        s = str(v or "").strip()
        if s:
            return normalize_database_url(s)
        return resolve_database_url()

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
