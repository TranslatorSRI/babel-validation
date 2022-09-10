<template>
  <p>{{text}}</p>
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