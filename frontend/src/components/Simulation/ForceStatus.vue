<template>
  <div class="force-status">
    <h3>Force Status</h3>
    <div v-for="side in ['BLUE', 'RED']" :key="side" class="side">
      <h4 :class="side.toLowerCase()">{{ side }}</h4>
      <div class="stats">
        <span>Units: {{ sideUnits(side).length }}</span>
        <span>Avg Strength: {{ avgStrength(side) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useSimulationStore } from '../../store/simulation'
const store = useSimulationStore()

function sideUnits(side) {
  return store.units.filter(u => u.side === side && u.status !== 'DESTROYED')
}
function avgStrength(side) {
  const units = sideUnits(side)
  if (!units.length) return 0
  return Math.round(units.reduce((sum, u) => sum + u.strength, 0) / units.length * 100)
}
</script>

<style scoped>
.force-status { background: #16213e; padding: 1rem; border-radius: 8px; border: 1px solid #0f3460; }
h3 { color: #4cc9f0; margin-bottom: 0.75rem; font-size: 0.95rem; }
.side { margin-bottom: 0.75rem; }
h4 { font-size: 0.85rem; margin-bottom: 0.25rem; }
h4.blue { color: #3b82f6; }
h4.red { color: #ef4444; }
.stats { display: flex; gap: 1rem; font-size: 0.8rem; color: #888; }
</style>
