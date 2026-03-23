<template>
  <g class="air-missions">
    <g v-for="mission in displayMissions" :key="mission.mission_id">
      <text
        :x="hexToPixelX(mission.target_hex) + hexWidth / 2"
        :y="hexToPixelY(mission.target_hex) - 5"
        text-anchor="middle"
        font-size="14"
        :fill="mission.result === 'SUCCESS' ? '#22c55e' : '#ef4444'"
      >
        {{ missionIcon(mission.mission_type) }}
      </text>
    </g>
  </g>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const props = defineProps({
  hexToPixelX: Function,
  hexToPixelY: Function,
  hexWidth: Number,
})

const store = useSimulationStore()

const displayMissions = computed(() => {
  return (store.airMissions || []).filter(m => m.target_hex)
})

function missionIcon(type) {
  const icons = { CAS: '✈', INTERDICTION: '⊘', AIR_SUPERIORITY: '◈', RECON: '◎' }
  return icons[type] || '✈'
}
</script>
