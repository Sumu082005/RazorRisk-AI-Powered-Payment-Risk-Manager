"""Application Configuration Layer using Pydantic Settings."""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings with environment variable bindings."""
    
    RAZORRISK_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Razorpay API Credentials (Test Mode)
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_key_id"
    RAZORPAY_KEY_SECRET: str = "placeholder_key_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "placeholder_webhook_secret"
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    
    # Storage & Model Artifact Paths
    SQLITE_DB_PATH: str = "storage/audit.db"
    MODEL_ARTIFACT_PATH: str = "models/razorrisk_random_forest_pipeline.joblib"
    POLICY_CONFIG_PATH: str = "razorrisk/config/policy_config.json"
    
    # Pydantic Settings Config
    model_config = SettingsConfigDict(
        env_file=(".env", "app/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def is_production(self) -> bool:
        return self.RAZORRISK_ENV.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
