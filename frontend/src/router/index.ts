import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/profile/setup',
      name: 'ProfileSetup',
      component: () => import('@/views/ProfileSetupView.vue'),
      meta: { auth: true },
    },
    {
      path: '/',
      name: 'Home',
      component: () => import('@/views/NeedPlazaView.vue'),
      meta: { auth: true },
    },
    {
      path: '/needs/new',
      name: 'NeedCreate',
      component: () => import('@/views/NeedCreateView.vue'),
      meta: { auth: true },
    },
    {
      path: '/needs/applications',
      name: 'MyApplications',
      component: () => import('@/views/MyApplicationsView.vue'),
      meta: { auth: true },
    },
    {
      path: '/needs/:id',
      name: 'NeedDetail',
      component: () => import('@/views/NeedDetailView.vue'),
      meta: { auth: true },
    },
    {
      path: '/needs/manage',
      name: 'NeedManage',
      component: () => import('@/views/NeedManageView.vue'),
      meta: { auth: true },
    },
    {
      path: '/needs/:id/matches',
      name: 'MatchResult',
      component: () => import('@/views/MatchResultView.vue'),
      meta: { auth: true },
    },
    {
      path: '/messages',
      name: 'Messages',
      component: () => import('@/views/MessagesView.vue'),
      meta: { auth: true },
    },
    {
      path: '/agent',
      name: 'Agent',
      component: () => import('@/views/AgentView.vue'),
      meta: { auth: true },
    },
    {
      path: '/agent/:sessionId',
      name: 'AgentSession',
      component: () => import('@/views/AgentView.vue'),
      meta: { auth: true },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { auth: true },
    },
    {
      path: '/messages/:userId',
      name: 'MessagesWith',
      component: () => import('@/views/MessagesView.vue'),
      meta: { auth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ],
})

router.beforeEach((to, _from) => {
  const auth = useAuthStore()

  if (to.meta.auth && !auth.isLoggedIn) {
    return '/login'
  }
  if (to.meta.guest && auth.isLoggedIn) {
    return '/'
  }
})

export default router
