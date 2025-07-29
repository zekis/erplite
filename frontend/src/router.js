import { createRouter, createWebHistory } from 'vue-router'
import Home from './pages/Home.vue'
import Scheduler from './pages/Scheduler.vue'

function sessionUser() {
  let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
  let _sessionUser = cookies.get('user_id')
  if (_sessionUser === 'Guest') {
    _sessionUser = null
  }
  return _sessionUser
}

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
  },
  {
    path: '/scheduler',
    name: 'Scheduler',
    component: Scheduler,
  },
  {
    path: '/vue-scheduler',
    name: 'VueScheduler',
    component: () => import('./pages/VueScheduler.vue'),
  },
]

const router = createRouter({
  history: createWebHistory('/erplite'),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const user = sessionUser()
  
  if (!user) {
    // Redirect to Frappe login if not authenticated
    window.location.href = '/login?redirect-to=/erplite' + to.fullPath
  } else {
    next()
  }
})

export default router
