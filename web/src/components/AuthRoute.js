import React from 'react'
import { Route, Redirect } from 'react-router-dom'

import { AuthContext } from '../auth'

export default function AuthRoute({ component: Component, ...routeProps }) {
  const render = (props) => (
    <AuthContext.Consumer>
      {(user) =>
        user != null ? (
          <Component {...props} />
        ) : (
          <Redirect to={{ pathname: '/login' }} />
        )
      }
    </AuthContext.Consumer>
  )

  return <Route {...routeProps} render={render} />
}
