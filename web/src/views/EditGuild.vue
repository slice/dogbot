<template>
  <div class="edit-guild" v-if="guild != null">
    <h2><guild-icon :guild="guild"/> {{ guild.name }}</h2>
    <ul>
      <li>Members: {{ guild.members }}</li>
      <li>Owner: <strong>{{ guild.owner.tag }}</strong> (<code>{{ guild.owner.id }}</code>)</li>
    </ul>
    <h3>Configuration</h3>
    ...
  </div>
</template>

<script>
import API from '@/api'
import GuildIcon from '@/components/GuildIcon'

export default {
  name: 'edit-guild',
  data () {
    return {
      guild: null
    }
  },
  components: { GuildIcon },
  async created () {
    let guilds = await API.guilds()
    this.guild = guilds.find(g => g.id === this.guildId)
  },
  computed: {
    guildId () { return this.$route.params.id }
  }
}
</script>

<style scoped lang="stylus">
h2
  vertical-align middle
.guild-icon
  margin-right 0.5rem
  height 0.8em !important
  width 0.8em !important
</style>
