"""
Example: Semantic Search in Agent Memory with Embeddings.

Demonstrates how agents use Azure OpenAI embeddings for:
- Finding similar past experiences (episodic memory)
- Knowledge retrieval by meaning (semantic memory)
- Discovering relevant procedures (procedural memory)
- Cross-agent knowledge sharing
"""
import asyncio
from datetime import datetime

from src.core.memory import (
    create_embedding_client,
    EmbeddingModel,
    EmbeddingClient,
    SemanticSearchResult
)


async def example_1_basic_semantic_search():
    """Example 1: Basic semantic search over documents."""
    print("=" * 60)
    print("Example 1: Basic Semantic Search")
    print("=" * 60 + "\n")

    # 1. Create embedding client
    print("1. Creating embedding client...")
    client = create_embedding_client(
        azure_endpoint="https://your-resource.openai.azure.com",
        model=EmbeddingModel.SMALL_3,  # 5x cheaper than ada-002!
        use_managed_identity=True
    )
    print(f"   Model: {client.model}")
    print(f"   Dimensions: {client.dimensions}\n")

    # 2. Knowledge base (agent's accumulated knowledge)
    print("2. Building knowledge base...")
    knowledge_base = [
        {
            "text": "To reconcile payment discrepancies, compare Stripe transaction logs with the general ledger. Focus on timestamp mismatches and currency conversion rates.",
            "source": "finance_agent_123",
            "date": "2025-12-15"
        },
        {
            "text": "When detecting fraud patterns, look for: multiple failed payment attempts from same IP, velocity checks (>5 transactions per minute), unusual geographic patterns.",
            "source": "security_agent_456",
            "date": "2025-12-18"
        },
        {
            "text": "For QuickBooks integration, use OAuth 2.0 authentication. The refresh token expires after 100 days. Store securely in Azure Key Vault.",
            "source": "integration_agent_789",
            "date": "2025-12-20"
        },
        {
            "text": "Salesforce API rate limits: 15,000 calls per 24 hours for Enterprise. Implement exponential backoff when hitting 429 errors.",
            "source": "integration_agent_789",
            "date": "2025-12-21"
        },
        {
            "text": "To optimize PostgreSQL queries with pgvector, create IVFFlat indexes for embeddings larger than 10K rows. Use cosine distance operator <=>.",
            "source": "data_agent_101",
            "date": "2025-12-22"
        }
    ]
    print(f"   Knowledge base: {len(knowledge_base)} entries\n")

    # 3. Perform semantic search
    print("3. Semantic searches:\n")

    queries = [
        "How do I handle payment reconciliation issues?",
        "What are the authentication requirements for accounting software?",
        "How can I improve vector search performance?"
    ]

    for query in queries:
        print(f"   Query: \"{query}\"")

        results = await client.semantic_search(
            query=query,
            candidates=knowledge_base,
            top_k=2,
            text_field="text"
        )

        print(f"   Top results:")
        for i, result in enumerate(results, 1):
            print(f"      {i}. [Similarity: {result.similarity:.3f}] {result.metadata['source']}")
            print(f"         \"{result.text[:80]}...\"")

        print()

    # 4. Show statistics
    print("4. Client statistics:")
    stats = client.get_stats()
    print(f"   Total API calls: {stats['cache_misses']}")
    print(f"   Cache hits: {stats['cache_hits']}")
    print(f"   Cache hit rate: {stats['cache_hit_rate']:.1%}")
    print(f"   Total tokens: {stats['total_tokens']}")
    print(f"   Total cost: ${stats['total_cost_usd']:.6f}")
    print(f"   Model: {stats['model']}")

    await client.close()
    print()


async def example_2_episodic_memory_search():
    """Example 2: Searching agent's episodic memory (past experiences)."""
    print("=" * 60)
    print("Example 2: Episodic Memory Search")
    print("=" * 60 + "\n")

    client = create_embedding_client(
        azure_endpoint="https://your-resource.openai.azure.com",
        model=EmbeddingModel.SMALL_3,
        use_managed_identity=True
    )

    # Simulated episodic memory from finance agent
    print("1. Agent's past experiences (episodic memory)...\n")

    episodes = [
        {
            "text": "Reconciled $125,000 in payments. Found 3 discrepancies due to timezone conversion errors between Stripe (UTC) and QuickBooks (PST).",
            "timestamp": "2025-12-15 09:30:00",
            "task_id": "reconcile_001",
            "success": True
        },
        {
            "text": "Attempted fraud detection on transaction TXN_9876. False positive - customer was legitimately purchasing from multiple devices during travel.",
            "timestamp": "2025-12-16 14:22:00",
            "task_id": "fraud_check_047",
            "success": False
        },
        {
            "text": "Built Salesforce integration. Encountered rate limiting. Implemented retry with exponential backoff (initial: 1s, max: 60s). Success rate improved to 99.8%.",
            "timestamp": "2025-12-18 11:15:00",
            "task_id": "integration_sf_001",
            "success": True
        },
        {
            "text": "Generated monthly financial report. Data pipeline failed midway due to Databricks cluster timeout. Increased cluster timeout from 30min to 2hrs.",
            "timestamp": "2025-12-19 03:00:00",
            "task_id": "report_monthly_12",
            "success": False
        },
        {
            "text": "Reconciled PayPal transactions. Discovered API returns pending transactions separately from completed. Modified query to fetch both and merge.",
            "timestamp": "2025-12-20 10:45:00",
            "task_id": "reconcile_pp_001",
            "success": True
        }
    ]

    # Agent encounters a new situation and searches for similar past experiences
    current_situation = "I need to reconcile transactions from a new payment processor called Square. The timestamps seem to be in a different timezone."

    print(f"2. Current situation:\n   \"{current_situation}\"\n")
    print("3. Searching for similar past experiences...\n")

    results = await client.semantic_search(
        query=current_situation,
        candidates=episodes,
        top_k=3,
        text_field="text"
    )

    print("   Most relevant experiences:")
    for i, result in enumerate(results, 1):
        episode = result.metadata
        print(f"\n   {i}. [Similarity: {result.similarity:.3f}] {episode['task_id']}")
        print(f"      Time: {episode['timestamp']}")
        print(f"      Success: {episode['success']}")
        print(f"      Experience: \"{result.text}\"")

    print("\n   → Agent can learn from episode #1 (timezone issues with Stripe/QuickBooks)")
    print("   → Agent knows to check timezone handling immediately\n")

    await client.close()


async def example_3_procedural_memory():
    """Example 3: Finding relevant procedures by semantic meaning."""
    print("=" * 60)
    print("Example 3: Procedural Memory Search")
    print("=" * 60 + "\n")

    client = create_embedding_client(
        azure_endpoint="https://your-resource.openai.azure.com",
        model=EmbeddingModel.SMALL_3,
        use_managed_identity=True
    )

    # Procedural memory (learned procedures from successful tasks)
    print("1. Agent's learned procedures...\n")

    procedures = [
        {
            "text": "PROCEDURE: API Rate Limit Handling\n1. Detect 429 response\n2. Extract Retry-After header (if present)\n3. Implement exponential backoff: wait = min(base * 2^attempt, max_wait)\n4. Add jitter: wait += random(0, 0.1 * wait)\n5. Retry up to 5 times",
            "procedure_id": "proc_001",
            "success_rate": 0.98,
            "times_used": 47
        },
        {
            "text": "PROCEDURE: OAuth Token Refresh\n1. Check token expiry (expire_time - 5 minutes)\n2. If expired: POST to /oauth/token with refresh_token\n3. Update stored access_token and refresh_token\n4. Store new expiry time\n5. Retry original request with new token",
            "procedure_id": "proc_002",
            "success_rate": 1.0,
            "times_used": 156
        },
        {
            "text": "PROCEDURE: Payment Reconciliation\n1. Fetch transactions from payment processor (last 24 hours)\n2. Fetch corresponding entries from general ledger\n3. Match by transaction_id or reference_number\n4. For unmatched: check ±2 hour window (timezone issues)\n5. Flag discrepancies for manual review",
            "procedure_id": "proc_003",
            "success_rate": 0.95,
            "times_used": 89
        },
        {
            "text": "PROCEDURE: Database Connection Recovery\n1. Catch connection error\n2. Wait 5 seconds (allow temporary network issues to resolve)\n3. Attempt reconnect with exponential backoff\n4. If max retries exceeded: notify ops team\n5. Switch to read replica if available",
            "procedure_id": "proc_004",
            "success_rate": 0.92,
            "times_used": 23
        }
    ]

    # Agent needs to solve a problem
    problem = "The API is returning 429 errors and I keep getting rate limited. How should I handle this?"

    print(f"2. Current problem:\n   \"{problem}\"\n")
    print("3. Searching for relevant procedures...\n")

    results = await client.semantic_search(
        query=problem,
        candidates=procedures,
        top_k=2,
        text_field="text"
    )

    print("   Best matching procedures:")
    for i, result in enumerate(results, 1):
        proc = result.metadata
        print(f"\n   {i}. [Similarity: {result.similarity:.3f}] {proc['procedure_id']}")
        print(f"      Success rate: {proc['success_rate']:.1%}")
        print(f"      Times used: {proc['times_used']}")
        print(f"      Procedure:")
        for line in result.text.split('\n'):
            print(f"         {line}")

    print("\n   → Agent will apply procedure #1 (API Rate Limit Handling)")
    print("   → This procedure has 98% success rate from 47 past uses\n")

    await client.close()


async def example_4_batch_processing():
    """Example 4: Efficient batch processing with caching."""
    print("=" * 60)
    print("Example 4: Batch Processing & Caching")
    print("=" * 60 + "\n")

    client = create_embedding_client(
        azure_endpoint="https://your-resource.openai.azure.com",
        model=EmbeddingModel.SMALL_3,
        use_managed_identity=True
    )

    # Large batch of texts
    print("1. Processing batch of 50 texts...\n")

    texts = [
        f"This is document number {i} about various topics in finance and technology."
        for i in range(50)
    ]

    # First batch (no cache)
    print("   First batch (cold cache):")
    results1 = await client.embed_batch(texts, batch_size=20)
    stats1 = client.get_stats()
    print(f"      Processed: {len(results1)} texts")
    print(f"      Tokens used: {stats1['total_tokens']}")
    print(f"      Cost: ${stats1['total_cost_usd']:.6f}")
    print(f"      Cache hit rate: {stats1['cache_hit_rate']:.1%}\n")

    # Second batch (same texts, should hit cache)
    print("   Second batch (warm cache, same texts):")
    results2 = await client.embed_batch(texts, batch_size=20)
    stats2 = client.get_stats()
    print(f"      Processed: {len(results2)} texts")
    print(f"      Additional tokens: {stats2['total_tokens'] - stats1['total_tokens']}")
    print(f"      Additional cost: ${stats2['total_cost_usd'] - stats1['total_cost_usd']:.6f}")
    print(f"      Cache hit rate: {stats2['cache_hit_rate']:.1%}")
    print(f"      Savings: ~100% (all cached!)\n")

    # Cost comparison
    print("2. Cost comparison:\n")
    print(f"   text-embedding-3-small: ${stats2['avg_cost_per_1k_tokens']:.6f} per 1K tokens")
    print(f"   text-embedding-ada-002: $0.000100 per 1K tokens (5x more expensive)")
    print(f"   text-embedding-3-large: $0.000130 per 1K tokens (6.5x more expensive)")
    print()
    print(f"   For {stats2['total_tokens']} tokens:")
    print(f"      3-small (used): ${stats2['total_cost_usd']:.6f}")
    print(f"      ada-002: ${stats2['total_tokens'] * 0.0001 / 1000:.6f} (5x more)")
    print(f"      3-large: ${stats2['total_tokens'] * 0.00013 / 1000:.6f} (6.5x more)")
    print()

    await client.close()


async def example_5_chunking_long_documents():
    """Example 5: Automatic chunking for long documents."""
    print("=" * 60)
    print("Example 5: Long Document Chunking")
    print("=" * 60 + "\n")

    client = create_embedding_client(
        azure_endpoint="https://your-resource.openai.azure.com",
        model=EmbeddingModel.SMALL_3,
        use_managed_identity=True
    )

    # Long document (simulated API documentation)
    print("1. Processing long document (API documentation)...\n")

    long_document = """
    STRIPE API DOCUMENTATION

    Authentication:
    All API requests must include your API key in the Authorization header using Bearer authentication.
    Example: Authorization: Bearer sk_test_1234567890abcdef

    Rate Limiting:
    The Stripe API has rate limits to ensure system stability. Standard accounts have a limit of 100 requests
    per second. When you exceed the rate limit, you'll receive a 429 Too Many Requests response.

    We recommend implementing exponential backoff in your retry logic. Start with a 1 second delay and double
    it with each retry, up to a maximum of 60 seconds.

    Payment Intents:
    Payment Intents guide you through the process of collecting payment from your customers. They track the
    lifecycle of a customer's payment, from creation through checkout and settlement.

    To create a payment intent, POST to /v1/payment_intents with the amount and currency:
    {
        "amount": 2000,
        "currency": "usd",
        "payment_method_types": ["card"]
    }

    Webhooks:
    Stripe uses webhooks to notify your application about events that happen in your account. This allows you
    to respond to actions like successful payments, failed charges, or subscription changes.

    Configure webhook endpoints in your Dashboard. Each endpoint can be configured to receive specific event
    types. Stripe signs all webhook events to ensure they came from Stripe and haven't been tampered with.

    Error Handling:
    Stripe uses conventional HTTP response codes to indicate the success or failure of an API request. Codes
    in the 2xx range indicate success, 4xx indicate an error with the request, and 5xx indicate an error with
    Stripe's servers.

    Common error codes:
    - 400 Bad Request: The request was unacceptable, often due to missing a required parameter
    - 401 Unauthorized: No valid API key provided
    - 402 Request Failed: The parameters were valid but the request failed
    - 404 Not Found: The requested resource doesn't exist
    - 429 Too Many Requests: Too many requests hit the API too quickly
    - 500, 502, 503, 504 Server Errors: Something went wrong on Stripe's end
    """ * 3  # Repeat 3 times to make it longer

    print(f"   Document length: {len(long_document)} characters\n")

    # Chunk and embed
    print("2. Chunking and embedding...\n")
    chunk_results = await client.embed_chunks(
        text=long_document,
        chunk_size=2000,
        overlap=200
    )

    print(f"   Generated {len(chunk_results)} chunks:")
    for i, result in enumerate(chunk_results, 1):
        print(f"      Chunk {i}: {len(result.text)} chars, {result.tokens_used} tokens")

    print()

    # Search across chunks
    print("3. Searching across chunks...\n")

    query = "What should I do when I get rate limited?"

    print(f"   Query: \"{query}\"\n")

    # Create candidates from chunks
    candidates = [
        {"text": result.text, "chunk_id": i, "embedding": result.embedding}
        for i, result in enumerate(chunk_results, 1)
    ]

    results = await client.semantic_search(
        query=query,
        candidates=candidates,
        top_k=2,
        text_field="text",
        embedding_field="embedding"  # Use pre-computed embeddings
    )

    print("   Most relevant chunks:")
    for i, result in enumerate(results, 1):
        print(f"\n   {i}. Chunk #{result.metadata['chunk_id']} [Similarity: {result.similarity:.3f}]")
        # Show snippet
        relevant_part = result.text[result.text.find("Rate Limiting"):result.text.find("Rate Limiting") + 300]
        print(f"      \"{relevant_part}...\"")

    print()

    await client.close()


async def main():
    """Run all embedding examples."""
    print("\n")
    print("█" * 60)
    print("ANTS Embedding & Semantic Search Examples")
    print("█" * 60)
    print("\n")

    await example_1_basic_semantic_search()
    await example_2_episodic_memory_search()
    await example_3_procedural_memory()
    await example_4_batch_processing()
    await example_5_chunking_long_documents()

    print("=" * 60)
    print("All Examples Complete")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("✓ Semantic search finds meaning, not just keywords")
    print("✓ Agents retrieve similar past experiences from episodic memory")
    print("✓ Procedural memory enables agents to reuse proven solutions")
    print("✓ Caching eliminates redundant API calls (100% hit rate)")
    print("✓ text-embedding-3-small is 5x cheaper than ada-002")
    print("✓ Batch processing optimizes throughput")
    print("✓ Automatic chunking handles long documents")
    print("✓ Cross-agent knowledge sharing via shared vector store")
    print()


if __name__ == "__main__":
    asyncio.run(main())
