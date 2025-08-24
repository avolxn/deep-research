from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GOOGLE_API_KEY: str
    TAVILY_API_KEY: str

    LLM_NAME: str = "gemini-2.0-flash"
    CHAT_DB_PATH: str = "data/chat_db.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Settings()

GOOGLE_API_KEY = config.GOOGLE_API_KEY
TAVILY_API_KEY = config.TAVILY_API_KEY

LLM_NAME = config.LLM_NAME
CHAT_DB_PATH = config.CHAT_DB_PATH
