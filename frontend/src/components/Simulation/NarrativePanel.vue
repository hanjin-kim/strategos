<template>
  <div class="narrative-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-header" @click="isCollapsed = !isCollapsed">
      <span>Intel & Reports</span>
      <span class="chevron">{{ isCollapsed ? '&#x25B8;' : '&#x25BE;' }}</span>
    </div>
    <div v-if="!isCollapsed" class="panel-content">
      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >{{ tab.label }}</button>
      </div>

      <div v-if="activeTab === 'report'" class="tab-content">
        <div v-if="narrative.summary" class="summary">{{ narrative.summary }}</div>
        <div v-if="narrative.combat_reports?.length" class="combat-reports">
          <h4>Engagements</h4>
          <div v-for="(report, i) in narrative.combat_reports" :key="i" class="report-item">{{ report }}</div>
        </div>
        <div v-if="narrative.strategic_analysis" class="analysis">
          <h4>Analysis</h4>
          {{ narrative.strategic_analysis }}
        </div>
        <div v-if="narrative.key_events?.length" class="key-events">
          <h4>Key Events</h4>
          <ul><li v-for="(evt, i) in narrative.key_events" :key="i">{{ evt }}</li></ul>
        </div>
        <div v-if="!narrative.summary" class="no-data">No battle report available.</div>
      </div>

      <div v-if="activeTab === 'comms'" class="tab-content">
        <div v-if="dialogue.length" class="comms-list">
          <div v-for="(msg, i) in dialogue" :key="i" class="comm-item" :class="msg.tone">
            <div class="comm-top">
              <span class="comm-speaker">{{ msg.speaker }}</span>
              <span class="comm-tone">{{ msg.tone }}</span>
            </div>
            <div class="comm-text">"{{ msg.text }}"</div>
          </div>
        </div>
        <div v-if="eventReactions.length" class="reactions">
          <h4>Intercepts</h4>
          <div v-for="(r, i) in eventReactions" :key="i" class="reaction-item">{{ r }}</div>
        </div>
        <div v-if="!dialogue.length && !eventReactions.length" class="no-data">No intercepted communications.</div>
      </div>

      <div v-if="activeTab === 'briefing'" class="tab-content">
        <div v-if="staffBriefing" class="briefing-box">
          <span class="briefing-star">&#x2605;</span>
          <p>{{ staffBriefing }}</p>
        </div>
        <div v-else class="no-data">No staff briefing available.</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const store = useSimulationStore()
const isCollapsed = ref(false)
const activeTab = ref('report')

const tabs = [
  { id: 'report', label: 'Report' },
  { id: 'comms', label: 'Enemy Comms' },
  { id: 'briefing', label: 'Briefing' },
]

const narrative = computed(() => store.currentNarrative || {})
const dialogue = computed(() => narrative.value.enemy_dialogue || [])
const staffBriefing = computed(() => narrative.value.staff_briefing || '')
const eventReactions = computed(() => narrative.value.event_reactions || [])
</script>

<style scoped>
.narrative-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
  max-height: 400px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  font-weight: 600;
  color: var(--text-muted);
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.chevron { font-size: 0.75rem; }
.panel-content { display: flex; flex-direction: column; max-height: 350px; }

.tab-bar { display: flex; border-bottom: 1px solid var(--border-subtle); }
.tab-bar button {
  flex: 1; padding: 0.4rem 0.5rem; background: transparent; border: none;
  border-bottom: 2px solid transparent; color: var(--text-muted);
  font-size: 0.65rem; font-weight: 600; cursor: pointer; font-family: inherit;
  text-transform: uppercase; letter-spacing: 0.03em; transition: all 0.15s;
}
.tab-bar button:hover { color: var(--text-secondary); }
.tab-bar button.active { color: var(--accent); border-bottom-color: var(--accent); }

.tab-content {
  padding: 0.75rem;
  overflow-y: auto;
  flex: 1;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.summary { margin-bottom: 0.75rem; }
h4 { color: var(--text-muted); font-size: 0.6rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin: 0.6rem 0 0.25rem; }
.report-item { padding: 0.25rem 0; border-bottom: 1px solid var(--border-subtle); font-size: 0.78rem; }
.key-events ul { padding-left: 1rem; margin: 0.2rem 0; }
.key-events li { font-size: 0.78rem; }

.comms-list { display: flex; flex-direction: column; gap: 0.5rem; }
.comm-item {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 0.5rem 0.65rem;
  border-left: 3px solid var(--text-muted);
}
.comm-item.defiant { border-left-color: var(--red); }
.comm-item.frustrated { border-left-color: var(--yellow); }
.comm-item.confident { border-left-color: var(--green); }
.comm-item.desperate { border-left-color: #a855f7; }
.comm-item.cautious { border-left-color: var(--text-muted); }
.comm-top { display: flex; justify-content: space-between; margin-bottom: 0.2rem; }
.comm-speaker { color: var(--text-primary); font-weight: 600; font-size: 0.72rem; }
.comm-tone { font-size: 0.58rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em; }
.comm-text { color: var(--text-secondary); font-style: italic; font-size: 0.75rem; }

.reactions { margin-top: 0.5rem; }
.reaction-item { color: var(--text-muted); font-size: 0.75rem; padding: 0.15rem 0; }

.briefing-box {
  display: flex; gap: 0.5rem; align-items: flex-start;
  background: var(--bg-secondary); border-radius: var(--radius-sm); padding: 0.75rem;
}
.briefing-star { color: var(--yellow); font-size: 0.9rem; flex-shrink: 0; }
.briefing-box p { color: var(--text-secondary); margin: 0; line-height: 1.6; font-size: 0.8rem; }

.no-data { color: var(--text-muted); font-style: italic; padding: 0.5rem 0; font-size: 0.78rem; }
</style>
