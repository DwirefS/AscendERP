-- ANTS PostgreSQL Initialization Script
-- Sets up database schema with pgvector extension

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS ants;
CREATE SCHEMA IF NOT EXISTS memory;
CREATE SCHEMA IF NOT EXISTS audit;

-- Set search path
SET search_path TO ants, memory, audit, public;

-- Memory: Episodic entries
CREATE TABLE IF NOT EXISTS memory.episodic (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255) NOT NULL,
    content JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_episodic_tenant ON memory.episodic(tenant_id);
CREATE INDEX idx_episodic_agent ON memory.episodic(agent_id);
CREATE INDEX idx_episodic_created ON memory.episodic(created_at DESC);
CREATE INDEX idx_episodic_content ON memory.episodic USING GIN(content);

-- Memory: Semantic entries with vector embeddings
CREATE TABLE IF NOT EXISTS memory.semantic (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_semantic_tenant ON memory.semantic(tenant_id);
CREATE INDEX idx_semantic_agent ON memory.semantic(agent_id);
CREATE INDEX idx_semantic_embedding ON memory.semantic USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Memory: Procedural patterns
CREATE TABLE IF NOT EXISTS memory.procedural (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255) NOT NULL,
    pattern JSONB NOT NULL,
    success_rate DECIMAL(5,4) DEFAULT 0.0,
    execution_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_procedural_tenant ON memory.procedural(tenant_id);
CREATE INDEX idx_procedural_agent ON memory.procedural(agent_id);
CREATE INDEX idx_procedural_success ON memory.procedural(success_rate DESC);

-- ANTS: Agent registry
CREATE TABLE IF NOT EXISTS ants.agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_type VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0.0',
    config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ANTS: Agent executions
CREATE TABLE IF NOT EXISTS ants.executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(255) NOT NULL UNIQUE,
    agent_id UUID REFERENCES ants.agents(id),
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    input JSONB NOT NULL,
    output JSONB,
    status VARCHAR(50) DEFAULT 'running',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    latency_ms DECIMAL(12,2),
    tokens_used INTEGER DEFAULT 0,
    error TEXT
);

CREATE INDEX idx_executions_trace ON ants.executions(trace_id);
CREATE INDEX idx_executions_tenant ON ants.executions(tenant_id);
CREATE INDEX idx_executions_status ON ants.executions(status);
CREATE INDEX idx_executions_started ON ants.executions(started_at DESC);

-- ANTS: Tool usage tracking
CREATE TABLE IF NOT EXISTS ants.tool_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID REFERENCES ants.executions(id),
    tool_name VARCHAR(255) NOT NULL,
    tool_args JSONB,
    result JSONB,
    policy_decision VARCHAR(50),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    latency_ms DECIMAL(12,2)
);

CREATE INDEX idx_tool_usage_execution ON ants.tool_usage(execution_id);
CREATE INDEX idx_tool_usage_tool ON ants.tool_usage(tool_name);

-- Audit: Receipts (immutable audit log)
CREATE TABLE IF NOT EXISTS audit.receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    receipt_type VARCHAR(50) NOT NULL,
    trace_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255),
    action VARCHAR(255) NOT NULL,
    actor VARCHAR(255),
    resource VARCHAR(255),
    details JSONB NOT NULL,
    policy_decision VARCHAR(50),
    hash VARCHAR(64),  -- SHA-256 of previous receipt for chain integrity
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_receipts_trace ON audit.receipts(trace_id);
CREATE INDEX idx_receipts_tenant ON audit.receipts(tenant_id);
CREATE INDEX idx_receipts_type ON audit.receipts(receipt_type);
CREATE INDEX idx_receipts_created ON audit.receipts(created_at DESC);

-- Make receipts table append-only
CREATE RULE receipts_no_update AS ON UPDATE TO audit.receipts DO INSTEAD NOTHING;
CREATE RULE receipts_no_delete AS ON DELETE TO audit.receipts DO INSTEAD NOTHING;

-- ANTS: Metrics aggregation
CREATE TABLE IF NOT EXISTS ants.metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    tenant_id VARCHAR(255),
    agent_type VARCHAR(255),
    value DECIMAL(18,6) NOT NULL,
    labels JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name ON ants.metrics(metric_name, timestamp DESC);
CREATE INDEX idx_metrics_tenant ON ants.metrics(tenant_id, timestamp DESC);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to relevant tables
CREATE TRIGGER update_episodic_updated_at
    BEFORE UPDATE ON memory.episodic
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_semantic_updated_at
    BEFORE UPDATE ON memory.semantic
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_procedural_updated_at
    BEFORE UPDATE ON memory.procedural
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON ants.agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Insert default agents
INSERT INTO ants.agents (agent_type, name, description) VALUES
    ('finance.reconciliation', 'Reconciliation Agent', 'Automates financial reconciliation'),
    ('retail.inventory', 'Inventory Agent', 'Manages inventory levels and replenishment'),
    ('cybersecurity.defender', 'Defender Triage Agent', 'Triages security alerts'),
    ('selfops.infra', 'InfraOps Agent', 'Manages infrastructure operations')
ON CONFLICT (agent_type) DO NOTHING;

-- Grant permissions
GRANT ALL ON SCHEMA ants TO ants;
GRANT ALL ON SCHEMA memory TO ants;
GRANT ALL ON SCHEMA audit TO ants;
GRANT ALL ON ALL TABLES IN SCHEMA ants TO ants;
GRANT ALL ON ALL TABLES IN SCHEMA memory TO ants;
GRANT ALL ON ALL TABLES IN SCHEMA audit TO ants;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA ants TO ants;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA memory TO ants;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA audit TO ants;
