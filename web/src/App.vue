<template>
  <div id="app">
    <topbar :loggedIn="loggedIn"/>
    <div class="content" :class="{ 'logged-out': loggedIn === false }">
      <!-- loggedIn will be null before fetching, so show nothing while loading -->
      <router-view v-if="loggedIn === true"/>
      <login v-if="loggedIn === false"/>
    </div>
  </div>
</template>

<script>
import Topbar from '@/components/Topbar'
import Login from '@/components/Login'
import API from '@/api'

export default {
  name: 'app',
  data () {
    return { loggedIn: null }
  },
  components: { Topbar, Login },
  async beforeCreate () {
    let resp = await API.request('/auth/user')
    this.loggedIn = resp.active
  }
}
</script>

<style lang="stylus">
html, body
  margin 0

html, body, #app
  width 100%
  height 100%

#app
  font 16px/1.5 system-ui, sans-serif

.content
  &.logged-out
    width 100%
    height 100%
    display flex
    justify-content center
    align-items center
  &:not(.logged-out)
    max-width 950px
    margin 0 auto
    padding 1em
  h2:first-child
    margin-top 0

*
  box-sizing border-box
</style>
