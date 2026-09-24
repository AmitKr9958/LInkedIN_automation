from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    dry_run: bool = True
    headless: bool = False
    browser_profile_dir: str = ".browser-profile"
    log_level: str = "INFO"
    approval_required: bool = True
    llm_provider: str = "none"
    openai_api_key: str | None = None
    linkedin_base_url: str = "https://www.linkedin.com"

    @property
    def profile_path(self) -> Path:
        path = ROOT / self.browser_profile_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

settings = Settings()
