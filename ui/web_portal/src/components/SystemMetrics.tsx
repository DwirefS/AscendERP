/**
 * ANTS Web Portal - System Metrics Component
 *
 * Displays system-wide metrics and health status.
 */

'use client'

import { Activity, Cpu, Database, Zap } from 'lucide-react'
import type { SystemStatus } from '@/types/agent'

interface SystemMetricsProps {
  status: SystemStatus
}

export function SystemMetrics({ status }: SystemMetricsProps) {
  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return `${days}d ${hours}h`
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Active Agents */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-600">Active Agents</p>
          <Zap className="w-5 h-5 text-primary-600" />
        </div>
        <p className="text-3xl font-bold text-gray-900">
          {status.active_agents}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          of {status.total_agents} total
        </p>
      </div>

      {/* Executions Today */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-600">Executions Today</p>
          <Activity className="w-5 h-5 text-green-600" />
        </div>
        <p className="text-3xl font-bold text-gray-900">
          {status.total_executions_today.toLocaleString()}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          {status.active_conversations} active conversations
        </p>
      </div>

      {/* System Health */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-600">System Health</p>
          <Cpu className="w-5 h-5 text-blue-600" />
        </div>
        <p className="text-3xl font-bold text-gray-900 capitalize">
          {status.metrics.swarm_health}
        </p>
        <div className="mt-2 space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-gray-600">CPU</span>
            <span className="font-medium">{status.metrics.cpu_percent}%</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-600">Memory</span>
            <span className="font-medium">{status.metrics.memory_percent}%</span>
          </div>
        </div>
      </div>

      {/* Uptime */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-600">Uptime</p>
          <Database className="w-5 h-5 text-purple-600" />
        </div>
        <p className="text-3xl font-bold text-gray-900">
          {formatUptime(status.uptime_seconds)}
        </p>
        <p className="text-xs text-gray-500 mt-1 capitalize">
          Status: {status.status}
        </p>
      </div>
    </div>
  )
}
