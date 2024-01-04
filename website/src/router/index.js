import { createRouter, createWebHistory } from "vue-router";
import HomeView from "@/views/HomeView.vue";
import NodeNormValidator from "@/views/NodeNormValidator.vue";
import NameResValidator from "@/views/NameResValidator.vue";
import AutocompleteValidator from "@/views/AutocompleteValidator.vue";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  base: import.meta.env.BASE_URL,
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue"),
    },
    {
      path: "/nodenorm/",
      name: "Node Normalization Validator",
      component: () => import("../views/NodeNormValidator.vue"),
    },
    {
      path: "/nameres/",
      name: "Name Resolver Validator",
      component: () => import("../views/NameResValidator.vue"),
    },
    {
      path: "/autocomplete/",
      name: "Autocomplete Validator",
      component: () => import("../views/AutocompleteValidator.vue"),
    },
    {
      path: "/about/",
      name: "about",
      // route level code-splitting
      // this generates a separate chunk (About.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import("../views/AboutView.vue"),
    },
  ],
});

export default router;
