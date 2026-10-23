from enum import Enum
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    """Enterprise configuration for Safety Graph Orchestrator."""

    model_config = SettingsConfigDict(
        env_prefix="SAFETY_GRAPH_",
        env_file=".env",
        extra="ignore",
    )

    # General
    app_name: str = "safety-graph-orchestrator"
    app_version: str = "0.1.0"
    log_level: LogLevel = LogLevel.INFO

    # LLM Settings (Local Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 60.0
    use_mock_llm_fallback: bool = True  # Automatically fall back to deterministic mock if Ollama unreachable

    # ChromaDB & Vector Retrieval
    chroma_persist_dir: Path = Path(".chromadb")
    chroma_collection_name: str = "safety_sops_and_regulations"
    retrieval_top_k: int = 4
    similarity_threshold: float = 0.70

    # Risk & Escalation Thresholds
    auto_escalate_critical: bool = True
    max_rca_depth: int = 5


settings = Settings()
