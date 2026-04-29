import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ScenarioSetupView from '../views/ScenarioSetupView.vue'
import SimulationView from '../views/SimulationView.vue'
import GameView from '../views/GameView.vue'
import BatchView from '../views/BatchView.vue'
import BusinessSimulationView from '../views/BusinessSimulationView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/setup', name: 'setup', component: ScenarioSetupView },
  { path: '/game/:id', name: 'game', component: GameView, props: true },
  { path: '/simulation/business/:id', name: 'business-simulation', component: BusinessSimulationView },
  { path: '/simulation/:id', name: 'simulation', component: SimulationView, props: true },
  { path: '/batch', name: 'batch', component: BatchView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
