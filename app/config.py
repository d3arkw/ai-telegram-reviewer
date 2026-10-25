from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LLM_PROVIDER: str = "gemini"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    ROUTERAI_API_KEY: str | None = None
    ROUTERAI_MODEL: str = "qwen/qwen3.7-flash"

    TELEGRAM_BOT_TOKEN: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def check_keys(self):
        if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY обязателен при LLM_PROVIDER=gemini")
        if self.LLM_PROVIDER == "routerai" and not self.ROUTERAI_API_KEY:
            raise ValueError("ROUTERAI_API_KEY обязателен при LLM_PROVIDER=routerai")
        return self


settings = Settings()
