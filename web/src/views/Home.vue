<template>
  <div class="home">
    <login/>
  </div>
</template>

<script>
import Login from '@/components/Login'

export default {
  name: 'home',
  components: {
    Login
  }
}
</script>

<style scoped lang="stylus">
.home
  width 100%
  height 100%
  display flex
  justify-content center
  align-items center
</style>
