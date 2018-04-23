<template>
  <div class="edit-guild" v-if="guild != null">
    <h2><guild-icon :guild="guild"/> {{ guild.name }}</h2>
    <div class="flash" v-if="flash">{{ flash }}</div>
    <ul>
      <li>Members: {{ guild.members }}</li>
      <li>Owner: <strong>{{ guild.owner.tag }}</strong> (<code>{{ guild.owner.id }}</code>)</li>
    </ul>
    <h3>Configuration{{ dirty ? '*' : '' }}</h3>
    <div class="error" v-if="error">{{ error }}</div>
    <button type="button" :disabled="error" @click="save" title="You can also press CTRL+S (or CMD+S on Macs).">Save Changes</button>
    <ace-editor @change="processEditorChange" @save="save" :content="loadedConfig" lang="yaml" theme="chrome"/>
  </div>
</template>

<script>
import API from '@/api'
import GuildIcon from '@/components/GuildIcon'

import AceEditor from '@/components/AceEditor'
import 'brace/mode/yaml'
import 'brace/ext/searchbox'
import 'brace/theme/chrome'

import joi from 'joi-browser'
import yaml from 'js-yaml'

let schema = joi.compile(
  joi.object().keys({
    editors: joi.array().items(joi.number().label('user id'))
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
      config: '',
      loadedConfig: '',
      dirty: false,
      flash: null,
      flashing: false,
      error: null
    }
  },
  components: { GuildIcon, AceEditor },
  methods: {
    async save () {
      if (this.error) return
      console.log('Saving...')
      await API.patch(`/api/guild/${this.guildId}/config`, this.config, {
        headers: {
          'content-type': 'text/yaml'
        }
      })
      this.showFlash('Saved.')
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
    this.loadedConfig = (await API.get(`/api/guild/${this.guildId}/config`)).config || ''
  },
  computed: {
    guildId () { return this.$route.params.id }
  }
}
</script>

<style scoped lang="stylus">
h2
  vertical-align middle

button
  background #dedede
  border none
  padding 0.5em 1em
  display block
  font inherit
  border-radius 0.15rem
  margin-bottom 1rem
  cursor pointer
  &[disabled]
    cursor not-allowed

.error
  padding 0.5em
  background pink
  white-space pre
  margin-bottom 1rem
  font 12px monospace
  border-radius 0.15rem

.guild-icon
  margin-right 0.5rem
  height 0.8em !important
  width 0.8em !important

.editor
  width 100%
  height 25em

.flash
  position fixed
  color green
  bottom 1rem
  left 1rem
  padding 0.5em 1em
  border-radius 0.15rem
  background lightgreen
  animation out 2s linear 1 forwards

@keyframes out
  50%
    opacity 1

  100%
    opacity 0.0

.ace_editor
  font 13pt Menlo, Consolas, monospace
</style>
