from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseModel):
    """Конфигурация агента"""

    LLM_NAME: str
    RATE_LIMIT_PER_MINUTE: int
    GOOGLE_API_KEY: str
    TAVILY_API_KEY: str


class ApiConfig(BaseModel):
    """Конфигурация API"""

    TITLE: str
    DESCRIPTION: str
    VERSION: str
    HOST: str
    PORT: int
    RELOAD: bool


class DatabaseConfig(BaseModel):
    """Конфигурация базы данных"""

    NAME: str
    USER: str
    PASSWORD: str
    HOST: str

    @property
    def URL(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:5432/{self.NAME}"


class Settings(BaseSettings):
    """Главные настройки приложения"""

    AGENT: AgentConfig
    DATABASE: DatabaseConfig
    API: ApiConfig

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        env_nested_max_split=1,
        extra="ignore",
    )


settings = Settings()
