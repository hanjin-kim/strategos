<template>
  <g class="fog-overlay" v-if="viewSide !== 'OMNISCIENT'">
    <rect
      v-for="hex in hiddenHexes"
      :key="`fog-${hex.q}-${hex.r}`"
      :x="hexToPixelX(hex)"
      :y="hexToPixelY(hex)"
      :width="hexWidth"
      :height="hexHeight"
      fill="rgba(0,0,0,0.6)"
      class="fog-hidden"
    />
    <rect
      v-for="hex in partialHexes"
      :key="`partial-${hex.q}-${hex.r}`"
      :x="hexToPixelX(hex)"
      :y="hexToPixelY(hex)"
      :width="hexWidth"
      :height="hexHeight"
      fill="rgba(0,0,0,0.3)"
      class="fog-partial"
    />
  </g>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const props = defineProps({
  hexToPixelX: Function,
  hexToPixelY: Function,
  hexWidth: Number,
  hexHeight: Number,
  allHexes: Array,
})

const store = useSimulationStore()
const viewSide = computed(() => store.viewSide)

const hiddenHexes = computed(() => {
  if (!store.intelReports || viewSide.value === 'OMNISCIENT') return []
  // Full implementation needs visible_hexes from backend
  return []
})

const partialHexes = computed(() => {
  // Will be populated when backend provides visible_hexes
  return []
})
</script>
