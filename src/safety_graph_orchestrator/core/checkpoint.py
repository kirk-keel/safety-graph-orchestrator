import os
from pathlib import Path
import sqlite3
from typing import Optional
from langgraph.checkpoint.sqlite import SqliteSaver

# Allow our domain models in msgpack serialization
existing_allowed = os.environ.get("LANGGRAPH_ALLOWED_MSGPACK_MODULES", "")
if "safety_graph_orchestrator" not in existing_allowed:
    os.environ["LANGGRAPH_ALLOWED_MSGPACK_MODULES"] = (
        f"{existing_allowed},safety_graph_orchestrator.core.models" if existing_allowed else "safety_graph_orchestrator.core.models"
    )

DEFAULT_DB_PATH = Path(".checkpoints.db")


def get_sqlite_checkpointer(db_path: Optional[Path] = None) -> SqliteSaver:
    """Creates a persistent SQLite checkpointer for LangGraph state persistence."""
    target_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    saver = SqliteSaver(conn=conn)
    saver.setup()
    return saver
