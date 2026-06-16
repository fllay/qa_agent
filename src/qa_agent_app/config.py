from functools import lru_cache
from pathlib import Path
import glob
import os
import shutil

from pydantic import AliasChoices, Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_graphify_bin(command: str) -> str:
    value = command.strip()
    if value.lower() != "auto":
        return value or "graphify"

    path_command = shutil.which("graphify")
    if path_command:
        return path_command

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            pattern = os.path.join(appdata, "Python", "Python*", "Scripts", "graphify.exe")
            candidates = sorted(glob.glob(pattern), reverse=True)
            for candidate in candidates:
                if os.path.isfile(candidate):
                    return candidate

    return "graphify"


class Settings(BaseSettings):
    data_dir: Path = Field(default=Path("data"), validation_alias=AliasChoices("QA_AGENT_DATA_DIR", "DATA_DIR"))
    database_path: Path = Field(
        default=Path("data/qa_agent.sqlite"),
        validation_alias=AliasChoices("QA_AGENT_DATABASE_PATH", "DATABASE_PATH"),
    )
    graphify_bin: str = Field(default="auto", validation_alias=AliasChoices("GRAPHIFY_BIN", "QA_AGENT_GRAPHIFY_BIN"))
    graphify_timeout_seconds: int = Field(
        default=1800,
        validation_alias=AliasChoices("GRAPHIFY_TIMEOUT_SECONDS", "QA_AGENT_GRAPHIFY_TIMEOUT_SECONDS"),
    )
    github_token: str | None = Field(default=None, validation_alias=AliasChoices("GITHUB_TOKEN", "QA_AGENT_GITHUB_TOKEN"))
    github_max_pages: int = Field(
        default=10,
        validation_alias=AliasChoices("GITHUB_MAX_PAGES", "QA_AGENT_GITHUB_MAX_PAGES"),
    )
    github_per_page: int = Field(
        default=100,
        validation_alias=AliasChoices("GITHUB_PER_PAGE", "QA_AGENT_GITHUB_PER_PAGE"),
    )
    llm_provider: str = Field(default="local", validation_alias=AliasChoices("QA_AGENT_LLM_PROVIDER", "LLM_PROVIDER"))
    local_llm_base_url: str = Field(
        default="http://127.0.0.1:11434/v1",
        validation_alias=AliasChoices("QA_AGENT_LOCAL_LLM_BASE_URL", "LOCAL_LLM_BASE_URL"),
    )
    local_llm_api_key: str = Field(
        default="local",
        validation_alias=AliasChoices("QA_AGENT_LOCAL_LLM_API_KEY", "LOCAL_LLM_API_KEY"),
    )
    local_llm_model: str = Field(
        default="llama3.1:8b",
        validation_alias=AliasChoices("QA_AGENT_LOCAL_LLM_MODEL", "LOCAL_LLM_MODEL"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "QA_AGENT_OPENROUTER_API_KEY"),
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("OPENROUTER_BASE_URL", "QA_AGENT_OPENROUTER_BASE_URL"),
    )
    openrouter_main_model: str = Field(
        default="openrouter/auto",
        validation_alias=AliasChoices("OPENROUTER_MAIN_MODEL", "QA_AGENT_OPENROUTER_MAIN_MODEL"),
    )
    openrouter_reserve_model_1: str = Field(
        default="openai/gpt-4o-mini",
        validation_alias=AliasChoices("OPENROUTER_RESERVE_MODEL_1", "QA_AGENT_OPENROUTER_RESERVE_MODEL_1"),
    )
    openrouter_reserve_model_2: str = Field(
        default="google/gemini-flash-1.5",
        validation_alias=AliasChoices("OPENROUTER_RESERVE_MODEL_2", "QA_AGENT_OPENROUTER_RESERVE_MODEL_2"),
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_adaptive_graphify_bin(self) -> "Settings":
        self.graphify_bin = resolve_graphify_bin(self.graphify_bin)
        return self

    @property
    def topics_dir(self) -> Path:
        return self.data_dir / "topics"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.topics_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
