/**
 * ANTS Web Portal - Chat Interface Component
 *
 * Modal chat interface for conversing with ANTS agents.
 */

'use client'

import { useState, useEffect } from 'react'
import { X, Send } from 'lucide-react'
import type { Agent, Message } from '@/types/agent'
import { api } from '@/lib/api'

interface ChatInterfaceProps {
  agent: Agent
  onClose: () => void
}

export function ChatInterface({ agent, onClose }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)

  useEffect(() => {
    initializeConversation()
  }, [agent.id])

  const initializeConversation = async () => {
    try {
      const conversation = await api.startConversation(agent.id)
      setConversationId(conversation.id)

      const msgs = await api.getMessages(conversation.id)
      setMessages(msgs)
    } catch (error) {
      console.error('Failed to start conversation:', error)
    }
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !conversationId) return

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: conversationId,
      sender: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
    }

    setMessages([...messages, userMessage])
    setInputValue('')

    try {
      const agentResponse = await api.sendMessage(conversationId, inputValue)
      setMessages((prev) => [...prev, agentResponse])
    } catch (error) {
      console.error('Failed to send message:', error)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl h-[600px] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h3 className="text-lg font-semibold">{agent.name}</h3>
            <p className="text-sm text-gray-600">{agent.type}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[70%] rounded-lg p-3 ${
                  message.sender === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <p className="text-sm">{message.content}</p>
                <p className="text-xs mt-1 opacity-70">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="border-t p-4">
          <div className="flex space-x-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Type a message..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              onClick={handleSendMessage}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
