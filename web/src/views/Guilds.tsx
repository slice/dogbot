import React, { Component } from 'react'

import API from '../api'
import { Guild } from '../types'

export default class Guilds extends Component<{}, { guilds: Guild[] }> {
  async componentDidMount() {
    const guilds = await API.get<Guild[]>('/api/guilds')
    this.setState({ guilds })
  }

  render() {
    return <div>guilds here blah</div>
  }
}
