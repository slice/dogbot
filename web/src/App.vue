<template>
  <div id="app">
    <topbar :loggedIn="loggedIn" @statusUpdate="statusUpdate"/>
    <div class="content" :class="{ 'logged-out': loggedIn === false }">
      <!-- loggedIn will be null before fetching, so show nothing while loading -->
      <router-view :class="{ inactive: !ready }" v-if="loggedIn === true"/>
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
    return { loggedIn: null, ready: false }
  },
  components: { Topbar, Login },
  async beforeCreate () {
    let resp = await API.request('/auth/user')
    this.loggedIn = resp.active
  },
  methods: {
    statusUpdate (ready) {
      this.ready = ready
    }
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

.inactive
  opacity 0.3
  pointer-events none

*
  box-sizing border-box
</style>
