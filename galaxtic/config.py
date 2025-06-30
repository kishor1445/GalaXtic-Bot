from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class DiscordConfig(BaseModel):
    BOT_TOKEN: str
    BOT_OWNER_ID: str
    UNKNOWN_ERROR_WEBHOOK_URL: str
    SUGGESTION_WEBHOOK_URL: str
    TEST_GUILD_ID: Optional[int] = None


class SurrealDBConfig(BaseModel):
    URL: str
    USERNAME: str
    PASSWORD: str
    NS: str
    DB: str


class SeafileConfig(BaseModel):
    SERVER_URL: str
    REPO_API_TOKEN: str


class AIConfig(BaseModel):
    TOGETHER_API_KEY: str


class WebshareProxyConfig(BaseModel):
    username: str
    password: str
    ip: str
    port: str

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"), env_nested_delimiter="__"
    )

    DISCORD: DiscordConfig
    SURREALDB: SurrealDBConfig
    SEAFILE: SeafileConfig
    AI: AIConfig
    COOKIES_FILE: Path = Path(".cookies.txt")
    WEBSHARE: WebshareProxyConfig | None = None
    
