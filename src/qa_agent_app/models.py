from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TopicStatus = Literal["new", "ready", "indexing", "error"]
SourceKind = Literal["github", "local_path", "upload"]


class Topic(BaseModel):
    id: str
    name: str
    description: str = ""
    status: TopicStatus = "new"
    progress_percent: int = 0
    progress_label: str = ""
    graph_path: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class ChatThread(BaseModel):
    id: str
    topic_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadCreate(BaseModel):
    title: str = Field(default="New thread", min_length=1, max_length=120)


class IngestRequest(BaseModel):
    kind: SourceKind
    value: str


class IngestResult(BaseModel):
    topic: Topic
    message: str


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    max_context_items: int = Field(default=8, ge=1, le=30)


class Citation(BaseModel):
    label: str
    path: str | None = None
    score: float = 0


class QuestionResponse(BaseModel):
    topic_id: str
    question: str
    answer: str
    citations: list[Citation]
    context_items: list[str]


class LlmSettings(BaseModel):
    provider: Literal["local", "openrouter"] = "local"
    local_base_url: str = "http://127.0.0.1:11434/v1"
    local_api_key: str = "local"
    local_model: str = "llama3.1:8b"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_main_model: str = "openrouter/auto"
    openrouter_reserve_model_1: str = "openai/gpt-4o-mini"
    openrouter_reserve_model_2: str = "google/gemini-flash-1.5"
