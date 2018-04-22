<template>
  <div id="app">
    <Status/>
    <router-view/>
  </div>
</template>

<script>
import Status from '@/components/Status'

export default {
  name: 'app',
  components: { Status }
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

*
  box-sizing border-box
</style>
