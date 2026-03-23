<template>
  <g class="supply-overlay" v-if="showSupply">
    <circle
      v-for="status in cutOffUnits"
      :key="`supply-${status.unit_id}`"
      :cx="getUnitX(status.unit_id) + 12"
      :cy="getUnitY(status.unit_id) - 12"
      r="6"
      fill="#ef4444"
      stroke="#fff"
      stroke-width="1"
    />
    <circle
      v-for="status in reducedUnits"
      :key="`supply-r-${status.unit_id}`"
      :cx="getUnitX(status.unit_id) + 12"
      :cy="getUnitY(status.unit_id) - 12"
      r="6"
      fill="#f59e0b"
      stroke="#fff"
      stroke-width="1"
    />
  </g>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const props = defineProps({
  getUnitX: Function,
  getUnitY: Function,
  showSupply: { type: Boolean, default: true },
})

const store = useSimulationStore()

const cutOffUnits = computed(() => {
  const status = store.supplyStatus || {}
  return Object.values(status).filter(s => s.level === 'CUT_OFF')
})

const reducedUnits = computed(() => {
  const status = store.supplyStatus || {}
  return Object.values(status).filter(s => s.level === 'REDUCED')
})
</script>
