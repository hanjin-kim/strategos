<template>
  <g :class="['unit-marker', { clickable: isPlayerUnit }]">
    <!-- Selection ring -->
    <circle
      v-if="selected"
      :cx="center.x" :cy="center.y" :r="size * 0.55"
      fill="none" stroke="#4cc9f0" stroke-width="1.5"
      stroke-dasharray="3 2"
      class="selection-ring"
    />
    <!-- Pending command dot -->
    <circle
      v-if="hasPending"
      :cx="center.x + size * 0.4" :cy="center.y - size * 0.35" :r="size * 0.1"
      fill="#4cc9f0"
    />
    <!-- Unit body -->
    <rect
      :x="center.x - size / 2"
      :y="center.y - size / 2"
      :width="size"
      :height="size * 0.7"
      :fill="unit.side === 'BLUE' ? '#1e3a6e' : '#6e1e1e'"
      :stroke="selected ? '#4cc9f0' : (unit.side === 'BLUE' ? '#3b7cf5' : '#e84545')"
      :stroke-width="selected ? 1.5 : 0.8"
      rx="3"
      :class="{ 'player-unit': isPlayerUnit }"
    />
    <!-- Unit type label -->
    <text
      :x="center.x"
      :y="center.y - size * 0.05"
      text-anchor="middle"
      fill="white"
      :font-size="size * 0.32"
      font-weight="700"
      font-family="'JetBrains Mono', monospace"
    >{{ typeSymbol }}</text>
    <!-- Strength bar bg -->
    <rect
      :x="center.x - size / 2"
      :y="center.y + size * 0.25"
      :width="size"
      :height="2.5"
      fill="rgba(255,255,255,0.08)"
      rx="1"
    />
    <!-- Strength bar fill -->
    <rect
      :x="center.x - size / 2"
      :y="center.y + size * 0.25"
      :width="size * unit.strength"
      :height="2.5"
      :fill="strengthColor"
      rx="1"
    />
  </g>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  unit: Object,
  center: Object,
  size: Number,
  selected: { type: Boolean, default: false },
  hasPending: { type: Boolean, default: false },
  isPlayerUnit: { type: Boolean, default: false },
})

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

<style scoped>
.unit-marker { pointer-events: all; }
.unit-marker.clickable { cursor: pointer; }
.unit-marker.clickable:hover rect.player-unit { filter: brightness(1.25); }
.selection-ring {
  animation: pulse 1.8s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
