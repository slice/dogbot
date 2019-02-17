import React, { Component } from 'react'
import {
  BrowserRouter as Router,
  Route,
  Switch,
  Redirect,
} from 'react-router-dom'

import { GlobalStyle } from '..'
import { themes } from '../theming'
import { ThemeProvider } from 'styled-components'
import API from '../api'
import logFactory from '../log'
import AuthRoute from './AuthRoute'
import Guilds from '../views/Guilds'
import Login from '../views/Login'
import GuildConfig from '../views/GuildConfig'
import { AuthContext } from '../auth'
import Nav from './Nav'

const log = logFactory('auth')

export default class App extends Component {
  state = { authState: null, theme: themes[localStorage.dogTheme || 'light'] }

  async componentDidMount() {
    try {
      var user = await this.fetchUser()
      this.setState({ authState: { user } })
    } catch (error) {
      this.setState({ authState: { user: null } })
    }

    if (user != null) {
      log(`logged in as ${user.username}#${user.discriminator} (${user.id})`)
    }
  }

  async fetchUser() {
    return await API.get('/auth/profile')
  }

  handleToggleLights = () => {
    this.setState(
      (state) => ({
        theme: state.theme.name === 'dark' ? themes.light : themes.dark,
      }),
      () => {
        const { name } = this.state.theme
        localStorage.dogTheme = name
      }
    )
  }

  render() {
    const { authState, theme } = this.state

    if (authState == null) {
      return (
        <div id="router-wrapper">
          <div id="content">Loading...</div>
        </div>
      )
    }

    return (
      <div id="router-wrapper">
        <AuthContext.Provider value={authState.user || null}>
          <Router>
            <ThemeProvider theme={theme}>
              <>
                <GlobalStyle />
                <Nav onToggleLights={this.handleToggleLights} />

                <div id="content">
                  <Switch>
                    <Redirect from="/" to="/guilds" exact />
                    <Route path="/login" exact component={Login} />
                    <AuthRoute path="/guilds" exact component={Guilds} />
                    <AuthRoute
                      path="/guilds/:id"
                      exact
                      component={GuildConfig}
                    />
                  </Switch>
                </div>
              </>
            </ThemeProvider>
          </Router>
        </AuthContext.Provider>
      </div>
    )
  }
}
