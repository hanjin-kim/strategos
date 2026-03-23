<template>
  <div class="simulation">
    <div class="header">
      <h2>Simulation</h2>
      <div class="status-bar">
        <SideToggle />
        <span class="status" :class="store.status">{{ store.status || 'loading' }}</span>
        <span>Turn {{ store.currentTurn }} / {{ store.maxTurns }}</span>
        <button v-if="store.isRunning" @click="store.stop()" class="stop-btn">Stop</button>
      </div>
    </div>
    <div class="layout">
      <div class="map-panel">
        <BattlefieldMap />
      </div>
      <div class="side-panel">
        <ForceStatus />
        <NarrativePanel />
        <TurnTimeline />
        <CommandLog />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useSimulationStore } from '../store/simulation'
import BattlefieldMap from '../components/Simulation/BattlefieldMap.vue'
import ForceStatus from '../components/Simulation/ForceStatus.vue'
import TurnTimeline from '../components/Simulation/TurnTimeline.vue'
import CommandLog from '../components/Simulation/CommandLog.vue'
import SideToggle from '../components/Simulation/SideToggle.vue'
import NarrativePanel from '../components/Simulation/NarrativePanel.vue'

const props = defineProps({ id: String })
const store = useSimulationStore()

onMounted(async () => {
  store.currentSimulationId = props.id
  await store.fetchStatus()
  await store.fetchState()
  if (store.isRunning) store.startPolling()
})

onUnmounted(() => {
  store.eventSource?.close()
})
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
h2 { color: #4cc9f0; }
.status-bar { display: flex; gap: 1rem; align-items: center; }
.status { padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; text-transform: uppercase; }
.status.running { background: #1b4332; color: #52b788; }
.status.completed { background: #1b3a4b; color: #4cc9f0; }
.status.error { background: #4a1c1c; color: #ff6b6b; }
.status.created { background: #2d2d44; color: #888; }
.stop-btn { padding: 0.3rem 1rem; background: #e63946; color: white; border: none; border-radius: 4px; cursor: pointer; }
.layout { display: grid; grid-template-columns: 1fr 350px; gap: 1rem; height: calc(100vh - 140px); }
.map-panel { background: #16213e; border-radius: 8px; overflow: hidden; padding: 1rem; }
.side-panel { display: flex; flex-direction: column; gap: 1rem; overflow-y: auto; }
</style>
