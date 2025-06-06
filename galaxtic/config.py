from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordConfig(BaseModel):
    BOT_TOKEN: str
    BOT_OWNER_ID: str
    UNKNOWN_ERROR_WEBHOOK_URL: str
    SUGGESTION_WEBHOOK_URL: str
    TEST_GUILD_ID: int


class SurrealDBConfig(BaseModel):
    URL: str
    USERNAME: str
    PASSWORD: str
    NS: str
    DB: str


class CloudinaryConfig(BaseModel):
    CLOUD_NAME: str
    API_KEY: str
    API_SECRET: str


class AIConfig(BaseModel):
    TOGETHER_API_KEY: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"), env_nested_delimiter="__"
    )

    DISCORD: DiscordConfig
    SURREALDB: SurrealDBConfig
    CLOUDINARY: CloudinaryConfig
    AI: AIConfig
