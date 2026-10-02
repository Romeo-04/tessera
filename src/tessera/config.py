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

    @property
    def telemetry_db(self) -> Path:
        return self.data_dir / "telemetry.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
