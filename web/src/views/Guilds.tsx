import React, { Component } from 'react'

import './Guilds.scss'
import API from '../api'
import Guild from './Guild'
import { Guild as GuildT } from '../types'

export default class Guilds extends Component<{}, { guilds: GuildT[] }> {
  state = { guilds: [] }

  async componentDidMount() {
    const guilds = await API.get<GuildT[]>('/api/guilds')
    this.setState({ guilds })
  }

  render() {
    let content
    if (this.state.guilds.length !== 0) {
      const guilds = this.state.guilds.map((guild: GuildT) => (
        <Guild key={guild.id} guild={guild} />
      ))
      content = (
        <>
          <p>Click on a server below to edit its configuration:</p>
          <div className="guild-list">{guilds}</div>
        </>
      )
    } else {
      content = <p>Nothing here.</p>
    }

    return (
      <div id="guilds">
        <h2>Servers</h2>
        {content}
      </div>
    )
  }
}
