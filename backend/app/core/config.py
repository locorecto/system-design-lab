from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    app_name: str = "System Design Lab API"
    environment: str = "dev"
    default_sandbox_profile: str = "medium"
    max_run_duration_sec: int = Field(default=1800, ge=60)


settings = AppSettings()

