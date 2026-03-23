<template>
  <div class="force-org-tree">
    <div v-for="side in ['BLUE', 'RED']" :key="side" class="side-section">
      <h3 :class="side.toLowerCase()">{{ side }} Forces</h3>
      <div v-for="cmd in getCommandTree(side)" :key="cmd.id" class="commander-node">
        <div class="cmd-header" :class="{ theater: cmd.rank === 'Theater', division: cmd.rank === 'Division' }">
          {{ cmd.rank }}: {{ cmd.name }}
        </div>
        <div v-for="unit in cmd.units" :key="unit.id" class="unit-leaf" @click="$emit('select-unit', unit.id)">
          <span class="unit-name">{{ unit.name }}</span>
          <span class="unit-strength" :style="{ width: (unit.strength * 40) + 'px' }">&nbsp;</span>
          <span v-if="unit.supply_level" class="supply-badge" :class="unit.supply_level.toLowerCase()">
            {{ unit.supply_level[0] }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

defineEmits(['select-unit'])
const store = useSimulationStore()

function getCommandTree(side) {
  const commanders = Object.values(store.state?.commanders || {}).filter(c => c.side === side)
  const units = Object.values(store.state?.units || {}).filter(u => u.side === side)

  return commanders.map(cmd => ({
    ...cmd,
    units: units.slice(0, 5),
  }))
}
</script>

<style scoped>
.force-org-tree { font-size: 12px; color: #e2e8f0; }
.side-section { margin-bottom: 16px; }
h3.blue { color: #3b82f6; }
h3.red { color: #ef4444; }
h3 { font-size: 13px; margin-bottom: 8px; }
.commander-node { margin-left: 8px; margin-bottom: 8px; }
.cmd-header { font-weight: 600; padding: 2px 0; }
.cmd-header.theater { color: #fbbf24; }
.cmd-header.division { color: #a78bfa; }
.unit-leaf { display: flex; align-items: center; gap: 6px; padding: 2px 8px; cursor: pointer; }
.unit-leaf:hover { background: #1e293b; border-radius: 4px; }
.unit-name { flex: 1; }
.unit-strength { height: 4px; background: #22c55e; border-radius: 2px; }
.supply-badge { font-size: 10px; padding: 1px 4px; border-radius: 3px; font-weight: 700; }
.supply-badge.full { background: #166534; color: #4ade80; }
.supply-badge.reduced { background: #713f12; color: #fbbf24; }
.supply-badge.cut_off { background: #7f1d1d; color: #fca5a5; }
</style>
