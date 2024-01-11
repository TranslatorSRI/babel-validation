<script setup lang="ts">
    defineProps<{
      title?: string
      style?: string
    }>()
</script>

<template>
  <div class="card" :style="style">
    <div class="card-body">
      <h5 v-if="title" class="card-title">{{title}}</h5>
      <slot />
    </div>
  </div>
</template>

<style scoped>

</style>