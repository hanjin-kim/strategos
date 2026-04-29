<template>
  <div class="game">
    <div class="game-header">
      <div class="header-left">
        <span class="brand-sm">STRATEGOS</span>
        <span class="header-sep">|</span>
        <span class="side-badge" :class="store.playerSide?.toLowerCase()">
          {{ store.playerSide }}
        </span>
      </div>
      <div class="header-center">
        <div class="turn-display">
          <span class="turn-label">TURN</span>
          <span class="turn-num">{{ store.currentTurn }}</span>
          <span class="turn-sep">/</span>
          <span class="turn-max">{{ store.maxTurns }}</span>
        </div>
      </div>
      <div class="header-right">
        <span class="status-pill" :class="statusClass">{{ statusLabel }}</span>
      </div>
    </div>

    <div class="game-layout">
      <div class="map-panel">
        <BattlefieldMap :interactive="true" />
      </div>
      <div class="side-panel">
        <CommandPanel />
        <ForceStatus />
        <NarrativePanel />
      </div>
    </div>

    <TurnResultModal
      v-if="store.showTurnResult && store.lastTurnResult"
      :result="store.lastTurnResult"
      @dismiss="store.dismissTurnResult()"
    />

    <Transition name="toast">
      <div v-if="store.error" class="error-toast">
        <span>{{ store.error }}</span>
        <button @click="store.error = null">&times;</button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useSimulationStore } from '../store/simulation'
import BattlefieldMap from '../components/Simulation/BattlefieldMap.vue'
import ForceStatus from '../components/Simulation/ForceStatus.vue'
import NarrativePanel from '../components/Simulation/NarrativePanel.vue'
import CommandPanel from '../components/Game/CommandPanel.vue'
import TurnResultModal from '../components/Game/TurnResultModal.vue'

const props = defineProps({ id: String })
const store = useSimulationStore()

const STATUS_MAP = {
  waiting_for_commands: 'Your Turn',
  running: 'Processing',
  completed: 'Game Over',
  error: 'Error',
  created: 'Ready',
}
const statusLabel = computed(() => STATUS_MAP[store.status] || store.status || 'Loading')
const statusClass = computed(() => (store.status || '').replace(/_/g, '-'))

onMounted(async () => {
  store.currentSimulationId = props.id
  await store.fetchStatus()
  await store.fetchState()
  if (store.isPlayerMode) await store.fetchAvailableActions()
})
</script>

<style scoped>
.game { height: calc(100vh - 52px); display: flex; flex-direction: column; }

.game-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0;
  margin-bottom: 0.5rem;
}
.header-left, .header-right { display: flex; align-items: center; gap: 0.6rem; }
.brand-sm {
  font-weight: 800;
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  color: var(--text-muted);
}
.header-sep { color: var(--border-default); font-size: 0.9rem; }
.side-badge {
  padding: 0.2rem 0.65rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.side-badge.blue { background: var(--blue-bg); color: var(--blue); }
.side-badge.red { background: var(--red-bg); color: var(--red); }

.header-center { display: flex; align-items: baseline; }
.turn-display { display: flex; align-items: baseline; gap: 0.2rem; }
.turn-label {
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  margin-right: 0.3rem;
}
.turn-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-primary);
}
.turn-sep { color: var(--text-muted); font-size: 0.9rem; }
.turn-max {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.status-pill {
  padding: 0.2rem 0.7rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.status-pill.waiting-for-commands { background: rgba(34, 197, 94, 0.12); color: var(--green); }
.status-pill.running { background: rgba(234, 179, 8, 0.12); color: var(--yellow); }
.status-pill.completed { background: var(--accent-glow); color: var(--accent); }
.status-pill.error { background: var(--red-bg); color: var(--red); }
.status-pill.created { background: var(--bg-elevated); color: var(--text-muted); }

.game-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 0.75rem;
  flex: 1;
  min-height: 0;
}
.map-panel {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  overflow-y: auto;
}

.error-toast {
  position: fixed;
  bottom: 1.25rem;
  right: 1.25rem;
  background: rgba(239, 68, 68, 0.15);
  color: var(--red);
  padding: 0.6rem 1rem;
  border-radius: var(--radius-md);
  display: flex;
  gap: 1rem;
  align-items: center;
  border: 1px solid rgba(239, 68, 68, 0.2);
  backdrop-filter: blur(8px);
  z-index: 100;
  font-size: 0.85rem;
}
.error-toast button {
  background: none;
  border: none;
  color: var(--red);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0;
}

.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }
</style>
