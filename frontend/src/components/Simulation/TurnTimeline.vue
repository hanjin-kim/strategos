<template>
  <div class="timeline">
    <h3>Turn Timeline</h3>
    <input
      type="range"
      :min="0"
      :max="store.currentTurn || 1"
      v-model.number="viewTurn"
      @change="onTurnChange"
    />
    <div class="turn-label">Viewing Turn {{ viewTurn }} / {{ store.currentTurn }}</div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useSimulationStore } from '../../store/simulation'
const store = useSimulationStore()
const viewTurn = ref(0)

watch(() => store.currentTurn, (val) => { viewTurn.value = val })

function onTurnChange() {
  if (viewTurn.value > 0) {
    store.fetchState(viewTurn.value)
  } else {
    store.fetchState()
  }
}
</script>

<style scoped>
.timeline { background: #16213e; padding: 1rem; border-radius: 8px; border: 1px solid #0f3460; }
h3 { color: #4cc9f0; margin-bottom: 0.75rem; font-size: 0.95rem; }
input[type="range"] { width: 100%; accent-color: #4cc9f0; }
.turn-label { text-align: center; font-size: 0.8rem; color: #888; margin-top: 0.5rem; }
</style>
