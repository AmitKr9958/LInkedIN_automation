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
    # Final profile writes require a separate explicit opt-in in addition to
    # the dashboard approval. Scheduled optimizer runs remain read-only.
    linkedin_profile_write_enabled: bool = Field(
        default=False,
        validation_alias="LINKEDIN_PROFILE_WRITE_ENABLED",
    )
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
    llm_provider: str = Field(default="none", validation_alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="https://openrouter.ai/api/v1", validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="openrouter/auto", validation_alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    nine_router_api_key: str | None = Field(default=None, validation_alias="NINE_ROUTER_API_KEY")
    llm_timeout_seconds: int = Field(default=60, validation_alias="LLM_TIMEOUT_SECONDS")
    llm_http_referer: str = Field(default="http://127.0.0.1:8765", validation_alias="LLM_HTTP_REFERER")
    llm_app_name: str = Field(default="LinkedIn Agent Control Center", validation_alias="LLM_APP_NAME")
    openai_api_key: str | None = None
    linkedin_base_url: str = "https://www.linkedin.com"
    # Use the user's authenticated profile URL for profile reads. This is
    # intentionally read-only and prevents the optimizer from opening the
    # generic /in/ landing route.
    profile_url: str = Field(
        default="https://www.linkedin.com/in/amit-kumar-272071153/",
        validation_alias="PROFILE_URL",
    )

    @property
    def profile_path(self) -> Path:
        path = ROOT / self.browser_profile_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()
if not settings.llm_api_key:
    if settings.llm_provider.lower() == "openrouter":
        settings.llm_api_key = settings.openrouter_api_key
    elif settings.llm_provider.lower() == "9router":
        settings.llm_api_key = settings.nine_router_api_key
