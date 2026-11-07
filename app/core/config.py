from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OrderFlow API"
    environment: str = "development"
    secret_key: str = "dev-only-orderflow-secret-key-please-change"
    access_token_expire_minutes: int = 60
    database_url: str = "sqlite:///./orderflow.db"
    payment_provider: str = "mock"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @model_validator(mode="after")
    def validate_production_secret(self):
        if self.environment.lower() in {"prod", "production"}:
            if len(self.secret_key) < 32 or any(word in self.secret_key.lower() for word in ("replace", "change-me", "local-dev", "development-only")):
                raise ValueError("Set SECRET_KEY to a unique random value of at least 32 characters in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
