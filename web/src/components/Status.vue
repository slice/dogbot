<template>
  <div class="status">
    <div class="dot" :style="{ 'background-color': color }"></div>
    {{ message }}
  </div>
</template>

<script>
import API from '@/api'

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
  async mounted () {
    let resp = await API.request('/api/status')
    if (resp.ready) {
      this.color = COLORS.green
      this.message = `Ready. Connected to ${resp.guilds} guilds`
    } else {
      this.message = 'Cannot connect to Dog'
    }
  }
}
</script>

<style scoped lang="stylus">
.status
  background #222
  color #fff
  padding 0.5em 1em
  display flex
  align-items center

.dot
  display inline-block
  width 10px
  height 10px
  border-radius 100%
  margin-right 0.5em
</style>
