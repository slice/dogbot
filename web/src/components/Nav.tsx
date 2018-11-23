import React, { Component } from 'react'

import './Nav.scss'
import { Status } from '../types'
import API from '../api'
import { Link } from 'react-router-dom'

type State = {
  status: Status | null
}

enum ConnectionStatus {
  CONNECTING,
  CONNECTED,
  DISCONNECTED,
}

function statusToText(status: ConnectionStatus): string {
  switch (status) {
    case ConnectionStatus.CONNECTING:
      return 'connecting...'
    case ConnectionStatus.CONNECTED:
      return 'connected'
    case ConnectionStatus.DISCONNECTED:
      return 'disconnected?'
  }
}

function statusToColor(status: ConnectionStatus): string {
  switch (status) {
    case ConnectionStatus.CONNECTING:
      return 'hsl(40, 100%, 30%)'
    case ConnectionStatus.CONNECTED:
      return 'hsl(130, 100%, 30%)'
    case ConnectionStatus.DISCONNECTED:
      return 'hsl(345, 100%, 30%)'
  }
}

export default class Nav extends Component<{}, State> {
  state: State = { status: null }

  async componentDidMount() {
    try {
      const status = await API.get<Status>('/api/status')
      this.setState({ status })
    } catch (err) {
      this.disconnected()
    }
  }

  disconnected() {
    this.setState({ status: { ready: false, ping: -1, guilds: 0 } })
  }

  status(): ConnectionStatus {
    if (this.state.status == null) {
      return ConnectionStatus.CONNECTING
    } else if (this.state.status) {
      return ConnectionStatus.CONNECTED
    } else {
      return ConnectionStatus.DISCONNECTED
    }
  }

  render() {
    const status = this.status()
    let statusText

    if (status === ConnectionStatus.CONNECTED) {
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
          {`${statusToText(status)} (${this.state.status!.guilds} servers)`}
        </div>
      )
    } else {
      statusText = <div id="status-text">{statusToText(status)}</div>
    }

    return (
      <nav>
        <h1>
          <Link to="/">dogbot</Link>
        </h1>
        <div id="status">
          <div
            id="status-circle"
            style={{ backgroundColor: statusToColor(status) }}
          />
          {statusText}
        </div>
      </nav>
    )
  }
}
