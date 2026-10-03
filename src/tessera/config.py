from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from the environment, never from code."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nebius_api_key: str = Field(..., alias="NEBIUS_API_KEY")
    nebius_base_url: str = Field(
        "https://api.tokenfactory.nebius.com/v1", alias="NEBIUS_BASE_URL"
    )
    data_dir: Path = Field(Path("./data"), alias="TESSERA_DATA_DIR")
    # Public-demo spend control. ~$0.035 a session, $50 of credits, live until
    # 2026-12-15: half a dollar a day is ~14 sessions and leaves headroom.
    daily_usd: float = Field(0.50, alias="TESSERA_DAILY_USD")
    calls_per_window: int = Field(6, alias="TESSERA_CALLS_PER_WINDOW")
    window_seconds: float = Field(600, alias="TESSERA_WINDOW_SECONDS")
    tavily_api_key: str | None = Field(None, alias="TAVILY_API_KEY")

    @property
    def telemetry_db(self) -> Path:
        return self.data_dir / "telemetry.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
