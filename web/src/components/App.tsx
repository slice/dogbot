import React, { Component } from 'react'
import { BrowserRouter as Router, Route } from 'react-router-dom'

import API from '../api'
import logFactory from '../log'
import { User } from '../types'
import Guilds from '../views/Guilds'
import Login from '../views/Login'
import AuthRoute from './AuthRoute'
import Landing from '../views/Landing'
import { AuthContext, AuthState, load, store } from '../auth'

const log = logFactory('auth')

export default class App extends Component<{}, { auth: AuthState | null }> {
  state = { auth: null }

  async componentDidMount() {
    const state = load()

    if (state == null || window.location.hash === '#auth_bust') {
      if (window.location.hash !== '') {
        // reset hash
        window.history.replaceState({}, document.title, '.')
      }

      // no state was preserved
      log('fetching authentication state...')
      const newState = await this.fetchAuthState()
      store(newState)
    } else {
      // auth state was preserved, restore.
      log('loading authentication state...')
      this.setState({ auth: state })
    }
  }

  async fetchAuthState() {
    const response = await API.get<{ active: boolean; user: User }>(
      '/auth/user'
    )

    log('/auth/user response:', response)

    const authState: AuthState = {
      authenticated: response.active,
      user: response.user,
    }

    this.setState({ auth: authState })
    return authState
  }

  render() {
    let routes
    if (this.state.auth !== null) {
      routes = (
        <AuthContext.Provider value={this.state.auth!}>
          <Router>
            <>
              <Route path="/login" exact component={Login} />
              <Route path="/" exact component={Landing} />
              <AuthRoute path="/guilds" exact component={Guilds} />
            </>
          </Router>
        </AuthContext.Provider>
      )
    } else {
      routes = <p>Loading...</p>
    }

    return (
      <div id="app-wrapper">
        <div id="content">{routes}</div>
      </div>
    )
  }
}
