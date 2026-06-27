from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qops_runtime_mode: str = "local"
    qops_paper_only: bool = True
    redis_url: str = "redis://localhost:6379/0"
    qops_api_port: int = 8000
    qops_mobile_notify_enabled: bool = False
    qops_mobile_notify_channel: str = "local"


settings = RuntimeSettings()
