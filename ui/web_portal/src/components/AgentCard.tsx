/**
 * ANTS Web Portal - Agent Card Component
 *
 * Displays agent information in a card format with status, metrics,
 * and quick actions.
 */

'use client'

import { Activity, Zap, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import type { Agent } from '@/types/agent'

interface AgentCardProps {
  agent: Agent
  onClick?: () => void
}

export function AgentCard({ agent, onClick }: AgentCardProps) {
  const statusColors = {
    active: 'bg-green-100 text-green-800 border-green-200',
    idle: 'bg-gray-100 text-gray-800 border-gray-200',
    busy: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    error: 'bg-red-100 text-red-800 border-red-200',
    offline: 'bg-gray-100 text-gray-600 border-gray-200',
  }

  const statusIcons = {
    active: <Activity className="w-4 h-4" />,
    idle: <Clock className="w-4 h-4" />,
    busy: <Zap className="w-4 h-4" />,
    error: <AlertCircle className="w-4 h-4" />,
    offline: <AlertCircle className="w-4 h-4" />,
  }

  const statusDotColors = {
    active: 'bg-green-500',
    idle: 'bg-gray-400',
    busy: 'bg-yellow-500',
    error: 'bg-red-500',
    offline: 'bg-gray-400',
  }

  return (
    <div
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 card-hover cursor-pointer"
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">
            {agent.name}
          </h3>
          <p className="text-sm text-gray-600">{agent.description}</p>
        </div>

        {/* Status indicator */}
        <div className="flex items-center space-x-1">
          <span className={`flex h-2 w-2`}>
            <span className={`animate-ping absolute inline-flex h-2 w-2 rounded-full ${statusDotColors[agent.status]} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${statusDotColors[agent.status]}`}></span>
          </span>
        </div>
      </div>

      {/* Agent Type Badge */}
      <div className="flex items-center space-x-2 mb-4">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
          {agent.type}
        </span>
        <span
          className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusColors[agent.status]}`}
        >
          {statusIcons[agent.status]}
          <span className="capitalize">{agent.status}</span>
        </span>
      </div>

      {/* Capabilities */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 mb-2">Capabilities</p>
        <div className="flex flex-wrap gap-1">
          {agent.capabilities.slice(0, 3).map((capability, index) => (
            <span
              key={index}
              className="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded"
            >
              {capability}
            </span>
          ))}
          {agent.capabilities.length > 3 && (
            <span className="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded">
              +{agent.capabilities.length - 3} more
            </span>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-500">Tasks Completed</p>
          <p className="text-lg font-semibold text-gray-900">
            {agent.metrics.tasks_completed}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Success Rate</p>
          <p className="text-lg font-semibold text-gray-900">
            {(agent.metrics.success_rate * 100).toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
        <div>
          <p className="text-xs text-gray-500">Avg Response</p>
          <p className="text-sm font-medium text-gray-900">
            {agent.metrics.avg_response_time_ms}ms
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Last Active</p>
          <p className="text-sm font-medium text-gray-900">
            {new Date(agent.last_active).toLocaleTimeString()}
          </p>
        </div>
      </div>

      {/* Quick actions */}
      <div className="flex items-center space-x-2 mt-4 pt-4 border-t border-gray-100">
        <button className="flex-1 px-3 py-1.5 text-sm font-medium text-primary-700 bg-primary-50 rounded hover:bg-primary-100 transition-colors">
          Chat
        </button>
        <button className="flex-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-50 rounded hover:bg-gray-100 transition-colors">
          Metrics
        </button>
      </div>
    </div>
  )
}
