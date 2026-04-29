<template>
  <div class="force-status">
    <div class="fs-header">Force Status</div>
    <div class="sides">
      <div v-for="side in ['BLUE', 'RED']" :key="side" class="side-block" :class="side.toLowerCase()">
        <div class="side-top">
          <span class="side-label">{{ side }}</span>
          <span class="unit-count">{{ sideUnits(side).length }} units</span>
        </div>
        <div class="strength-row">
          <div class="strength-bar-bg">
            <div class="strength-bar-fill" :class="side.toLowerCase()" :style="{ width: avgStrength(side) + '%' }"></div>
          </div>
          <span class="strength-val">{{ avgStrength(side) }}%</span>
        </div>
        <div class="unit-types">
          <span v-for="(count, type) in typeBreakdown(side)" :key="type" class="type-tag">
            {{ TYPE_LABELS[type] || type }} {{ count }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useSimulationStore } from '../../store/simulation'
const store = useSimulationStore()

const TYPE_LABELS = {
  INFANTRY: 'INF',
  MECHANIZED: 'MEC',
  ARMOR: 'ARM',
  ARTILLERY: 'ART',
  AIR_DEFENSE: 'ADA',
  ENGINEER: 'ENG',
  HQ: 'HQ',
}

function sideUnits(side) {
  return store.units.filter(u => u.side === side && u.status !== 'DESTROYED')
}

function avgStrength(side) {
  const units = sideUnits(side)
  if (!units.length) return 0
  return Math.round(units.reduce((sum, u) => sum + u.strength, 0) / units.length * 100)
}

function typeBreakdown(side) {
  const counts = {}
  for (const u of sideUnits(side)) {
    const t = u.unit_type || 'UNKNOWN'
    counts[t] = (counts[t] || 0) + 1
  }
  return counts
}
</script>

<style scoped>
.force-status {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.75rem;
}
.fs-header {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.6rem;
}

.sides { display: flex; flex-direction: column; gap: 0.6rem; }
.side-block {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 0.6rem 0.75rem;
}

.side-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}
.side-label { font-size: 0.75rem; font-weight: 700; }
.side-block.blue .side-label { color: var(--blue); }
.side-block.red .side-label { color: var(--red); }
.unit-count { font-size: 0.7rem; color: var(--text-muted); }

.strength-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.strength-bar-bg {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}
.strength-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}
.strength-bar-fill.blue { background: var(--blue); }
.strength-bar-fill.red { background: var(--red); }
.strength-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--text-secondary);
  min-width: 32px;
  text-align: right;
}

.unit-types { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.type-tag {
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.04);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
}
</style>
