/**
 * ANTS Web Portal - Auth Provider
 *
 * Authentication context provider using Azure AD / MSAL.
 */

'use client'

import { ReactNode } from 'react'

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  // In production, this would use @azure/msal-react for Azure AD authentication
  // For now, just pass through children
  return <>{children}</>
}
