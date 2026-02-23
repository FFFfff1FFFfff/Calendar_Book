from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    nylas_client_id: str
    nylas_api_key: str
    nylas_api_uri: str = "https://api.us.nylas.com"
    nylas_callback_uri: str

    encryption_key: str

    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    slot_duration_minutes: int = 30

    model_config = {"env_file": ".env"}


settings = Settings()
