<template>
  <div class="home">
    <h2>Guilds</h2>
    <div class="guilds">
      <router-link to="/where" class="guild" v-for="guild of guilds" :key="guild.id">
        <strong>{{ guild.name }}</strong>&nbsp;
        <span class="count">({{ guild.members }} member{{ guild.members === 1 ? '' : 's' }})</span>
      </router-link>
    </div>
  </div>
</template>

<script>
import API from '@/api'

export default {
  name: 'home',
  data () {
    return {
      guilds: null
    }
  },
  async created () {
    this.guilds = await API.request('/api/guilds')
  }
}
</script>

<style scoped lang="stylus">
.guild
  display block
  color inherit
  text-decoration none
  border-radius 0.15rem
  padding 0.5em 1em
  &:hover
    background #eee
  .count
    color #999
</style>
