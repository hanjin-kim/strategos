<template>
  <div class="simulation">
    <div class="sim-header">
      <div class="header-left">
        <span class="brand-sm">STRATEGOS</span>
        <span class="sep">|</span>
        <span class="observer-tag">Observer</span>
      </div>
      <div class="header-center">
        <SideToggle />
        <div class="turn-display">
          <span class="turn-label">TURN</span>
          <span class="turn-num">{{ store.currentTurn }}</span>
          <span class="turn-sep">/</span>
          <span class="turn-max">{{ store.maxTurns }}</span>
        </div>
      </div>
      <div class="header-right">
        <span class="status-pill" :class="store.status">{{ store.status || 'loading' }}</span>
        <button v-if="store.isRunning" @click="store.stop()" class="btn-stop">Stop</button>
      </div>
    </div>
    <div class="sim-layout">
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
.simulation { height: calc(100vh - 52px); display: flex; flex-direction: column; }

.sim-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.5rem 0; margin-bottom: 0.5rem;
}
.header-left, .header-right { display: flex; align-items: center; gap: 0.6rem; }
.header-center { display: flex; align-items: center; gap: 1rem; }
.brand-sm { font-weight: 800; font-size: 0.7rem; letter-spacing: 0.12em; color: var(--text-muted); }
.sep { color: var(--border-default); }
.observer-tag {
  font-size: 0.65rem; font-weight: 600; padding: 0.15rem 0.5rem;
  border-radius: 4px; background: var(--bg-elevated); color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.05em;
}

.turn-display { display: flex; align-items: baseline; gap: 0.2rem; }
.turn-label { font-size: 0.6rem; font-weight: 600; color: var(--text-muted); letter-spacing: 0.1em; margin-right: 0.3rem; }
.turn-num { font-family: 'JetBrains Mono', monospace; font-size: 1.3rem; font-weight: 700; color: var(--text-primary); }
.turn-sep { color: var(--text-muted); font-size: 0.9rem; }
.turn-max { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--text-muted); }

.status-pill {
  padding: 0.2rem 0.7rem; border-radius: 6px; font-size: 0.7rem;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
}
.status-pill.running { background: rgba(34, 197, 94, 0.12); color: var(--green); }
.status-pill.completed { background: var(--accent-glow); color: var(--accent); }
.status-pill.error { background: var(--red-bg); color: var(--red); }
.status-pill.created { background: var(--bg-elevated); color: var(--text-muted); }

.btn-stop {
  padding: 0.3rem 0.75rem; background: var(--red-bg); color: var(--red);
  border: 1px solid rgba(239, 68, 68, 0.2); border-radius: var(--radius-sm);
  cursor: pointer; font-size: 0.75rem; font-weight: 600; font-family: inherit;
  transition: all 0.15s;
}
.btn-stop:hover { background: rgba(239, 68, 68, 0.2); }

.sim-layout {
  display: grid; grid-template-columns: 1fr 340px; gap: 0.75rem;
  flex: 1; min-height: 0;
}
.map-panel {
  background: var(--bg-secondary); border-radius: var(--radius-md);
  overflow: hidden; border: 1px solid var(--border-subtle);
}
.side-panel {
  display: flex; flex-direction: column; gap: 0.6rem; overflow-y: auto;
}
</style>
