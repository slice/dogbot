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

export default class App extends Component<
  {},
  { authState: AuthState | null }
> {
  state = { authState: null }

  async componentDidMount() {
    const savedAuthState = load()

    // Use the cached authentication state first, so we don't have to wait for
    // network requests to finish in case the saved one was still valid.
    //
    // For example: if a logged in auth state has been saved (and we are in fact
    // logged in), then this setState call will be accurate, and fetching the
    // auth state later will have no effect because the values are the same.
    // If a logged in auth state has been saved, but the session has become
    // invalidated for whatever reason, we'll momentarily believe that we are
    // logged in, but the upcoming network request will revoke that state.
    //
    // In other words, the second setState is used to invalidate sessions.
    if (savedAuthState != null) {
      this.setState({ authState: savedAuthState })
    }

    const authState = await this.fetchAuthState()
    this.setState({ authState })
    store(authState)
  }

  async fetchAuthState() {
    const response = await API.get<AuthState>('/auth/session/state')
    return response
  }

  render() {
    let routes
    if (this.state.authState !== null) {
      routes = (
        <AuthContext.Provider value={this.state.authState!}>
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
