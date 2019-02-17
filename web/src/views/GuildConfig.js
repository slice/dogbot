import React, { Component } from 'react'
import styled from 'styled-components'
import 'styled-components/macro'

import { monospace } from '../theming'
import validate from '../schema'
import API from '../api'
import ShrinkableText from '../components/ShrinkableText'
import Notice from '../components/Notice'
import Button from '../components/Button'
import { GuildIcon } from '../components/Icon'
import ConfigEditor from '../components/ConfigEditor'

function isMac() {
  return navigator.userAgent.includes('Macintosh')
}

function prettifyValidationError(message) {
  const unwantedMessage =
    '\n If "null" is intended as an empty value be sure to mark the schema as `.nullable()`'
  return message.replace(unwantedMessage, '').replace('ValidationError: ', '')
}

const StyledGuildConfig = styled.div`
  h2 {
    display: flex;
    align-items: center;

    .icon {
      margin-right: 1rem;
    }
  }
`

export default class GuildConfig extends Component {
  state = {
    guild: null,
    error: null,
    lint: null,
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

  handleConfigChange = async (config) => {
    this.setState({ config, saved: false })

    try {
      await validate(config)
      this.setState({ lint: null })
    } catch (error) {
      this.setState({ lint: prettifyValidationError(error.toString()) })
    }
  }

  handleSaveClick = () => {
    this.save()
  }

  async save() {
    if (this.state.lint != null) {
      // prevent saving if there are errors in the config
      return
    }

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
    const { guild, config, error, lint, saved } = this.state

    if (error != null && guild == null) {
      return <Notice mood="danger">Couldn't load server: {error}</Notice>
    }

    if (guild == null) {
      return <p>Loading...</p>
    }

    return (
      <StyledGuildConfig>
        <h2>
          <GuildIcon guild={guild} />
          <ShrinkableText>{guild.name}</ShrinkableText>
        </h2>

        {error != null ? (
          <Notice mood="danger">Couldn't save: {error}</Notice>
        ) : null}

        {lint != null ? (
          <Notice mood="danger">Invalid config: {lint.toString()}</Notice>
        ) : null}

        {saved ? <Notice mood="success">Saved.</Notice> : null}

        <div className="guild-config">
          <ConfigEditor
            value={config}
            onChange={this.handleConfigChange}
            fontSize={18}
            showPrintMargin={false}
            editorProps={{ $blockScrolling: true }}
            setOptions={{
              tabSize: 2,
              showFoldWidgets: false,
              fontFamily: monospace,
            }}
          />

          <Button
            onClick={this.handleSaveClick}
            css="margin-top: 1rem"
            disabled={lint != null}
          >
            Save
          </Button>

          <small css="display: block; margin-top: 1rem; opacity: 0.5;">
            You can also press {isMac() ? '⌘' : 'CTRL+'}S to save.
          </small>
        </div>
      </StyledGuildConfig>
    )
  }
}
