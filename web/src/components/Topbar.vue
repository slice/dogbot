<template>
  <div class="topbar">
    <div class="brand"><strong>dog</strong></div>
    <div class="status">
      <div class="dot" :style="{ 'background-color': color }"></div>
      {{ message }}
    </div>
    <div class="links">
      <a href="https://github.com/slice/dogbot" target="_blank" rel="noreferrer">
        <font-awesome-icon :icon="githubIcon"/>
        Open Source
      </a>
      <a href="https://patreon.com/slcxyz" target="_blank" rel="noreferrer">
        <font-awesome-icon :icon="patreonIcon"/>
        Donate on Patreon
      </a>
    </div>
  </div>
</template>

<script>
import API from '@/api'
import FontAwesomeIcon from '@fortawesome/vue-fontawesome'
import brands from '@fortawesome/fontawesome-free-brands'

const COLORS = {
  green: 'hsla(128, 100%, 70%, 1)',
  red: 'hsla(0, 100%, 70%, 1)'
}

export default {
  name: 'status',
  data () {
    return {
      color: COLORS.red,
      message: '...'
    }
  },
  computed: {
    githubIcon () { return brands.faGithub },
    patreonIcon () { return brands.faPatreon }
  },
  components: { FontAwesomeIcon },
  async mounted () {
    let resp = await API.request('/api/status')
    if (resp.ready) {
      this.color = COLORS.green
      this.message = 'Connected'
    } else {
      this.message = 'Disconnected'
    }
  }
}
</script>

<style scoped lang="stylus">
.topbar
  background #222
  color #fff
  padding 1em 2em
  display flex
  align-items center

.brand
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
  margin-right 0.5em

@media (max-width: 550px)
  .topbar
    padding 0.5em 1em !important

  .links
    display none
</style>
