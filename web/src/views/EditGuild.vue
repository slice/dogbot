<template>
  <div class="edit-guild" v-if="guild != null">
    <h2><guild-icon :guild="guild"/> {{ guild.name }}</h2>
    <ul>
      <li>Members: {{ guild.members }}</li>
      <li>Owner: <strong>{{ guild.owner.tag }}</strong> (<code>{{ guild.owner.id }}</code>)</li>
    </ul>
    <h3>Configuration</h3>
    <button type="button" @click="save" title="You can also press CTRL+S (or CMD+S on Macs).">Save Changes</button>
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

export default {
  name: 'edit-guild',
  data () {
    return {
      guild: null,
      config: '',
      loadedConfig: ''
    }
  },
  components: { GuildIcon, AceEditor },
  methods: {
    async save () {
      console.log('Saving...')
      await API.patch(`/api/guild/${this.guildId}/config`, this.config, {
        headers: {
          'content-type': 'text/yaml'
        }
      })
    },

    processEditorChange (content) {
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

.guild-icon
  margin-right 0.5rem
  height 0.8em !important
  width 0.8em !important

.editor
  width 100%
  height 25em

.ace_editor
  font 13pt Menlo, Consolas, monospace
</style>
