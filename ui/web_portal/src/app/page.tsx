/**
 * ANTS Web Portal - Dashboard Page
 *
 * Main dashboard showing agent overview, active conversations,
 * and system status.
 */

'use client'

import { useState, useEffect } from 'react'
import { AgentCard } from '@/components/AgentCard'
import { ChatInterface } from '@/components/ChatInterface'
import { SystemMetrics } from '@/components/SystemMetrics'
import { AgentMarketplace } from '@/components/AgentMarketplace'
import { api } from '@/lib/api'
import type { Agent, SystemStatus } from '@/types/agent'

export default function Dashboard() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()

    // Refresh every 30 seconds
    const interval = setInterval(loadDashboardData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadDashboardData = async () => {
    try {
      const [agentsData, statusData] = await Promise.all([
        api.getAgents(),
        api.getSystemStatus()
      ])

      setAgents(agentsData)
      setSystemStatus(statusData)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading ANTS Dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold gradient-text">
              ANTS Dashboard
            </h1>
            <p className="text-gray-600 mt-1">
              AI-Agent Native Tactical System
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <p className="text-sm text-gray-500">System Status</p>
              <div className="flex items-center space-x-2 mt-1">
                <span className="flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                </span>
                <span className="text-sm font-medium text-green-600">Operational</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* System Metrics */}
      {systemStatus && (
        <SystemMetrics status={systemStatus} />
      )}

      {/* Active Agents */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-900">Active Agents</h2>
          <p className="text-sm text-gray-500">
            {agents.filter(a => a.status === 'active').length} of {agents.length} agents active
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onClick={() => setSelectedAgent(agent)}
            />
          ))}
        </div>

        {agents.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg">
            <p className="text-gray-500">No agents deployed</p>
            <button className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700">
              Deploy Your First Agent
            </button>
          </div>
        )}
      </section>

      {/* Agent Marketplace */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Agent Marketplace</h2>
        <AgentMarketplace />
      </section>

      {/* Chat Interface (Modal) */}
      {selectedAgent && (
        <ChatInterface
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
        />
      )}
    </div>
  )
}
