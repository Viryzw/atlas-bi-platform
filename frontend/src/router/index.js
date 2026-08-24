import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Chat from '../views/Chat.vue'
import Metrics from '../views/admin/Metrics.vue'
import DataSources from '../views/admin/DataSources.vue'
import Users from '../views/admin/Users.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/chat', component: Chat },
  { path: '/admin/metrics', component: Metrics },
  { path: '/admin/datasources', component: DataSources },
  { path: '/admin/users', component: Users }
]

export default createRouter({
  history: createWebHistory(),
  routes
})