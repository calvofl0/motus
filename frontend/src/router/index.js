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

const base = window.location.pathname.replace(/\/[^/]*$/, '/')

const router = createRouter({
  history: createWebHistory(base),
  routes
})

export default router
