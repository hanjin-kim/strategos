<template>
  <div class="narrative-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="isCollapsed = !isCollapsed">
      <span>Battle Report</span>
      <span>{{ isCollapsed ? '▶' : '▼' }}</span>
    </div>
    <div v-if="!isCollapsed" class="panel-content">
      <div v-if="narrative.summary" class="summary">
        {{ narrative.summary }}
      </div>
      <div v-if="narrative.combat_reports?.length" class="combat-reports">
        <h4>Engagements</h4>
        <div v-for="(report, i) in narrative.combat_reports" :key="i" class="report-item">
          {{ report }}
        </div>
      </div>
      <div v-if="narrative.strategic_analysis" class="analysis">
        <h4>Analysis</h4>
        {{ narrative.strategic_analysis }}
      </div>
      <div v-if="narrative.key_events?.length" class="key-events">
        <h4>Key Events</h4>
        <ul>
          <li v-for="(evt, i) in narrative.key_events" :key="i">{{ evt }}</li>
        </ul>
      </div>
      <div v-if="!narrative.summary" class="no-data">
        No narrative available for this turn.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const store = useSimulationStore()
const isCollapsed = ref(false)

const narrative = computed(() => store.currentNarrative || {})
</script>

<style scoped>
.narrative-panel {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  max-height: 400px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #1e293b;
  cursor: pointer;
  font-weight: 600;
  color: #e2e8f0;
  font-size: 13px;
}
.panel-content {
  padding: 12px;
  overflow-y: auto;
  max-height: 350px;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.5;
}
.summary { margin-bottom: 12px; }
h4 { color: #94a3b8; font-size: 11px; text-transform: uppercase; margin: 8px 0 4px; }
.report-item { padding: 4px 0; border-bottom: 1px solid #1e293b; }
.key-events ul { padding-left: 16px; margin: 4px 0; }
.no-data { color: #475569; font-style: italic; }
</style>
