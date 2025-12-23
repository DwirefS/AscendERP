/**
 * ANTS Web Portal - Navigation Component
 *
 * Main navigation bar with user menu and navigation links.
 */

'use client'

import Link from 'next/link'
import { Home, Zap, BarChart3, Settings, User } from 'lucide-react'

export function Navigation() {
  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <Zap className="w-8 h-8 text-primary-600" />
            <span className="text-xl font-bold gradient-text">ANTS</span>
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center space-x-6">
            <Link
              href="/"
              className="flex items-center space-x-1 text-gray-700 hover:text-primary-600 transition-colors"
            >
              <Home className="w-4 h-4" />
              <span>Dashboard</span>
            </Link>
            <Link
              href="/agents"
              className="flex items-center space-x-1 text-gray-700 hover:text-primary-600 transition-colors"
            >
              <Zap className="w-4 h-4" />
              <span>Agents</span>
            </Link>
            <Link
              href="/analytics"
              className="flex items-center space-x-1 text-gray-700 hover:text-primary-600 transition-colors"
            >
              <BarChart3 className="w-4 h-4" />
              <span>Analytics</span>
            </Link>
            <Link
              href="/settings"
              className="flex items-center space-x-1 text-gray-700 hover:text-primary-600 transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </Link>
          </div>

          {/* User Menu */}
          <div className="flex items-center space-x-2">
            <button className="flex items-center space-x-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
              <User className="w-5 h-5 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">User</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}
