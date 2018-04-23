<template>
  <img :src="guild.icon_url" class="guild-icon">
</template>

<script>
export default {
  name: 'guild-icon',
  props: {
    guild: Object
  }
}
</script>

<style scoped lang="stylus">
.guild-icon
  object-fit cover
  width 2em
  height 2em
  border-radius 50%
</style>
