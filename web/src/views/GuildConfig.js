import React, { Component } from 'react'

import './GuildConfig.scss'
import API from '../api'
import GuildIcon from '../components/GuildIcon'

export default class GuildConfig extends Component {
  state = {
    guild: null,
  }

  get guildId() {
    return this.props.match.params.id
  }

  async componentDidMount() {
    const guild = await API.get(`/api/guild/${this.guildId}`)
    this.setState({ guild })
  }

  render() {
    const { guild } = this.state

    if (guild == null) {
      return <p>Loading...</p>
    }

    return (
      <div className="guild-detail">
        <h2>
          <GuildIcon guild={guild} />
          {guild.name}
        </h2>
      </div>
    )
  }
}
