<template>
  <g class="command-arrows" v-if="store.isPlayerMode">
    <g v-for="cmd in arrowCommands" :key="cmd.unit_id">
      <line
        :x1="cmd.from.x" :y1="cmd.from.y"
        :x2="cmd.to.x" :y2="cmd.to.y"
        :stroke="cmd.action_type === 'ATTACK' ? '#ef4444' : '#4cc9f0'"
        stroke-width="2"
        stroke-linecap="round"
        :marker-end="cmd.action_type === 'ATTACK' ? 'url(#arrow-red)' : 'url(#arrow-blue)'"
      />
    </g>
    <defs>
      <marker id="arrow-blue" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
        <path d="M0,0 L8,3 L0,6 Z" fill="#4cc9f0" />
      </marker>
      <marker id="arrow-red" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
        <path d="M0,0 L8,3 L0,6 Z" fill="#ef4444" />
      </marker>
    </defs>
  </g>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const props = defineProps({
  hexCenter: Function,
})

const store = useSimulationStore()

const arrowCommands = computed(() => {
  const arrows = []
  for (const cmd of store.pendingCommands) {
    const unit = store.gameState?.units?.[cmd.unit_id]
    if (!unit) continue

    let targetHex = cmd.target_hex
    if (!targetHex && cmd.target_unit_id) {
      const target = store.gameState?.units?.[cmd.target_unit_id]
      if (target) targetHex = target.position
    }
    if (!targetHex) continue

    arrows.push({
      unit_id: cmd.unit_id,
      action_type: cmd.action_type || cmd.mission,
      from: props.hexCenter(unit.position.q, unit.position.r),
      to: props.hexCenter(targetHex.q, targetHex.r),
    })
  }
  return arrows
})
</script>
