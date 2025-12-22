"""
Embedding Client for Semantic Search in Agent Memory.

Provides vector embeddings using Azure OpenAI for:
- Semantic memory search (episodic, semantic, procedural)
- Similar experience retrieval
- Knowledge graph traversal by meaning
- Cross-agent knowledge sharing

Supports:
- Azure OpenAI text-embedding-ada-002 (1536 dimensions)
- Azure OpenAI text-embedding-3-small (1536 dimensions, better performance)
- Azure OpenAI text-embedding-3-large (3072 dimensions, highest quality)
- Batch processing for efficiency
- Local caching to reduce API calls
- Automatic chunking for long documents
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
import structlog
from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential

logger = structlog.get_logger()


class EmbeddingModel:
    """Supported embedding models."""
    ADA_002 = "text-embedding-ada-002"  # 1536 dims, $0.0001/1K tokens
    SMALL_3 = "text-embedding-3-small"  # 1536 dims, $0.00002/1K tokens (5x cheaper!)
    LARGE_3 = "text-embedding-3-large"  # 3072 dims, $0.00013/1K tokens (highest quality)


@dataclass
class EmbeddingResult:
    """Result from embedding operation."""
    text: str
    embedding: List[float]
    model: str
    dimensions: int
    tokens_used: int
    cached: bool = False


@dataclass
class SemanticSearchResult:
    """Result from semantic search."""
    text: str
    similarity: float
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class EmbeddingClient:
    """
    Client for generating embeddings using Azure OpenAI.

    Features:
    - Multiple model support (ada-002, 3-small, 3-large)
    - Batch processing for efficiency
    - Local LRU cache to avoid redundant API calls
    - Automatic text chunking for long documents
    - Cost tracking and optimization
    """

    def __init__(
        self,
        azure_endpoint: str,
        api_version: str = "2024-02-15-preview",
        model: str = EmbeddingModel.SMALL_3,
        use_managed_identity: bool = True,
        api_key: Optional[str] = None,
        max_cache_size: int = 10000,
        cache_ttl_hours: int = 24
    ):
        self.azure_endpoint = azure_endpoint
        self.api_version = api_version
        self.model = model
        self.max_cache_size = max_cache_size
        self.cache_ttl_hours = cache_ttl_hours

        # Model dimensions
        self.dimensions = {
            EmbeddingModel.ADA_002: 1536,
            EmbeddingModel.SMALL_3: 1536,
            EmbeddingModel.LARGE_3: 3072
        }[model]

        # Authentication
        if use_managed_identity:
            self.credential = DefaultAzureCredential()
            self.client = AsyncAzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_version=api_version,
                azure_ad_token_provider=self._get_token
            )
        else:
            if not api_key:
                raise ValueError("api_key required when not using managed identity")

            self.client = AsyncAzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_version=api_version,
                api_key=api_key
            )
            self.credential = None

        # Local cache (in-memory LRU)
        self._cache: Dict[str, Tuple[List[float], datetime]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Cost tracking
        self._total_tokens = 0
        self._total_cost = 0.0

    async def _get_token(self):
        """Get Azure AD token for managed identity."""
        if self.credential:
            token = await self.credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        return None

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text."""
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()

    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cache entry is still valid."""
        return datetime.utcnow() - timestamp < timedelta(hours=self.cache_ttl_hours)

    async def embed_text(
        self,
        text: str,
        use_cache: bool = True
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use local cache

        Returns:
            EmbeddingResult with vector and metadata
        """
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                embedding, timestamp = self._cache[cache_key]
                if self._is_cache_valid(timestamp):
                    self._cache_hits += 1
                    logger.debug("embedding_cache_hit", text_length=len(text))

                    return EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        model=self.model,
                        dimensions=self.dimensions,
                        tokens_used=0,
                        cached=True
                    )

        self._cache_misses += 1

        # Generate embedding via API
        try:
            response = await self.client.embeddings.create(
                input=text,
                model=self.model
            )

            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens

            # Update cache
            if use_cache and len(self._cache) < self.max_cache_size:
                cache_key = self._get_cache_key(text)
                self._cache[cache_key] = (embedding, datetime.utcnow())

            # Track cost
            self._total_tokens += tokens_used
            self._total_cost += self._calculate_cost(tokens_used)

            logger.debug(
                "embedding_generated",
                text_length=len(text),
                tokens=tokens_used,
                model=self.model
            )

            return EmbeddingResult(
                text=text,
                embedding=embedding,
                model=self.model,
                dimensions=self.dimensions,
                tokens_used=tokens_used,
                cached=False
            )

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e), text_length=len(text))
            raise

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
        use_cache: bool = True
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (max 2048 for Azure OpenAI)
            use_cache: Whether to use local cache

        Returns:
            List of EmbeddingResults
        """
        results = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Check cache first
            if use_cache:
                cached_results = []
                uncached_texts = []
                uncached_indices = []

                for idx, text in enumerate(batch):
                    cache_key = self._get_cache_key(text)
                    if cache_key in self._cache:
                        embedding, timestamp = self._cache[cache_key]
                        if self._is_cache_valid(timestamp):
                            cached_results.append((idx, EmbeddingResult(
                                text=text,
                                embedding=embedding,
                                model=self.model,
                                dimensions=self.dimensions,
                                tokens_used=0,
                                cached=True
                            )))
                            self._cache_hits += 1
                            continue

                    uncached_texts.append(text)
                    uncached_indices.append(idx)
                    self._cache_misses += 1

            else:
                uncached_texts = batch
                uncached_indices = list(range(len(batch)))
                cached_results = []

            # Generate embeddings for uncached texts
            if uncached_texts:
                try:
                    response = await self.client.embeddings.create(
                        input=uncached_texts,
                        model=self.model
                    )

                    tokens_used = response.usage.total_tokens
                    self._total_tokens += tokens_used
                    self._total_cost += self._calculate_cost(tokens_used)

                    # Process results
                    uncached_results = []
                    for idx, (text, data) in enumerate(zip(uncached_texts, response.data)):
                        embedding = data.embedding

                        # Update cache
                        if use_cache and len(self._cache) < self.max_cache_size:
                            cache_key = self._get_cache_key(text)
                            self._cache[cache_key] = (embedding, datetime.utcnow())

                        uncached_results.append((uncached_indices[idx], EmbeddingResult(
                            text=text,
                            embedding=embedding,
                            model=self.model,
                            dimensions=self.dimensions,
                            tokens_used=tokens_used // len(uncached_texts),  # Approximate per-text
                            cached=False
                        )))

                    logger.info(
                        "batch_embeddings_generated",
                        batch_size=len(uncached_texts),
                        tokens=tokens_used,
                        model=self.model
                    )

                except Exception as e:
                    logger.error("batch_embedding_failed", error=str(e), batch_size=len(uncached_texts))
                    raise

            # Combine cached and uncached results in original order
            batch_results = sorted(cached_results + uncached_results, key=lambda x: x[0])
            results.extend([result for _, result in batch_results])

        return results

    async def embed_chunks(
        self,
        text: str,
        chunk_size: int = 8000,  # ~8K tokens (safe for all models)
        overlap: int = 200
    ) -> List[EmbeddingResult]:
        """
        Chunk long text and generate embeddings for each chunk.

        Args:
            text: Long text to chunk and embed
            chunk_size: Max characters per chunk
            overlap: Character overlap between chunks

        Returns:
            List of EmbeddingResults for each chunk
        """
        if len(text) <= chunk_size:
            return [await self.embed_text(text)]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)

                if break_point > chunk_size - 500:  # Within reasonable distance
                    end = start + break_point + 1
                    chunk = text[start:end]

            chunks.append(chunk)
            start = end - overlap

        logger.info("text_chunked", total_length=len(text), chunks=len(chunks))

        # Embed all chunks
        return await self.embed_batch(chunks)

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Returns value between -1 (opposite) and 1 (identical).
        """
        import math

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(b * b for b in embedding2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    async def semantic_search(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
        text_field: str = "text",
        embedding_field: Optional[str] = None
    ) -> List[SemanticSearchResult]:
        """
        Perform semantic search over candidate texts.

        Args:
            query: Search query
            candidates: List of dicts with text (and optionally pre-computed embeddings)
            top_k: Number of top results to return
            text_field: Field name containing text
            embedding_field: Field name containing pre-computed embedding (optional)

        Returns:
            List of top-k SemanticSearchResults sorted by similarity
        """
        # Embed query
        query_result = await self.embed_text(query)
        query_embedding = query_result.embedding

        # Embed candidates (or use pre-computed)
        candidate_embeddings = []

        for candidate in candidates:
            if embedding_field and embedding_field in candidate:
                # Use pre-computed embedding
                candidate_embeddings.append(candidate[embedding_field])
            else:
                # Generate embedding
                text = candidate.get(text_field, "")
                result = await self.embed_text(text)
                candidate_embeddings.append(result.embedding)

        # Calculate similarities
        results = []
        for candidate, embedding in zip(candidates, candidate_embeddings):
            similarity = self.cosine_similarity(query_embedding, embedding)

            results.append(SemanticSearchResult(
                text=candidate.get(text_field, ""),
                similarity=similarity,
                metadata=candidate,
                embedding=embedding
            ))

        # Sort by similarity and return top-k
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]

    def _calculate_cost(self, tokens: int) -> float:
        """Calculate API cost based on tokens."""
        # Pricing as of Dec 2025
        pricing = {
            EmbeddingModel.ADA_002: 0.0001 / 1000,   # $0.0001 per 1K tokens
            EmbeddingModel.SMALL_3: 0.00002 / 1000,  # $0.00002 per 1K tokens
            EmbeddingModel.LARGE_3: 0.00013 / 1000   # $0.00013 per 1K tokens
        }

        return tokens * pricing[self.model]

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 6),
            "avg_cost_per_1k_tokens": round(self._calculate_cost(1000), 6)
        }

    def clear_cache(self):
        """Clear embedding cache."""
        self._cache.clear()
        logger.info("embedding_cache_cleared")

    async def close(self):
        """Close client connections."""
        await self.client.close()

        if self.credential:
            await self.credential.close()

        logger.info("embedding_client_closed")


# Factory function
def create_embedding_client(
    azure_endpoint: str,
    model: str = EmbeddingModel.SMALL_3,
    use_managed_identity: bool = True,
    api_version: str = "2024-02-15-preview"
) -> EmbeddingClient:
    """Create an EmbeddingClient instance."""
    return EmbeddingClient(
        azure_endpoint=azure_endpoint,
        model=model,
        use_managed_identity=use_managed_identity,
        api_version=api_version
    )
