<template>
  <g>
    <rect
      :x="center.x - size / 2"
      :y="center.y - size / 2"
      :width="size"
      :height="size * 0.7"
      :fill="unit.side === 'BLUE' ? '#1e40af' : '#991b1b'"
      :stroke="unit.side === 'BLUE' ? '#3b82f6' : '#ef4444'"
      stroke-width="1"
      rx="2"
    />
    <!-- Unit type symbol -->
    <text
      :x="center.x"
      :y="center.y - size * 0.05"
      text-anchor="middle"
      fill="white"
      :font-size="size * 0.35"
      font-weight="bold"
    >{{ typeSymbol }}</text>
    <!-- Strength bar -->
    <rect
      :x="center.x - size / 2"
      :y="center.y + size * 0.25"
      :width="size"
      :height="3"
      fill="#333"
    />
    <rect
      :x="center.x - size / 2"
      :y="center.y + size * 0.25"
      :width="size * unit.strength"
      :height="3"
      :fill="strengthColor"
    />
  </g>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ unit: Object, center: Object, size: Number })

const TYPE_SYMBOLS = {
  INFANTRY: 'INF',
  MECHANIZED: 'MEC',
  ARMOR: 'ARM',
  ARTILLERY: 'ART',
  AIR_DEFENSE: 'ADA',
  ENGINEER: 'ENG',
  HQ: 'HQ',
}

const typeSymbol = computed(() => TYPE_SYMBOLS[props.unit.unit_type] || '?')
const strengthColor = computed(() => {
  const s = props.unit.strength
  if (s > 0.6) return '#22c55e'
  if (s > 0.3) return '#eab308'
  return '#ef4444'
})
</script>
