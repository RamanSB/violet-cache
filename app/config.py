from functools import lru_cache
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # DB
    database_url: str

    my_google_user_id: str
    # Google OAuth
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str

    model_config = SettingsConfigDict(
        env_file="/Users/raman/Documents/Development/Projects/notes-lab/.env"
    )


settings = Settings()


@lru_cache
def get_settings():
    return Settings()
