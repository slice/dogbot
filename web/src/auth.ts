import React from 'react'
import { User } from './types'

export interface AuthState {
  authenticated: boolean
  user: User | null
}

export const AuthContext = React.createContext({
  authenticated: false,
  user: null,
})

export const STORAGE_KEY = '_dogbot_authentication_state'

export function store(state: AuthState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function load(): AuthState | null {
  const serialized = localStorage.getItem(STORAGE_KEY)
  if (serialized == null) {
    return null
  }
  return JSON.parse(serialized)
}
