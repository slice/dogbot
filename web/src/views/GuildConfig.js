import React, { Component } from 'react'

import './GuildConfig.scss'
import API from '../api'
import Button from '../components/Button'
import GuildIcon from '../components/GuildIcon'
import ConfigEditor from '../components/ConfigEditor'

export default class GuildConfig extends Component {
  state = {
    guild: null,
    error: null,
    config: '',
  }

  get guildId() {
    return this.props.match.params.id
  }

  async componentDidMount() {
    try {
      var guild = await API.get(`/api/guild/${this.guildId}`)
      var { config } = await API.get(`/api/guild/${this.guildId}/config`)
    } catch (error) {
      this.setState({ error })
      return
    }

    this.setState({ guild, config: config || '' })
  }

  handleConfigChange = (config) => {
    this.setState({ config })
  }

  handleSaveClick = async () => {
    await API.patch(`/api/guild/${this.guildId}/config`, {
      body: this.state.config,
    })
  }

  render() {
    const { guild, config, error } = this.state

    if (error != null) {
      return <p>{error.toString()}</p>
    }

    if (guild == null) {
      return <p>Loading...</p>
    }

    return (
      <div className="guild-detail">
        <h2>
          <GuildIcon guild={guild} />
          {guild.name}
        </h2>
        <div className="guild-config">
          <ConfigEditor
            value={config}
            onChange={this.handleConfigChange}
            fontSize={18}
            showPrintMargin={false}
            editorProps={{ $blockScrolling: true }}
            setOptions={{ tabSize: 2, showFoldWidgets: false }}
          />

          <Button onClick={this.handleSaveClick}>Save</Button>
        </div>
      </div>
    )
  }
}
