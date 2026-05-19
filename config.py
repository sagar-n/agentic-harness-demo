"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    reasoning_model: str = "qwen3:14b"
    vision_model: str = "qwen2.5-vl:7b"
    fast_model: str = "qwen3:4b"

    # --- oMLX ---
    omlx_enabled: bool = False
    omlx_base_url: str = "http://localhost:8000"
    omlx_api_key: str = ""

    # --- Storage ---
    data_dir: Path = Path.home() / ".trademind"
    db_path: Path | None = None  # defaults to data_dir / "trademind.db"

    # --- Browser ---
    tradingview_url: str = "https://www.tradingview.com"
    browser_headless: bool = False
    browser_screenshot_dir: Path | None = None  # defaults to data_dir / "screenshots"

    # --- Langfuse ---
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://us.cloud.langfuse.com"

    # --- Retry ---
    min_confidence_threshold: float = 0.6
    max_retries: int = 2

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    def model_post_init(self, _ctx) -> None:
        if self.db_path is None:
            self.db_path = self.data_dir / "trademind.db"
        if self.browser_screenshot_dir is None:
            self.browser_screenshot_dir = self.data_dir / "screenshots"

    @property
    def ollama_chat_url(self) -> str:
        return f"{self.ollama_base_url}/api/chat"

    @property
    def ollama_generate_url(self) -> str:
        return f"{self.ollama_base_url}/api/generate"


settings = Settings()
