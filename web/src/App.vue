<template>
  <div id="app">
    <topbar :loggedIn="loggedIn"/>
    <div class="content" :class="{ 'logged-out': !loggedIn }">
      <!-- loggedIn will be null before fetching, so show nothing while loading -->
      <router-view v-if="loggedIn === true"/>
      <login v-if="loggedIn === false"/>
      <spinner v-if="loggedIn == null"/>
    </div>
  </div>
</template>

<script>
import Topbar from '@/components/Topbar'
import Login from '@/components/Login'
import API from '@/api'
import Spinner from '@/components/Spinner'

export default {
  name: 'app',
  data () {
    return { loggedIn: null }
  },
  components: { Topbar, Login, Spinner },
  async beforeCreate () {
    let resp = await API.get('/auth/user')
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
  padding 1em
  width 100%
  height 100%
  &.logged-out
    display flex
    justify-content center
    align-items center
  &:not(.logged-out)
    max-width 950px
    margin 0 auto
  h2:first-child
    margin-top 0

*
  box-sizing border-box
</style>
