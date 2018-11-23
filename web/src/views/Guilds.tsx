import React, { Component } from 'react'

import './Guilds.scss'
import API from '../api'
import Guild from './Guild'
import { Guild as GuildT } from '../types'

interface State {
  guilds: GuildT[] | null
}

export default class Guilds extends Component<{}, State> {
  state = { guilds: null }

  async componentDidMount() {
    const guilds = await API.get<GuildT[]>('/api/guilds')
    this.setState({ guilds })
  }

  render() {
    const { guilds } = this.state

    let content

    if (guilds == null) {
      content = <p>Loading servers...</p>
      // @ts-ignore
    } else if (guilds.length !== 0) {
      // @ts-ignore
      const guildNodes = guilds.map((guild: GuildT) => (
        <Guild key={guild.id} guild={guild} />
      ))
      content = (
        <>
          <p>Click on a server below to edit its configuration:</p>
          <div className="guild-list">{guildNodes}</div>
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
