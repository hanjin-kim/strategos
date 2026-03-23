<template>
  <div class="side-toggle">
    <button
      v-for="side in sides"
      :key="side.value"
      :class="['toggle-btn', { active: currentSide === side.value }]"
      @click="setSide(side.value)"
    >
      {{ side.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const store = useSimulationStore()
const currentSide = computed(() => store.viewSide)

const sides = [
  { value: 'BLUE', label: 'BLUE' },
  { value: 'RED', label: 'RED' },
  { value: 'OMNISCIENT', label: 'ALL' },
]

function setSide(side) {
  store.setViewSide(side)
}
</script>

<style scoped>
.side-toggle {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: #1e293b;
  border-radius: 6px;
}
.toggle-btn {
  padding: 4px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  background: transparent;
  color: #94a3b8;
}
.toggle-btn.active {
  background: #334155;
  color: #f8fafc;
}
.toggle-btn:hover:not(.active) {
  color: #e2e8f0;
}
</style>
