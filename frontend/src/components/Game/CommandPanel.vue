<template>
  <div class="command-panel">
    <div class="cp-header">
      <span class="cp-title">Commands</span>
      <span class="mode-tag">{{ store.commandMode }}</span>
    </div>

    <!-- Selected unit info -->
    <div v-if="store.selectedUnit" class="selected-unit">
      <div class="su-top">
        <span class="su-name">{{ store.selectedUnit.name }}</span>
        <span class="su-type">{{ store.selectedUnit.unit_type }}</span>
      </div>
      <div class="su-stats">
        <div class="su-stat">
          <span class="su-stat-label">STR</span>
          <div class="su-bar-bg">
            <div class="su-bar-fill" :class="strengthClass" :style="{ width: pct(store.selectedUnit.strength) + '%' }"></div>
          </div>
          <span class="su-stat-val">{{ pct(store.selectedUnit.strength) }}</span>
        </div>
        <div class="su-stat">
          <span class="su-stat-label">MP</span>
          <span class="su-stat-val mono">{{ store.selectedUnit.movement_points }}</span>
        </div>
      </div>
      <div class="intent-row">
        <button :class="{ active: store.commandIntent === 'MOVE' }" @click="store.setCommandIntent('MOVE')">Move</button>
        <button :class="{ active: store.commandIntent === 'ATTACK' }" @click="store.setCommandIntent('ATTACK')">Attack</button>
      </div>
    </div>
    <div v-else class="hint">Select a friendly unit on the map</div>

    <!-- Pending commands -->
    <div class="commands-list" v-if="store.pendingCommands.length">
      <div class="cl-header">
        <span class="cl-label">Pending</span>
        <span class="cl-count">{{ store.pendingCommands.length }}</span>
      </div>
      <div v-for="cmd in store.pendingCommands" :key="cmd.unit_id" class="cmd-row">
        <div class="cmd-info">
          <span class="cmd-unit">{{ unitName(cmd.unit_id) }}</span>
          <span class="cmd-action">
            {{ cmd.action_type || cmd.mission }}
            <template v-if="cmd.target_hex"> &rarr; {{ cmd.target_hex.q }},{{ cmd.target_hex.r }}</template>
            <template v-if="cmd.target_unit_id"> &rarr; {{ unitName(cmd.target_unit_id) }}</template>
          </span>
        </div>
        <button class="cmd-rm" @click="store.removeCommand(cmd.unit_id)">&times;</button>
      </div>
    </div>

    <!-- Strategic orders -->
    <div v-if="canIssueOrders && store.selectedUnit" class="strategic-section">
      <div class="cl-label">Mission Orders</div>
      <div class="mission-grid">
        <button v-for="m in missions" :key="m" class="mission-btn" @click="issueOrder(m)">{{ m }}</button>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="cp-actions">
      <button class="btn-clear" :disabled="!store.pendingCommands.length" @click="store.clearCommands()">Clear</button>
      <button class="btn-endturn" :disabled="store.isSteppingTurn" @click="store.submitAndStep()">
        {{ store.isSteppingTurn ? 'Processing...' : 'End Turn' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '../../store/simulation'

const store = useSimulationStore()
const missions = ['ATTACK', 'DEFEND', 'DELAY', 'RESERVE', 'WITHDRAW']

const canIssueOrders = computed(() =>
  store.commandMode === 'STRATEGIC' || store.commandMode === 'HYBRID'
)

const strengthClass = computed(() => {
  const s = store.selectedUnit?.strength ?? 0
  if (s > 0.6) return 'green'
  if (s > 0.3) return 'yellow'
  return 'red'
})

function pct(v) { return Math.round((v ?? 0) * 100) }

function unitName(unitId) {
  if (!store.gameState?.units) return unitId
  return store.gameState.units[unitId]?.name ?? unitId
}

function issueOrder(mission) {
  if (!store.selectedUnit) return
  store.addCommand({
    type: 'order',
    unit_id: store.selectedUnit.id,
    mission,
    target_hex: null,
    priority: 3,
  })
}
</script>

<style scoped>
.command-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.cp-header { display: flex; justify-content: space-between; align-items: center; }
.cp-title { font-size: 0.65rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.mode-tag {
  font-size: 0.55rem; font-weight: 700; padding: 0.12rem 0.45rem; border-radius: 4px;
  background: var(--accent-glow); color: var(--accent); text-transform: uppercase; letter-spacing: 0.04em;
}

.selected-unit {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 0.6rem 0.7rem;
}
.su-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; }
.su-name { font-weight: 700; font-size: 0.85rem; color: var(--text-primary); }
.su-type { font-size: 0.65rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }

.su-stats { display: flex; flex-direction: column; gap: 0.3rem; margin-bottom: 0.5rem; }
.su-stat { display: flex; align-items: center; gap: 0.4rem; }
.su-stat-label { font-size: 0.6rem; font-weight: 600; color: var(--text-muted); width: 24px; font-family: 'JetBrains Mono', monospace; }
.su-bar-bg { flex: 1; height: 4px; background: rgba(255, 255, 255, 0.06); border-radius: 2px; overflow: hidden; }
.su-bar-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.su-bar-fill.green { background: var(--green); }
.su-bar-fill.yellow { background: var(--yellow); }
.su-bar-fill.red { background: var(--red); }
.su-stat-val { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: var(--text-secondary); min-width: 20px; text-align: right; }
.mono { font-family: 'JetBrains Mono', monospace; }

.intent-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem; }
.intent-row button {
  padding: 0.35rem; border: 1px solid var(--border-default); border-radius: var(--radius-sm);
  background: transparent; color: var(--text-secondary); cursor: pointer; font-size: 0.75rem;
  font-weight: 500; font-family: inherit; transition: all 0.15s;
}
.intent-row button:hover { background: var(--bg-elevated); color: var(--text-primary); }
.intent-row button.active { background: var(--accent-glow); color: var(--accent); border-color: var(--border-active); }

.hint { color: var(--text-muted); font-size: 0.78rem; padding: 0.4rem 0; }

.cl-header { display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.3rem; }
.cl-label { font-size: 0.6rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.cl-count {
  font-size: 0.55rem; font-weight: 700; background: var(--accent-glow); color: var(--accent);
  padding: 0.05rem 0.35rem; border-radius: 8px; font-family: 'JetBrains Mono', monospace;
}

.commands-list { display: flex; flex-direction: column; gap: 0.25rem; }
.cmd-row {
  display: flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.5rem;
  background: var(--bg-secondary); border-radius: 4px; font-size: 0.78rem;
}
.cmd-info { flex: 1; display: flex; flex-direction: column; }
.cmd-unit { color: var(--text-primary); font-weight: 600; font-size: 0.75rem; }
.cmd-action { color: var(--text-muted); font-size: 0.7rem; }
.cmd-rm {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 1rem; padding: 0; line-height: 1; transition: color 0.15s;
}
.cmd-rm:hover { color: var(--red); }

.strategic-section { margin-top: 0.15rem; }
.mission-grid { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.25rem; }
.mission-btn {
  padding: 0.25rem 0.55rem; border: 1px solid var(--border-default); border-radius: 4px;
  background: transparent; color: var(--text-secondary); cursor: pointer;
  font-size: 0.7rem; font-weight: 500; font-family: inherit; transition: all 0.15s;
}
.mission-btn:hover { background: var(--bg-elevated); color: var(--text-primary); border-color: var(--border-active); }

.cp-actions { display: flex; gap: 0.4rem; margin-top: auto; padding-top: 0.25rem; }
.btn-clear {
  flex: 1; padding: 0.45rem; border: 1px solid var(--border-default); border-radius: var(--radius-sm);
  background: transparent; color: var(--text-secondary); cursor: pointer; font-size: 0.8rem;
  font-family: inherit; transition: all 0.15s;
}
.btn-clear:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-endturn {
  flex: 2; padding: 0.45rem; border: none; border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--accent), #3b82f6); color: #0a0e1a;
  cursor: pointer; font-size: 0.8rem; font-weight: 700; font-family: inherit; transition: all 0.15s;
}
.btn-endturn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-endturn:hover:not(:disabled) { box-shadow: 0 0 16px rgba(76, 201, 240, 0.25); }
</style>
