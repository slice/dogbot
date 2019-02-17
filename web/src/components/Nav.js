import React, { Component } from 'react'
import 'styled-components/macro'
import { Link } from 'react-router-dom'
import styled from 'styled-components'
import { FaSignOutAlt, FaGithub } from 'react-icons/fa'

import './Nav.scss'
import User from './User'
import API from '../api'
import { WhenLoggedIn } from '../auth'

const Links = styled.div`
  margin-left: auto;
  display: flex;

  a {
    margin-left: 2em;
    display: flex;
    align-items: center;
  }

  svg {
    margin-right: 0.5em;
  }
`

const StyledNav = styled.nav`
  @media (max-width: 700px) {
    svg {
      margin-right: 0 !important;
    }

    .link-text, .username, #status-text {
      display: none;
    }
  }
`

const ConnectionStatus = {
  CONNECTING: { text: 'Connecting...', color: 'hsl(40, 100%, 30%)' },
  CONNECTED: { text: 'Connected!', color: 'hsl(130, 100%, 30%)' },
  DISCONNECTED: { text: 'Disconnected.', color: 'hsl(345, 100%, 30%)' },
}

export default class Nav extends Component {
  state = {
    status: null,
  }

  async componentDidMount() {
    try {
      const status = await API.get('/api/status')
      this.setState({ status })
    } catch (error) {
      this.disconnected()
    }
  }

  disconnected() {
    this.setState({ status: { ready: false, ping: -1, guilds: 0 } })
  }

  status() {
    if (this.state.status == null) {
      return ConnectionStatus.CONNECTING
    } else if (this.state.status.ready) {
      return ConnectionStatus.CONNECTED
    } else {
      return ConnectionStatus.DISCONNECTED
    }
  }

  render() {
    const status = this.status()
    let statusText

    if (status.text === ConnectionStatus.CONNECTED.text) {
      statusText = (
        <div
          id="status-text"
          style={{
            animationName: 'status-text-hide',
            animationDuration: '0.25s',
            animationDelay: '1s',
            animationTimingFunction: 'ease-in-out',
            animationIterationCount: '1',
            animationDirection: 'normal',
            animationFillMode: 'forwards',
            animationPlayState: 'playing',
          }}
        >
          {`${status.text} (${this.state.status.guilds} servers)`}
        </div>
      )
    } else {
      statusText = <div id="status-text">{status.text}</div>
    }

    return (
      <StyledNav>
        <h1>
          <Link to="/">dogbot</Link>
        </h1>
        <div id="status">
          <div id="status-circle" style={{ backgroundColor: status.color }} />
          {statusText}
          <WhenLoggedIn>
            {(user) => <User css="margin-left: 0.5em;" user={user} />}
          </WhenLoggedIn>
        </div>
        <Links>
          <a
            href="https://github.com/slice/dogbot"
            target="_blank"
            rel="noopener noreferrer"
          >
            <FaGithub /> <span className="link-text">Source Code</span>
          </a>
          <WhenLoggedIn>
            <a href="/auth/logout">
              <FaSignOutAlt /> <span className="link-text">Logout</span>
            </a>
          </WhenLoggedIn>
        </Links>
      </StyledNav>
    )
  }
}
