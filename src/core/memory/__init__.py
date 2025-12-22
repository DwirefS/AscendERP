"""
Memory substrate for ANTS agents.
Provides episodic, semantic, procedural, and model memory with vector embeddings.
"""
from src.core.memory.substrate import (
    MemorySubstrate,
    MemoryConfig,
    MemoryEntry,
    MemoryType
)
from src.core.memory.database import DatabaseClient
from src.core.memory.embedding_client import (
    EmbeddingClient,
    EmbeddingModel,
    EmbeddingResult,
    SemanticSearchResult,
    create_embedding_client
)

__all__ = [
    "MemorySubstrate",
    "MemoryConfig",
    "MemoryEntry",
    "MemoryType",
    "DatabaseClient",
    "EmbeddingClient",
    "EmbeddingModel",
    "EmbeddingResult",
    "SemanticSearchResult",
    "create_embedding_client"
]
