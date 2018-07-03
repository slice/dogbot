<template>
  <div class="home">
    <h2>Servers</h2>
    <div class="ghost-notice" v-if="ghost">
      <strong>Warning:</strong> You do not share any servers with Dog.
    </div>
    <div class="guilds">
      <div class="empty" v-if="guilds && !guilds.length">No servers that you can edit.</div>
      <router-link :to="`/guild/${guild.id}`" class="guild" v-for="guild of guilds" :key="guild.id">
        <guild-icon :guild="guild"/>
        <strong>{{ guild.name }}</strong>&nbsp;
        <span class="count">({{ guild.members }} member{{ guild.members === 1 ? '' : 's' }})</span>
      </router-link>
      <spinner v-if="!guilds"/>
    </div>
  </div>
</template>

<script>
import API from '@/api'
import GuildIcon from '@/components/GuildIcon'
import Spinner from '@/components/Spinner'

export default {
  name: 'home',
  data () {
    return {
      guilds: null,
      ghost: false
    }
  },
  components: { GuildIcon, Spinner },
  async created () {
    const resp = await API.guilds()

    if (resp.error) {
      if (resp.code === 'UNKNOWN_DISCORD_USER') {
        this.ghost = true
      }
      this.guilds = []
    } else {
      this.guilds = resp
    }
  }
}
</script>

<style scoped lang="stylus">
.ghost-notice
  background pink
  border-radius 0.15em
  padding 1em
  margin 1em
.empty
  color #999
.guild
  display flex
  align-items center
  color inherit
  text-decoration none
  border-radius 0.15rem
  padding 0.5em 1em
  transition background .1s
  .guild-icon
    display block
    flex-shrink 0
    margin-right 1em
  &:hover
    background #efefef
  .count
    color #999

@media (max-width: 650px)
  .count
    display none

@media (max-width: 550px)
  .guild
    padding 0 0 0.5em 0 !important
    strong
      width 100%
      white-space nowrap
      overflow hidden
      text-overflow ellipsis
</style>
