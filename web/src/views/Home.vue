<template>
  <div class="home">
    <h2>Guilds</h2>
    <div class="guilds">
      <div class="empty" v-if="guilds && !guilds.length">Nothing here.</div>
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
      guilds: null
    }
  },
  components: { GuildIcon, Spinner },
  async created () {
    this.guilds = await API.guilds()
  }
}
</script>

<style scoped lang="stylus">
.empty
  color #999
.guild
  display flex
  align-items center
  color inherit
  text-decoration none
  border-radius 0.15rem
  padding 0.5em 1em
  .guild-icon
    display block
    margin-right 1em
  &:hover
    background #eee
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
