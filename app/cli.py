from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    dry_run: bool = True
    headless: bool = False
    browser_profile_dir: str = ".browser-profile"
    log_level: str = "INFO"
    approval_required: bool = True
    # End-to-end agent execution is opt-in. The scheduled runner explicitly enables it.
    agent_enabled: bool = Field(
        default=False,
        validation_alias="LINKEDIN_AGENT_ENABLED",
    )
    telegram_notifications_enabled: bool = Field(
        default=False,
        validation_alias="TELEGRAM_NOTIFICATIONS_ENABLED",
    )
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_chat_id: str | None = Field(
        default=None,
        validation_alias="TELEGRAM_CHAT_ID",
    )
    llm_provider: str = "none"
    openai_api_key: str | None = None
    linkedin_base_url: str = "https://www.linkedin.com"

    @property
    def profile_path(self) -> Path:
        path = ROOT / self.browser_profile_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()
