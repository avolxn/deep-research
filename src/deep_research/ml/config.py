from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearcherModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.3


class SummarizationModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.2


class ReportModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.5


class SupervisorModelConfig(BaseModel):
    model_name: str = "gpt-oss-120b"
    temperature: float = 0.3


class Config(BaseSettings):
    research_model: ResearcherModelConfig = ResearcherModelConfig()
    summarization_model: SummarizationModelConfig = SummarizationModelConfig()
    report_model: ReportModelConfig = ReportModelConfig()
    supervisor_model: SupervisorModelConfig = SupervisorModelConfig()

    MAX_RESEARCHER_ITERATIONS: int = 6
    MAX_CONCURRENT_RESEARCH_UNITS: int = 3
    MAX_TOOL_CALL_ITERATIONS: int = 10
    MAX_TASKS_PER_ITERATION: int = 3
    MIN_CONTENT_LENGTH: int = 100

    YANDEX_GPT_API_KEY: str
    YANDEX_GPT_FOLDER_ID: str
    TAVILY_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()
