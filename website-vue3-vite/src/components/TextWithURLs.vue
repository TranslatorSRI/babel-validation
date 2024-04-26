<template>
  <span class="text">{{text}}</span>
  <div v-if="Object.keys(urls).length > 0">
    <template v-for="name in Object.keys(urls)">
      <a class="small" target="_blank" :href="urls[name]">{{name}}</a>
    </template>
  </div>
</template>

<script>
export default {
  props: {
    text: String,
    urls: {
      type: Object,
      default: {}
    }
  }
}
</script>

<style scoped>
.text { margin-bottom: 0 }
a.small {
  margin: 0;
  padding: 0 1em 0 0;
}
</style>