from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearchModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.3
    max_tokens: int = 16384


class CompressionModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.1
    max_tokens: int = 8192


class SummarizationModelConfig(BaseModel):
    model_name: str = "gpt-oss-20b"
    temperature: float = 0.3
    max_tokens: int = 4096


class ReportModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.7
    max_tokens: int = 16384


class Config(BaseSettings):
    """Настройки агента"""

    research_model: ResearchModelConfig = ResearchModelConfig()
    compression_model: CompressionModelConfig = CompressionModelConfig()
    summarization_model: SummarizationModelConfig = SummarizationModelConfig()
    report_model: ReportModelConfig = ReportModelConfig()

    MAX_RESEARCHER_ITERATIONS: int = 6
    MAX_CONCURRENT_RESEARCH_UNITS: int = 3
    MAX_TOOL_CALL_ITERATIONS: int = 10

    YANDEX_GPT_API_KEY: str
    YANDEX_GPT_FOLDER_ID: str
    TAVILY_API_KEY: str

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()
