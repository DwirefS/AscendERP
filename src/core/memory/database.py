"""
Database client for ANTS Memory Substrate.
PostgreSQL with pgvector extension.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
from asyncpg import Pool
import structlog

logger = structlog.get_logger()


class DatabaseClient:
    """
    PostgreSQL client for ANTS memory substrate.
    Manages connections and provides query interface.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._pool: Optional[Pool] = None

    async def connect(self):
        """Create connection pool."""
        logger.info("connecting_to_database")

        self._pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=20,
            command_timeout=60
        )

        logger.info("database_connected")

    async def initialize_schemas(self):
        """
        Create memory schemas and tables if they don't exist.
        Called at startup to ensure database is ready.
        Uses pgvector for 1024-dimensional embeddings (NV-EmbedQA-E5-v5).
        Added 2026-03-04 for automated schema bootstrapping.
        """
        logger.info("initializing_database_schemas")

        async with self._pool.acquire() as conn:
            # Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

            # Create memory schema
            await conn.execute("CREATE SCHEMA IF NOT EXISTS memory;")

            # Episodic: agent execution traces, history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory.episodic (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    content JSONB NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # Semantic: knowledge with vector embeddings (1024D for NV-EmbedQA)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory.semantic (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(1024),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # Create IVFFlat index for vector similarity search
            # Lists=100 is good for up to ~100K vectors; increase for larger datasets
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_embedding
                ON memory.semantic
                USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
            """)

            # Procedural: learned patterns sorted by success rate
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory.procedural (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    pattern JSONB NOT NULL,
                    success_rate FLOAT DEFAULT 0.0,
                    execution_count INT DEFAULT 0,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # Create ANTS operational schema for agent management
            await conn.execute("CREATE SCHEMA IF NOT EXISTS ants;")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ants.agents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_type TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    config JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ants.executions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    trace_id TEXT NOT NULL,
                    agent_id UUID REFERENCES ants.agents(id),
                    tenant_id TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    input JSONB,
                    output JSONB,
                    status TEXT DEFAULT 'running',
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    latency_ms FLOAT,
                    tokens_used INT DEFAULT 0,
                    error TEXT
                );
            """)

            # Create audit schema for immutable receipts
            await conn.execute("CREATE SCHEMA IF NOT EXISTS audit;")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit.receipts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    receipt_type TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT,
                    resource TEXT,
                    details JSONB DEFAULT '{}',
                    policy_decision TEXT,
                    hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # Create indexes for common queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_tenant_agent
                ON memory.episodic (tenant_id, agent_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_tenant
                ON memory.semantic (tenant_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_procedural_agent_success
                ON memory.procedural (agent_id, success_rate DESC);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_executions_trace
                ON ants.executions (trace_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_receipts_trace
                ON audit.receipts (trace_id);
            """)

        logger.info("database_schemas_initialized")

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("database_closed")

    async def execute(self, query: str, *args) -> str:
        """Execute a query without returning results."""
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def fetchone(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetchval(self, query: str, *args):
        """Fetch a single value."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    # Episodic memory operations
    async def insert_episodic(
        self,
        entry_id: str,
        tenant_id: str,
        agent_id: str,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """Insert episodic memory entry."""
        import json

        query = """
            INSERT INTO memory.episodic (id, tenant_id, agent_id, content, metadata)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """

        return await self.fetchval(
            query,
            entry_id,
            tenant_id,
            agent_id,
            json.dumps(content),
            json.dumps(metadata)
        )

    async def query_episodic(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query episodic memories."""
        conditions = []
        params = []
        param_num = 1

        if tenant_id:
            conditions.append(f"tenant_id = ${param_num}")
            params.append(tenant_id)
            param_num += 1

        if agent_id:
            conditions.append(f"agent_id = ${param_num}")
            params.append(agent_id)
            param_num += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT id, tenant_id, agent_id, content, metadata, created_at, updated_at
            FROM memory.episodic
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_num} OFFSET ${param_num + 1}
        """

        params.extend([limit, offset])

        return await self.fetch(query, *params)

    # Semantic memory operations
    async def insert_semantic(
        self,
        entry_id: str,
        tenant_id: str,
        agent_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """Insert semantic memory entry with vector embedding."""
        import json

        query = """
            INSERT INTO memory.semantic (id, tenant_id, agent_id, content, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        return await self.fetchval(
            query,
            entry_id,
            tenant_id,
            agent_id,
            content,
            str(embedding),  # pgvector will convert
            json.dumps(metadata)
        )

    async def vector_search(
        self,
        embedding: List[float],
        tenant_id: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        conditions = []
        params = [str(embedding)]
        param_num = 2

        if tenant_id:
            conditions.append(f"tenant_id = ${param_num}")
            params.append(tenant_id)
            param_num += 1

        where_clause = f"AND {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT
                id,
                tenant_id,
                agent_id,
                content,
                metadata,
                created_at,
                1 - (embedding <=> $1) as similarity
            FROM memory.semantic
            WHERE 1 - (embedding <=> $1) >= ${param_num}
            {where_clause}
            ORDER BY embedding <=> $1
            LIMIT ${param_num + 1}
        """

        params.extend([threshold, limit])

        return await self.fetch(query, *params)

    # Procedural memory operations
    async def insert_procedural(
        self,
        entry_id: str,
        tenant_id: str,
        agent_id: str,
        pattern: Dict[str, Any],
        success_rate: float,
        metadata: Dict[str, Any]
    ) -> str:
        """Insert procedural memory entry."""
        import json

        query = """
            INSERT INTO memory.procedural (id, tenant_id, agent_id, pattern, success_rate, metadata, execution_count)
            VALUES ($1, $2, $3, $4, $5, $6, 1)
            RETURNING id
        """

        return await self.fetchval(
            query,
            entry_id,
            tenant_id,
            agent_id,
            json.dumps(pattern),
            success_rate,
            json.dumps(metadata)
        )

    async def update_procedural_success(
        self,
        entry_id: str,
        new_success_rate: float
    ):
        """Update procedural memory success rate."""
        query = """
            UPDATE memory.procedural
            SET
                success_rate = $2,
                execution_count = execution_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
        """

        await self.execute(query, entry_id, new_success_rate)

    async def query_procedural(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
        min_success_rate: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Query procedural memories."""
        # NOTE: Original code had a bug — referenced `conditions` before it was
        # defined (self-referencing list comprehension). Fixed 2026-03-04.
        conditions = ["success_rate >= $1"]
        params = [min_success_rate]
        param_num = 2  # Next parameter number after $1

        if tenant_id:
            conditions.append(f"tenant_id = ${param_num}")
            params.append(tenant_id)
            param_num += 1

        if agent_id:
            conditions.append(f"agent_id = ${param_num}")
            params.append(agent_id)
            param_num += 1

        where_clause = f"WHERE {' AND '.join(conditions)}"

        query = f"""
            SELECT id, tenant_id, agent_id, pattern, success_rate, execution_count, metadata, created_at
            FROM memory.procedural
            {where_clause}
            ORDER BY success_rate DESC, execution_count DESC
            LIMIT ${param_num}
        """

        params.append(limit)

        return await self.fetch(query, *params)

    # Agent execution tracking
    async def insert_execution(
        self,
        trace_id: str,
        agent_type: str,
        tenant_id: str,
        user_id: Optional[str],
        session_id: Optional[str],
        input_data: Dict[str, Any]
    ) -> str:
        """Insert agent execution record."""
        import json

        # Get agent_id from agents table
        agent_id_query = "SELECT id FROM ants.agents WHERE agent_type = $1"
        agent_id = await self.fetchval(agent_id_query, agent_type)

        query = """
            INSERT INTO ants.executions (trace_id, agent_id, tenant_id, user_id, session_id, input, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'running')
            RETURNING id
        """

        return await self.fetchval(
            query,
            trace_id,
            agent_id,
            tenant_id,
            user_id,
            session_id,
            json.dumps(input_data)
        )

    async def update_execution(
        self,
        trace_id: str,
        output: Dict[str, Any],
        status: str,
        latency_ms: float,
        tokens_used: int,
        error: Optional[str] = None
    ):
        """Update execution record with results."""
        import json

        query = """
            UPDATE ants.executions
            SET
                output = $2,
                status = $3,
                completed_at = CURRENT_TIMESTAMP,
                latency_ms = $4,
                tokens_used = $5,
                error = $6
            WHERE trace_id = $1
        """

        await self.execute(
            query,
            trace_id,
            json.dumps(output),
            status,
            latency_ms,
            tokens_used,
            error
        )

    # Audit receipts
    async def insert_receipt(
        self,
        receipt_type: str,
        trace_id: str,
        tenant_id: str,
        agent_id: str,
        action: str,
        actor: Optional[str],
        resource: Optional[str],
        details: Dict[str, Any],
        policy_decision: Optional[str],
        previous_hash: Optional[str]
    ) -> str:
        """Insert immutable audit receipt."""
        import json
        import hashlib

        # Calculate hash of this receipt
        receipt_data = f"{trace_id}{tenant_id}{agent_id}{action}{json.dumps(details)}{previous_hash}"
        receipt_hash = hashlib.sha256(receipt_data.encode()).hexdigest()

        query = """
            INSERT INTO audit.receipts (
                receipt_type, trace_id, tenant_id, agent_id, action,
                actor, resource, details, policy_decision, hash
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """

        return await self.fetchval(
            query,
            receipt_type,
            trace_id,
            tenant_id,
            agent_id,
            action,
            actor,
            resource,
            json.dumps(details),
            policy_decision,
            receipt_hash
        )
