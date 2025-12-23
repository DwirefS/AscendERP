/**
 * ANTS Web Portal - Agent Marketplace Component
 *
 * Browse and deploy agents from the marketplace.
 */

'use client'

import { useState, useEffect } from 'react'
import { Download, Tag, Clock } from 'lucide-react'
import type { AgentTemplate } from '@/types/agent'
import { api } from '@/lib/api'

export function AgentMarketplace() {
  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = async () => {
    try {
      const data = await api.getAgentTemplates()
      setTemplates(data)
    } catch (error) {
      console.error('Failed to load templates:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDeploy = async (template: AgentTemplate) => {
    try {
      await api.deployAgent({
        agent_template_id: template.id,
        agent_name: `${template.name} Instance`,
        environment: 'production',
        deployment_mode: 'cloud',
        resources: template.requirements,
        plugins: [],
      })
      alert(`Agent ${template.name} deployed successfully!`)
    } catch (error) {
      console.error('Failed to deploy agent:', error)
      alert('Failed to deploy agent')
    }
  }

  if (loading) {
    return <div className="text-center py-8">Loading marketplace...</div>
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {templates.map((template) => (
        <div
          key={template.id}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 card-hover"
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <h4 className="text-lg font-semibold text-gray-900">{template.name}</h4>
              <p className="text-sm text-gray-600 mt-1">{template.description}</p>
            </div>
            <span className={`px-2 py-1 text-xs rounded ${
              template.price_tier === 'free' ? 'bg-green-100 text-green-800' :
              template.price_tier === 'standard' ? 'bg-blue-100 text-blue-800' :
              'bg-purple-100 text-purple-800'
            }`}>
              {template.price_tier}
            </span>
          </div>

          <div className="flex flex-wrap gap-1 mb-4">
            {template.tags.map((tag, index) => (
              <span
                key={index}
                className="inline-flex items-center space-x-1 px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
              >
                <Tag className="w-3 h-3" />
                <span>{tag}</span>
              </span>
            ))}
          </div>

          <div className="space-y-2 mb-4 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Deploy Time</span>
              <span className="font-medium flex items-center space-x-1">
                <Clock className="w-4 h-4" />
                <span>{template.deployment_time_minutes} min</span>
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Resources</span>
              <span className="font-medium">
                {template.requirements.cpu_cores} CPU, {template.requirements.memory_gb}GB RAM
              </span>
            </div>
          </div>

          <button
            onClick={() => handleDeploy(template)}
            className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Deploy</span>
          </button>
        </div>
      ))}
    </div>
  )
}
