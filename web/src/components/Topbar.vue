<template>
  <div class="topbar">
    <router-link to="/" class="brand"><strong>dog</strong></router-link>
    <div class="status">
      <div class="dot" :style="{ 'background-color': color }"></div>
      <div class="user" v-if="user != null">
        <img class="icon" draggable="false"
          :src="`https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=64`">
        <span class="name">{{ user.username }}#{{ user.discriminator }}</span>
      </div>
    </div>
    <div class="links">
      <a href="https://github.com/slice/dogbot" class="promo" target="_blank" rel="noreferrer">
        <font-awesome-icon :icon="githubIcon"/>
        Open Source
      </a>
      <a href="https://patreon.com/slcxyz" class="promo" target="_blank" rel="noreferrer">
        <font-awesome-icon :icon="patreonIcon"/>
        Donate on Patreon
      </a>
      <a href="/auth/logout" v-if="loggedIn">
        <font-awesome-icon :icon="signOutIcon"/>
        <span>Sign Out</span>
      </a>
    </div>
  </div>
</template>

<script>
import API from '@/api'
import FontAwesomeIcon from '@fortawesome/vue-fontawesome'
import { faGithub, faPatreon } from '@fortawesome/fontawesome-free-brands'
import { faSignOutAlt } from '@fortawesome/fontawesome-free-solid'

const COLORS = {
  green: 'hsla(128, 100%, 30%, 1)',
  red: 'hsla(0, 100%, 30%, 1)'
}

export default {
  name: 'topbar',
  props: {
    loggedIn: Boolean
  },
  data () {
    return {
      color: COLORS.red,
      user: null
    }
  },
  computed: {
    githubIcon () { return faGithub },
    patreonIcon () { return faPatreon },
    signOutIcon () { return faSignOutAlt }
  },
  components: { FontAwesomeIcon },
  async mounted () {
    let resp = await API.get('/api/status')
    this.$emit('statusUpdate', resp.ready)
    if (resp.ready) {
      this.color = COLORS.green
    }
  },
  watch: {
    loggedIn: async function (new_, old) {
      if (!new_) return
      let { user } = await API.get('/auth/user')
      this.user = user
    }
  }
}
</script>

<style scoped lang="stylus">
.topbar
  background #eee
  color #444
  padding 1em 2em
  display flex
  align-items center

.status
  display flex
  align-items center

.user
  display flex
  align-items center
  .icon
    display block
    width 1.5em
    height 1.5em
    object-fit cover
    border-radius 100%
    margin-right 0.5em

.brand
  color inherit
  text-decoration inherit
  margin-right 1em

.links
  margin-left auto
  a
    color inherit
    text-decoration none
    &:not(:last-child)
      margin-right 1em
    svg
      margin-right 0.5em

.dot
  display inline-block
  width 10px
  height 10px
  border-radius 100%
  margin-right 2em

@media (max-width: 700px)
  .topbar
    padding 0.5em 1em !important

  .links .promo
    display none
  .links a
    svg
      margin 0
    span
      display none
</style>
