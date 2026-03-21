from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    encryption_key: str

    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    slot_duration_minutes: int = 30

    model_config = {"env_file": ".env"}


settings = Settings()
