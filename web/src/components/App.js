import React, { Component } from 'react'
import { BrowserRouter as Router, Route } from 'react-router-dom'

import API from '../api'
import logFactory from '../log'
import Guilds from '../views/Guilds'
import Login from '../views/Login'
import AuthRoute from './AuthRoute'
import Landing from '../views/Landing'
import { AuthContext, load, store } from '../auth'
import Nav from './Nav'

const log = logFactory('auth')

export default class App extends Component {
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
      log('saved auth state:', savedAuthState)
      this.setState({ authState: savedAuthState })
    }

    const authState = await this.fetchAuthState()
    this.setState({ authState })
    log('fresh auth state:', authState)
    store(authState)
  }

  async fetchAuthState() {
    const response = await API.get('/auth/session/state')
    return response
  }

  render() {
    if (this.state.authState == null) {
      return (
        <div id="router-wrapper">
          <div id="content">
            <p>Loading...</p>
          </div>
        </div>
      )
    }

    return (
      <div id="router-wrapper">
        <AuthContext.Provider value={this.state.authState}>
          <Router>
            <>
              <Nav />

              <div id="content">
                <Route path="/login" exact component={Login} />
                <Route path="/" exact component={Landing} />
                <AuthRoute path="/guilds" exact component={Guilds} />
              </div>
            </>
          </Router>
        </AuthContext.Provider>
      </div>
    )
  }
}
