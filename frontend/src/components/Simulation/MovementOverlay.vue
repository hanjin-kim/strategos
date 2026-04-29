<template>
  <g class="movement-overlay" v-if="store.selectedUnit && store.isPlayerMode">
    <polygon
      v-for="hex in reachableHexList"
      :key="`reach-${hex.q}-${hex.r}`"
      :points="hexPoints(hex.q, hex.r)"
      class="reachable-hex"
      :class="{ 'attack-hex': isEnemyAt(hex) }"
    />
  </g>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const props = defineProps({
  hexPoints: Function,
})

const store = useSimulationStore()

const reachableHexList = computed(() => {
  const hexes = []
  for (const key of store.reachableHexes) {
    const [q, r] = key.split(',').map(Number)
    hexes.push({ q, r })
  }
  return hexes
})

function isEnemyAt(hex) {
  const key = `${hex.q},${hex.r}`
  const units = store.unitsByHex[key]
  return units?.some(u => u.side !== store.playerSide && u.status !== 'DESTROYED')
}
</script>

<style scoped>
.reachable-hex {
  fill: rgba(76, 201, 240, 0.15);
  stroke: rgba(76, 201, 240, 0.5);
  stroke-width: 1.5;
  stroke-dasharray: 4 2;
  pointer-events: none;
}
.attack-hex {
  fill: rgba(239, 68, 68, 0.15);
  stroke: rgba(239, 68, 68, 0.5);
}
</style>
