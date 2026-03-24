<template>
  <div class="home">
    <h1>Wargame Simulation Platform</h1>
    <p class="subtitle">AI-powered modern warfare simulation with multi-agent decision making</p>
    <div class="features">
      <div class="feature">
        <h3>CRT Combat</h3>
        <p>Combat Results Table based resolution with terrain modifiers</p>
      </div>
      <div class="feature">
        <h3>WEGO Turns</h3>
        <p>Simultaneous execution with 3-phase turn model</p>
      </div>
      <div class="feature">
        <h3>AI Commanders</h3>
        <p>LLM-powered theater and battalion commanders with OODA loops</p>
      </div>
    </div>
    <div class="actions">
      <router-link to="/setup" class="start-btn">Start Simulation</router-link>
      <router-link to="/batch" class="batch-btn">Batch Analysis</router-link>
    </div>

    <!-- Recent Scenarios -->
    <div v-if="scenarios.length" class="scenario-list">
      <h2>Available Scenarios</h2>
      <div class="scenario-grid">
        <div
          v-for="scenario in scenarios"
          :key="scenario.name"
          class="scenario-card"
          @click="launchScenario(scenario)"
        >
          <div class="scenario-header">
            <span class="scenario-name">{{ scenario.display_name || scenario.name }}</span>
            <span
              class="domain-badge"
              :class="scenario.domain === 'business' ? 'domain-business' : 'domain-military'"
            >
              {{ scenario.domain === 'business' ? 'Business' : 'Military' }}
            </span>
          </div>
          <p v-if="scenario.description" class="scenario-desc">{{ scenario.description }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getScenarios, createSimulation, startSimulation } from '../api/client'

const router = useRouter()
const scenarios = ref([])

onMounted(async () => {
  try {
    scenarios.value = await getScenarios()
  } catch (e) {
    // scenarios list is optional; ignore errors
  }
})

async function launchScenario(scenario) {
  try {
    const { simulation_id } = await createSimulation(scenario.name)
    await startSimulation(simulation_id)
    if (scenario.domain === 'business') {
      router.push({ name: 'business-simulation', params: { id: simulation_id } })
    } else {
      router.push({ name: 'simulation', params: { id: simulation_id } })
    }
  } catch (e) {
    // fall back to setup page on error
    router.push('/setup')
  }
}
</script>

<style scoped>
.home { text-align: center; padding: 3rem 1rem; }
h1 { font-size: 2.5rem; margin-bottom: 0.5rem; color: #4cc9f0; }
.subtitle { color: #888; margin-bottom: 3rem; font-size: 1.1rem; }
.features { display: flex; gap: 2rem; justify-content: center; margin-bottom: 3rem; flex-wrap: wrap; }
.feature { background: #16213e; padding: 1.5rem; border-radius: 8px; width: 250px; border: 1px solid #0f3460; }
.feature h3 { color: #4cc9f0; margin-bottom: 0.5rem; }
.actions { display: flex; gap: 1rem; justify-content: center; margin-bottom: 3rem; }
.start-btn { display: inline-block; padding: 0.75rem 2rem; background: #4cc9f0; color: #1a1a2e; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 1.1rem; }
.start-btn:hover { background: #3db8df; }
.batch-btn { display: inline-block; padding: 0.75rem 2rem; background: #334155; color: #e2e8f0; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 1.1rem; }
.batch-btn:hover { background: #475569; }
.scenario-list { max-width: 900px; margin: 0 auto; text-align: left; }
.scenario-list h2 { font-size: 1.25rem; color: #94a3b8; margin-bottom: 1rem; text-align: center; }
.scenario-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
.scenario-card {
  background: #16213e;
  border: 1px solid #0f3460;
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: border-color 0.2s;
}
.scenario-card:hover { border-color: #4cc9f0; }
.scenario-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.scenario-name { font-weight: 700; color: #e2e8f0; font-size: 14px; }
.domain-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.domain-military { background: #1b3a4b; color: #4cc9f0; }
.domain-business { background: #1c2a14; color: #4ade80; }
.scenario-desc { font-size: 12px; color: #64748b; margin: 0; line-height: 1.4; }
</style>
