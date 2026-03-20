<template>
  <div class="setup">
    <h2>Scenario Setup</h2>
    <div v-if="store.error" class="error">{{ store.error }}</div>
    <div class="scenario-list">
      <div
        v-for="s in store.scenarios"
        :key="s.name"
        class="scenario-card"
        :class="{ selected: selected === s.name }"
        @click="selected = s.name"
      >
        <h3>{{ s.display_name }}</h3>
        <p>{{ s.description }}</p>
      </div>
      <div v-if="!store.scenarios.length" class="loading">Loading scenarios...</div>
    </div>
    <div class="controls">
      <label>
        Max Turns:
        <input v-model.number="maxTurns" type="number" min="1" max="200" />
      </label>
      <button :disabled="!selected" @click="startSim" class="start-btn">
        Start Simulation
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSimulationStore } from '../store/simulation'

const store = useSimulationStore()
const router = useRouter()
const selected = ref(null)
const maxTurns = ref(72)

onMounted(() => store.loadScenarios())

async function startSim() {
  await store.createAndStart(selected.value, maxTurns.value)
  if (store.currentSimulationId) {
    router.push({ name: 'simulation', params: { id: store.currentSimulationId } })
  }
}
</script>

<style scoped>
.setup { max-width: 800px; margin: 0 auto; }
h2 { margin-bottom: 1.5rem; color: #4cc9f0; }
.scenario-list { display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem; }
.scenario-card { background: #16213e; padding: 1.25rem; border-radius: 8px; cursor: pointer; border: 2px solid transparent; transition: border-color 0.2s; }
.scenario-card:hover { border-color: #0f3460; }
.scenario-card.selected { border-color: #4cc9f0; }
.scenario-card h3 { color: #e0e0e0; margin-bottom: 0.5rem; }
.scenario-card p { color: #888; font-size: 0.9rem; }
.controls { display: flex; gap: 1.5rem; align-items: center; }
.controls label { color: #888; }
.controls input { width: 80px; padding: 0.4rem; background: #16213e; color: #e0e0e0; border: 1px solid #0f3460; border-radius: 4px; }
.start-btn { padding: 0.6rem 1.5rem; background: #4cc9f0; color: #1a1a2e; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
.start-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error { background: #4a1c1c; color: #ff6b6b; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; }
.loading { color: #888; text-align: center; padding: 2rem; }
</style>
