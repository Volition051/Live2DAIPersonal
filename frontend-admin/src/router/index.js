import { createRouter, createWebHistory } from 'vue-router'

// 路由守卫：检查是否有 admin_token，没有则跳转登录页
const authGuard = (to, from, next) => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    next()
  } else {
    next('/login')
  }
}

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/knowledge',
    children: [
      {
        path: 'knowledge',
        name: 'KnowledgeList',
        component: () => import('@/views/KnowledgeList.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'upload',
        name: 'Upload',
        component: () => import('@/views/Upload.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'visitor-stats',
        name: 'VisitorStats',
        component: () => import('@/views/VisitorStats.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'admin-chat',
        name: 'AdminChat',
        component: () => import('@/views/AdminChat.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'admin-manage',
        name: 'AdminManage',
        component: () => import('@/views/AdminManage.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'database',
        name: 'DatabaseBrowser',
        component: () => import('@/views/DatabaseBrowser.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'attractions',
        name: 'Attractions',
        component: () => import('@/views/attractions.vue'),
        meta: { title: '景点管理', requireAuth: true, requireSuper: true }
      },
      {
        path: 'Live2DController',
        name: 'Live2DController',
        component: () => import('@/views/Live2DController.vue'),
        meta: { title: '数字人管理', requireAuth: true, requireSuper: true }
      },
      // 新增：数据大屏
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        beforeEnter: authGuard
      },
      // 新增：游客感受度报告
      {
        path: 'sentiment-report',
        name: 'SentimentReport',
        component: () => import('@/views/SentimentReport.vue'),
        beforeEnter: authGuard
      },
      {
        path: 'audio-settings',
        name: 'AudioSettings',
        component: () => import('@/views/AudioSettings.vue'),
        meta: { title: '音频设置', requireAuth: true, requireSuper: true }
      },
      {
        path: 'appearance-settings',
        name: 'AppearanceSettings',
        component: () => import('@/views/AppearanceSettings.vue'),
        meta: { title: '前端外观设置', requireAuth: true, requireSuper: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router