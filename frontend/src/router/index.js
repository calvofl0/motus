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

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
