/**
 * ANTS Web Portal - Type Definitions
 *
 * TypeScript type definitions for agents, conversations, and system data.
 */

export type AgentStatus = 'active' | 'idle' | 'busy' | 'error' | 'offline'

export type AgentType =
  | 'finance'
  | 'security'
  | 'crm'
  | 'hr'
  | 'supply_chain'
  | 'manufacturing'
  | 'retail'
  | 'healthcare'
  | 'selfops'
  | 'stem_cell'

export interface Agent {
  id: string
  name: string
  type: AgentType
  description: string
  status: AgentStatus
  capabilities: string[]
  created_at: string
  last_active: string
  metrics: {
    tasks_completed: number
    success_rate: number
    avg_response_time_ms: number
    total_execution_time_ms: number
  }
  metadata?: Record<string, any>
}

export interface Conversation {
  id: string
  agent_id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  status: 'active' | 'completed' | 'archived'
}

export interface Message {
  id: string
  conversation_id: string
  sender: 'user' | 'agent'
  content: string
  timestamp: string
  attachments?: Attachment[]
  metadata?: Record<string, any>
}

export interface Attachment {
  id: string
  name: string
  type: string
  size: number
  url: string
}

export interface SystemStatus {
  status: 'operational' | 'degraded' | 'outage'
  uptime_seconds: number
  active_agents: number
  total_agents: number
  active_conversations: number
  total_executions_today: number
  metrics: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
    swarm_health: 'healthy' | 'warning' | 'critical'
  }
}

export interface AgentTemplate {
  id: string
  name: string
  type: AgentType
  description: string
  category: string
  tags: string[]
  capabilities: string[]
  use_cases: string[]
  price_tier: 'free' | 'standard' | 'premium'
  deployment_time_minutes: number
  requirements: {
    cpu_cores: number
    memory_gb: number
    gpu_required: boolean
  }
}

export interface DeploymentConfig {
  agent_template_id: string
  agent_name: string
  environment: 'development' | 'staging' | 'production'
  deployment_mode: 'cloud' | 'edge' | 'hybrid'
  resources: {
    cpu_cores: number
    memory_gb: number
    gpu_enabled: boolean
  }
  plugins: string[]
  custom_config?: Record<string, any>
}

export interface PheromoneSignal {
  id: string
  type: string
  strength: number
  source_agent_id: string
  timestamp: string
  metadata: Record<string, any>
}

export interface SwarmMetrics {
  total_agents: number
  active_agents: number
  total_pheromones: number
  coordination_efficiency: number
  avg_response_time_ms: number
}
