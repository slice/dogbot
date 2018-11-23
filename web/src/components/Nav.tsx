import React, { Component } from 'react'

import './Nav.scss'
import { Status } from '../types'
import API from '../api'
import { Link } from 'react-router-dom'

type State = {
  status: Status
}

export default class Nav extends Component<{}, State> {
  state = { status: { ready: false, ping: -1, guilds: 0 } }

  async componentDidMount() {
    try {
      const status = await API.get<Status>('/api/status')
      this.setState({ status })
    } catch (err) {}
  }

  render() {
    const statusColor = this.state.status.ready
      ? 'hsl(130, 100%, 30%)'
      : 'hsl(345, 100%, 30%)'

    let statusText
    if (this.state.status.ready) {
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
          {`connected (${this.state.status.guilds} servers)`}
        </div>
      )
    } else {
      statusText = <div id="status-text">disconnected</div>
    }

    return (
      <nav>
        <h1>
          <Link to="/">dogbot</Link>
        </h1>
        <div id="status">
          <div id="status-circle" style={{ backgroundColor: statusColor }} />
          {statusText}
        </div>
      </nav>
    )
  }
}
