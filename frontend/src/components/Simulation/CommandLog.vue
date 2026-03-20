<template>
  <div class="command-log">
    <h3>Command Log</h3>
    <div class="log-entries">
      <div v-if="!store.units.length" class="empty">No data yet</div>
      <div v-for="unit in activeUnits" :key="unit.id" class="entry">
        <span class="unit-name" :class="unit.side.toLowerCase()">{{ unit.name }}</span>
        <span class="unit-status">{{ unit.status }} | STR: {{ Math.round(unit.strength * 100) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'
const store = useSimulationStore()

const activeUnits = computed(() =>
  store.units.filter(u => u.status !== 'DESTROYED').sort((a, b) => a.side.localeCompare(b.side))
)
</script>

<style scoped>
.command-log { background: #16213e; padding: 1rem; border-radius: 8px; border: 1px solid #0f3460; flex: 1; overflow-y: auto; }
h3 { color: #4cc9f0; margin-bottom: 0.75rem; font-size: 0.95rem; }
.log-entries { display: flex; flex-direction: column; gap: 0.3rem; }
.entry { display: flex; justify-content: space-between; font-size: 0.8rem; padding: 0.3rem 0; border-bottom: 1px solid #0f3460; }
.unit-name { font-weight: 500; }
.unit-name.blue { color: #3b82f6; }
.unit-name.red { color: #ef4444; }
.unit-status { color: #888; }
.empty { color: #555; text-align: center; padding: 1rem; }
</style>
