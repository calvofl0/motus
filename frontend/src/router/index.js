import { createRouter, createWebHistory } from 'vue-router'
import EasyMode from '../views/EasyMode.vue'
import ExpertMode from '../views/ExpertMode.vue'

const routes = [
  {
    path: '/',
    name: 'easy',
    component: EasyMode,
    meta: { mode: 'easy' }
  },
  {
    path: '/expert',
    name: 'expert',
    component: ExpertMode,
    meta: { mode: 'expert' }
  }
]

// Remove known route paths, handle missing trailing slash
let base = window.location.pathname.replace(/\/(expert)?\/?$/, '')
// Ensure we have at least '/' and add trailing slash
base = base || '/'
if (base !== '/' && !base.endsWith('/')) {
  base += '/'
}

const router = createRouter({
  history: createWebHistory(base),
  routes
})

export default router
