/**
 * ANTS Web Portal - Root Layout
 *
 * Main application layout with navigation, authentication,
 * and global providers.
 */

import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Navigation } from '@/components/Navigation'
import { AuthProvider } from '@/components/AuthProvider'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'ANTS - AI-Agent Native Tactical System',
  description: 'Intelligent multi-agent orchestration platform for enterprise automation',
  keywords: ['AI', 'agents', 'automation', 'enterprise', 'Azure', 'NVIDIA'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <div className="min-h-screen bg-gray-50">
            <Navigation />
            <main className="container mx-auto px-4 py-8">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  )
}
