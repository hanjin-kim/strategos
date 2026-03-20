import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ScenarioSetupView from '../views/ScenarioSetupView.vue'
import SimulationView from '../views/SimulationView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/setup', name: 'setup', component: ScenarioSetupView },
  { path: '/simulation/:id', name: 'simulation', component: SimulationView, props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
