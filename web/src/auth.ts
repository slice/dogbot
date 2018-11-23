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
