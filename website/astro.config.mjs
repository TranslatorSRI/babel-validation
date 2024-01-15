import { defineConfig } from 'astro/config';

import vue from "@astrojs/vue";

// https://astro.build/config
export default defineConfig({
  'base': '/babel-validation/',
  integrations: [vue()]
});