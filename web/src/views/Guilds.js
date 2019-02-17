import React, { Component } from 'react'
import { Link } from 'react-router-dom'

import './Guilds.scss'
import API from '../api'
import Notice from '../components/Notice'
import Guild from '../components/Guild'

export default class Guilds extends Component {
  state = {
    guilds: null,
    error: null,
  }

  async componentDidMount() {
    try {
      const guilds = await API.get('/api/guilds')
      this.setState({ guilds })
    } catch (error) {
      this.setState({ error })
    }
  }

  render() {
    const { guilds, error } = this.state

    let content

    if (guilds == null) {
      content = <p>Loading servers...</p>
    } else if (error != null) {
      content = <Notice mood="danger">Failed to load servers: {error}</Notice>
    } else if (guilds.length !== 0) {
      const guildNodes = guilds.map((guild) => (
        <li key={guild.id}>
          <Link to={`/guilds/${guild.id}`}>
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
      content = <p>No servers.</p>
    }

    return (
      <div id="guilds">
        <h2>Servers</h2>
        {content}
      </div>
    )
  }
}
