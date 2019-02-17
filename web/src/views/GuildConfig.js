import React, { Component } from 'react'
import 'styled-components/macro'

import './GuildConfig.scss'
import API from '../api'
import ShrinkableText from '../components/ShrinkableText'
import Notice from '../components/Notice'
import Button from '../components/Button'
import { GuildIcon } from '../components/Icon'
import ConfigEditor from '../components/ConfigEditor'

function isMac() {
  return navigator.userAgent.includes('Macintosh')
}

export default class GuildConfig extends Component {
  state = {
    guild: null,
    error: null,
    saved: false,
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
    window.addEventListener('keydown', this.handleKeydown)
  }

  componentWillUnmount() {
    window.removeEventListener('keydown', this.handleKeydown)
  }

  handleKeydown = (event) => {
    const modifierHeld = isMac() ? event.metaKey : event.ctrlKey
    if (modifierHeld && event.key === 's') {
      this.save()
      event.preventDefault()
    }
  }

  handleConfigChange = (config) => {
    this.setState({ config, saved: false })
  }

  handleSaveClick = () => {
    this.save()
  }

  async save() {
    try {
      await API.patch(`/api/guild/${this.guildId}/config`, {
        body: this.state.config,
      })
    } catch (error) {
      const { message } = error
      this.setState({ error: message })
      return
    }

    this.setState({ saved: true, error: null })
  }

  render() {
    const { guild, config, error, saved } = this.state

    if (error != null && guild == null) {
      return <Notice mood="danger">Couldn't load server: {error}</Notice>
    }

    if (guild == null) {
      return <p>Loading...</p>
    }

    return (
      <div className="guild-detail">
        <h2>
          <GuildIcon guild={guild} />
          <ShrinkableText>{guild.name}</ShrinkableText>
        </h2>

        {error != null ? (
          <Notice mood="danger">Couldn't save: {error}</Notice>
        ) : null}

        {saved ? <Notice mood="success">Saved.</Notice> : null}

        <div className="guild-config">
          <ConfigEditor
            value={config}
            onChange={this.handleConfigChange}
            fontSize={18}
            showPrintMargin={false}
            editorProps={{ $blockScrolling: true }}
            setOptions={{ tabSize: 2, showFoldWidgets: false }}
          />

          <Button onClick={this.handleSaveClick} css="margin-top: 1rem">
            Save
          </Button>

          <small css="display: block; margin-top: 1rem; opacity: 0.5;">
            You can also press {isMac() ? '⌘' : 'CTRL+'}S to save.
          </small>
        </div>
      </div>
    )
  }
}
