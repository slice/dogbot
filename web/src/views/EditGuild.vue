<template>
  <div class="edit-guild" v-if="guild != null">
    <header>
      <guild-icon :guild="guild"/>
      <h2>{{ guild.name }}</h2>
    </header>
    <div class="flash" v-if="flash">{{ flash }}</div>

    <!-- guild information -->
    <ul>
      <li>Members: {{ guild.members }}</li>
      <li>Owner: <strong>{{ guild.owner.tag }}</strong> (<code>{{ guild.owner.id }}</code>)</li>
    </ul>

    <!-- guild config -->
    <h3>Configuration{{ dirty ? '*' : '' }}</h3>
    <div class="error" v-if="error">{{ error }}</div>
    <!-- buttons above textarea -->
    <div class="toolbar">
      <button type="button" :disabled="error" @click="save"
        title="You can also press CTRL+S (or CMD+S on Macs).">Save Changes</button>
      <spinner v-if="saving"/>
    </div>
    <ace-editor v-if="config != null"
      @change="processEditorChange"
      @save="save"
      :content="config"
      lang="yaml"
      theme="chrome"/>
    <spinner v-else/>
  </div>
</template>

<script>
import API from '@/api'
import GuildIcon from '@/components/GuildIcon'
import Spinner from '@/components/Spinner'

import AceEditor from '@/components/AceEditor'
import 'brace/mode/yaml'
import 'brace/ext/searchbox'
import 'brace/theme/chrome'

import joi from 'joi-browser'
import yaml from 'js-yaml'

let schema = joi.compile(
  joi.object({
    editors: joi.array().items(joi.number().label('user id')),
    autoresponses: joi.object().keys().pattern(/.{4}/, joi.string()),
    gatekeeper: joi.object({
      enabled: joi.boolean(),
      checks: joi.object(),
      bounce_message: joi.string().min(1),
      broadcast_channel: joi.number().label('broadcast channel id')
    }),
    measure_gateway_lag: joi.boolean()
  })
)

function validate (raw) {
  let doc = yaml.safeLoad(raw)
  let { error } = joi.validate(doc, schema, {
    convert: false
  })
  if (error) throw error
}

export default {
  name: 'edit-guild',
  data () {
    return {
      guild: null,
      dirty: false,
      flash: null,
      flashing: false,
      error: null,
      saving: false,
      config: null
    }
  },
  components: { GuildIcon, AceEditor, Spinner },
  methods: {
    async save () {
      if (this.error) return
      if (this.config == null) return

      this.saving = true
      console.log('Saving...')
      await API.patch(`/api/guild/${this.guildId}/config`, this.config, {
        headers: {
          'content-type': 'text/yaml'
        }
      })
      this.showFlash('Saved.')
      this.saving = false
      this.dirty = false
    },

    showFlash (flash) {
      if (this.flashing) return
      this.flash = flash
      this.flashing = true
      setTimeout(() => {
        this.flash = null
        this.flashing = false
      }, 2000)
    },

    processEditorChange (content) {
      try {
        validate(content)
        this.error = null
      } catch (error) {
        this.error = error.message || error.toString()
        return
      }
      this.dirty = true
      this.config = content
    }
  },
  async created () {
    let guilds = await API.guilds()
    this.guild = guilds.find(g => g.id === this.guildId)

    const config = (await API.get(`/api/guild/${this.guildId}/config`)).config || ''
    this.config = config
  },
  computed: {
    guildId () { return this.$route.params.id }
  }
}
</script>

<style scoped lang="stylus">
h2
  vertical-align middle

.toolbar
  margin-bottom 1rem
  display flex
  align-items center
  button
    background #dedede
    border none
    padding 0.5em 1em
    font inherit
    border-radius 0.15rem
    cursor pointer
    &[disabled]
      cursor not-allowed
    margin-right 1em

.error
  padding 0.5em
  background pink
  white-space pre
  margin-bottom 1rem
  font 12px monospace
  border-radius 0.15rem

.guild-icon
  margin-right 1em

header
  display flex
  flex-flow row nowrap
  align-items center
  margin-bottom 1rem
  h2
    margin 0 !important

.editor
  width 100%
  height 25em

.flash
  position fixed
  color darken(lightgreen, 70%)
  bottom 1rem
  left 1rem
  padding 0.5em 1em
  border-radius 0.15rem
  background lightgreen
  animation out 2s linear 1 forwards
  z-index 100

@keyframes out
  50%
    opacity 1

  100%
    opacity 0.0

.ace_editor
  font 13pt Menlo, Consolas, monospace

@media (max-width: 550px)
  header h2
    width 100%
    white-space nowrap
    overflow hidden
    text-overflow ellipsis
  .guild-icon
    display none
  .ace_editor
    font-size 1rem
</style>
