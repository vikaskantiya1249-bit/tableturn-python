"""Application settings.
Nothing is hard-coded; an env-file can feed it.
Every field here is listed in .env.example.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Upgrade = Literal["never", "when_nobody_larger_waits", "always"]


class Settings(BaseSettings):

    host: str = "127.0.0.1"    # bind every interface so the kitchen screen reaches it
    port: int = 8080

    database_url: str = Field(
        default="sqlite:///./tableturn_v2.db"
    )

    seed_dir: str = Field(
        default="seed"
    )

    default_quote_minutes: int = Field(
        default=40,
        ge=1,
    )

    small_party_upgrade: Upgrade = "when_nobody_larger_waits"    # may a party take a table with more seats than covers

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )