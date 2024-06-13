import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: "/babel-validation/",
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        nodenorm: resolve(__dirname, "nodenorm/index.html"),
        nameres: resolve(__dirname, "nameres/index.html"),
        autocomplete: resolve(__dirname, "autocomplete/index.html"),
        autocomplete_bulk: resolve(__dirname, "autocomplete-bulk/index.html"),
      },
    },
  },
});
