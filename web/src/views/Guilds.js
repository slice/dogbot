import React, { Component } from 'react'
import styled from 'styled-components'
import 'styled-components/macro'
import { Link } from 'react-router-dom'

import API from '../api'
import Notice from '../components/Notice'
import Guild from '../components/Guild'
import Loading from '../components/Loading'

const GuildList = styled.ul`
  list-style-type: none;
  padding: 0;
  margin: 1rem 0;

  li a {
    color: inherit;
    text-decoration: inherit;
  }
`

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
      content = <Loading />
    } else if (error != null) {
      content = <Notice mood="danger">Failed to load servers: {error}</Notice>
    } else if (guilds.length !== 0) {
      const guildNodes = guilds.map((guild) => (
        <li key={guild.id}>
          <Link to={`/guilds/${guild.id}`} css="display: block">
            <Guild guild={guild} />
          </Link>
        </li>
      ))

      content = <GuildList>{guildNodes}</GuildList>
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
