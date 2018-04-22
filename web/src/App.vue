<template>
  <div id="app">
    <Status/>
    <div class="content" :class="{ 'logged-out': loggedIn === false }">
      <!-- loggedIn will be null before fetching, so show nothing while loading -->
      <router-view v-if="loggedIn === true"/>
      <Login v-if="loggedIn === false"/>
    </div>
  </div>
</template>

<script>
import Status from '@/components/Status'
import Login from '@/components/Login'
import API from '@/api'

export default {
  name: 'app',
  data () {
    return { loggedIn: null }
  },
  components: { Status, Login },
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

*
  box-sizing border-box
</style>
