// Unit tests for the dashboard's client-side logic: URL round-tripping,
// filtering and pagination. `npm test` runs them; CI runs them too.
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'happy-dom',
    include: ['test/**/*.test.js'],
  },
});
