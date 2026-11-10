"""Application settings.
Nothing is hard-coded.
Every field has a default; the environment can change it.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )