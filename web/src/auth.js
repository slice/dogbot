import React from 'react'

export const AuthContext = React.createContext({
  authenticated: false,
  user: null,
})

export const STORAGE_KEY = 'authenticationState'

export function store(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function load() {
  const serialized = localStorage.getItem(STORAGE_KEY)
  if (serialized == null) {
    return null
  }
  return JSON.parse(serialized)
}
