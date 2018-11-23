import React, { Component } from 'react'
import { BrowserRouter as Router, Route } from 'react-router-dom'

import API from '../api'
import logFactory from '../log'
import { User } from '../types'
import Guilds from '../views/Guilds'
import Login from '../views/Login'
import AuthRoute from './AuthRoute'
import Landing from '../views/Landing'
import { AuthContext, AuthState } from '../auth'

const log = logFactory('auth')

export default class App extends Component<{}, { auth: AuthState }> {
  state = { auth: { authenticated: false, user: null } }

  async componentDidMount() {
    log('fetching authentication state')
    const authState = await API.get<{ active: boolean; user: User }>(
      '/auth/user'
    )

    log('authentication state:', authState)
    const { active: authenticated, user } = authState
    this.setState({ auth: { authenticated, user } })
  }

  render() {
    return (
      <div id="app-wrapper">
        <div id="content">
          <AuthContext.Provider value={this.state.auth}>
            <Router>
              <>
                <Route path="/login" exact component={Login} />
                <Route path="/" exact component={Landing} />
                <AuthRoute path="/guilds" exact component={Guilds} />
              </>
            </Router>
          </AuthContext.Provider>
        </div>
      </div>
    )
  }
}
