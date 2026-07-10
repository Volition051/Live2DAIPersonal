import { createRouter, createWebHashHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const routes = [
  {
    path: "/",
    name: "Chat",
    component: () => import("@/views/Chat.vue"), //主页面
    meta: { requiresAuth: true },
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue"), //登录页面
  },
  {
    path: "/map",
    name: "Map",
    component: () => import("@/views/MapView.vue"), // 地图页面
  },
  {
    path: "/live2d-test",
    name: "Live2DTest",
    component: () => import("@/views/Live2DTest.vue"), // Live2D 肢体控制测试
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to, from) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
});

export default router;
