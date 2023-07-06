import { createRouter, createWebHistory } from "vue-router";
import HomeView from "@/views/HomeView.vue";
import NodeNormValidator from "@/views/NodeNormValidator.vue";
import NameResValidator from "@/views/NameResValidator.vue";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView,
    },
    {
      path: "/nodenorm",
      name: "Node Normalization Validator",
      component: NodeNormValidator,
    },
    {
      path: "/nameres",
      name: "Name Resolver Validator",
      component: NameResValidator,
    },
    {
      path: "/about",
      name: "about",
      // route level code-splitting
      // this generates a separate chunk (About.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import("../views/AboutView.vue"),
    },
  ],
});

export default router;
