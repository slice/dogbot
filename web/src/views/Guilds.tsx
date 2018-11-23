import React, { Component } from 'react'
import { Link } from 'react-router-dom'

import './Guilds.scss'
import API from '../api'
import Guild from './Guild'
import { Guild as GuildT } from '../types'

type State = {
  guilds: GuildT[] | null
}

export default class Guilds extends Component<{}, State> {
  state: State = { guilds: null }

  async componentDidMount() {
    const guilds = await API.get<GuildT[]>('/api/guilds')
    this.setState({ guilds })
  }

  render() {
    const { guilds } = this.state

    let content

    if (guilds == null) {
      content = <p>Loading servers...</p>
    } else if (guilds.length !== 0) {
      const guildNodes = guilds.map((guild: GuildT) => (
        <li key={guild.id}>
          <Link to={`/guild/${guild.id}`}>
            <Guild guild={guild} />
          </Link>
        </li>
      ))
      content = (
        <>
          <p>Click on a server below to edit its configuration:</p>
          <ul className="guild-list">{guildNodes}</ul>
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
