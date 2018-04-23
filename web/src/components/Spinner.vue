<template>
  <div class="spinner"></div>
</template>

<script>
export default {
  name: 'spinner'
}
</script>

<style scoped lang="stylus">
.spinner
  display inline-block
  width 2em
  height 2em
  background #0af
  animation 800ms ease-in-out infinite pulse
  border-radius 50%

@keyframes pulse
  0%
    transform scale(0.1)
  50%
    transform scale(1)
  100%
    transform scale(0.1)
</style>
