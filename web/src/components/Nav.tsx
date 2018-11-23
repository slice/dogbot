import React, { Component } from 'react'

import './Nav.scss'
import { Status } from '../types'
import API from '../api'
import { Link } from 'react-router-dom'

type State = {
  status: Status
}

export default class Nav extends Component<{}, State> {
  async componentDidMount() {
    const status = await API.get<Status>('/api/status')
    this.setState({ status })
  }

  render() {
    return (
      <nav>
        <h1>
          <Link to="/">dogbot</Link>
        </h1>
      </nav>
    )
  }
}
