import React from 'react'

export const AuthContext = React.createContext(null)

export function WhenLoggedIn({ children }) {
  return (
    <AuthContext.Consumer>
      {(user) =>
        user != null
          ? typeof children === 'function'
            ? children(user)
            : children
          : null
      }
    </AuthContext.Consumer>
  )
}
