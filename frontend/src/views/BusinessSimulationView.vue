<template>
  <div class="biz-sim-view">
    <header class="sim-header">
      <h1>{{ scenarioName || 'Business Simulation' }}</h1>
      <div class="header-controls">
        <span class="turn-badge">Turn {{ turn }}</span>
        <span class="phase-badge">{{ phase }}</span>
      </div>
    </header>

    <div class="sim-layout">
      <!-- Market Graph -->
      <div class="graph-panel">
        <MarketGraph
          :markets="markets"
          :units="units"
          :width="700"
          :height="450"
        />
      </div>

      <!-- Side Panel -->
      <div class="side-panel">
        <!-- Unit List grouped by side -->
        <div v-for="side in sides" :key="side" class="side-section">
          <h3 :style="{ color: sideColor(side) }">{{ side }}</h3>
          <BusinessUnitCard
            v-for="unit in unitsBySide(side)"
            :key="unit.id"
            :unit="unit"
          />
        </div>

        <!-- Narrative -->
        <div v-if="narrative" class="narrative-section">
          <h3>Market Report</h3>
          <p>{{ narrative }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getSimulationState, getSimulationStatus } from '../api/client'
import MarketGraph from '../components/Business/MarketGraph.vue'
import BusinessUnitCard from '../components/Business/BusinessUnitCard.vue'

const route = useRoute()
const simId = computed(() => route.params.id)

const state = ref({})
const turn = ref(0)
const phase = ref('')
const narrative = ref('')
const scenarioName = ref('')

const units = computed(() => state.value.units || {})
const markets = computed(() => {
  if (!state.value.market_map) return []
  return Object.values(state.value.market_map)
})

const sides = computed(() => {
  const s = new Set()
  Object.values(units.value).forEach(u => {
    if (u.side) s.add(typeof u.side === 'string' ? u.side : (u.side.value || u.side))
  })
  return [...s].sort()
})

function unitsBySide(side) {
  return Object.values(units.value).filter(u => {
    const uSide = typeof u.side === 'string' ? u.side : (u.side?.value || u.side)
    return uSide === side && u.status !== 'BANKRUPT'
  })
}

const sideColors = {
  'Netflix': '#e50914', 'DisneyPlus': '#113ccf',
  'LGES': '#1e40af', 'CATL': '#991b1b',
  'AWS': '#ff9900', 'Azure': '#0078d4',
  'BLUE': '#1e40af', 'RED': '#991b1b',
}

function sideColor(side) {
  return sideColors[side] || '#475569'
}

let pollInterval = null

async function fetchState() {
  try {
    const data = await getSimulationState(simId.value)
    state.value = data
    turn.value = data.turn || 0
    phase.value = data.phase || ''
    if (data.scenario_name) scenarioName.value = data.scenario_name
  } catch (e) {
    // silently ignore polling errors
  }
}

async function fetchStatus() {
  try {
    const data = await getSimulationStatus(simId.value)
    if (data.status === 'completed' || data.status === 'stopped') {
      clearInterval(pollInterval)
    }
  } catch (e) {
    // silently ignore polling errors
  }
}

onMounted(() => {
  fetchState()
  fetchStatus()
  pollInterval = setInterval(() => {
    fetchState()
    fetchStatus()
  }, 3000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.biz-sim-view {
  padding: 16px;
  color: #e2e8f0;
  min-height: 100vh;
  background: #0a0f1a;
}
.sim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
h1 { font-size: 20px; color: #4cc9f0; }
.header-controls { display: flex; gap: 8px; }
.turn-badge, .phase-badge {
  padding: 4px 12px;
  background: #1e293b;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
}
.sim-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
}
.graph-panel {
  border: 1px solid #1e293b;
  border-radius: 8px;
  overflow: hidden;
}
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
}
.side-section h3 {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
}
.narrative-section {
  background: #1e293b;
  padding: 12px;
  border-radius: 8px;
}
.narrative-section h3 { font-size: 13px; color: #94a3b8; margin-bottom: 4px; }
.narrative-section p { font-size: 12px; line-height: 1.5; color: #cbd5e1; }
</style>
