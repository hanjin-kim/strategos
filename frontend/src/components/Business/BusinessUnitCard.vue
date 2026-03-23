<template>
  <div class="bu-card" :style="{ borderColor: sideColor }">
    <div class="bu-header">
      <span class="bu-name">{{ unit.name }}</span>
      <span class="bu-side" :style="{ color: sideColor }">{{ unit.side }}</span>
    </div>
    <div class="bu-stats">
      <div class="stat-row">
        <span class="stat-label">Market Share</span>
        <div class="stat-bar-bg">
          <div class="stat-bar" :style="{ width: (unit.market_share * 100) + '%', background: '#22c55e' }" />
        </div>
        <span class="stat-value">{{ (unit.market_share * 100).toFixed(1) }}%</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Competitive Power</span>
        <span class="stat-value">{{ unit.competitive_power }}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Brand Loyalty</span>
        <span class="stat-value">{{ unit.brand_loyalty }}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Marketing Budget</span>
        <div class="stat-bar-bg">
          <div class="stat-bar" :style="{ width: (unit.marketing_budget * 100) + '%', background: '#3b82f6' }" />
        </div>
        <span class="stat-value">{{ (unit.marketing_budget * 100).toFixed(0) }}%</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">R&amp;D</span>
        <div class="stat-bar-bg">
          <div class="stat-bar" :style="{ width: (unit.rd_capability * 100) + '%', background: '#a78bfa' }" />
        </div>
        <span class="stat-value">{{ (unit.rd_capability * 100).toFixed(0) }}%</span>
      </div>
    </div>
    <div class="bu-position">
      {{ unit.position?.region }}:{{ unit.position?.segment }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  unit: { type: Object, required: true },
})

const sideColors = {
  'Netflix': '#e50914', 'DisneyPlus': '#113ccf',
  'LGES': '#1e40af', 'CATL': '#991b1b',
  'AWS': '#ff9900', 'Azure': '#0078d4',
  'BLUE': '#1e40af', 'RED': '#991b1b',
}

const sideColor = computed(() => sideColors[props.unit.side] || '#475569')
</script>

<style scoped>
.bu-card {
  background: #1e293b;
  border: 2px solid;
  border-radius: 8px;
  padding: 12px;
  min-width: 220px;
}
.bu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.bu-name { font-weight: 700; color: #e2e8f0; font-size: 13px; }
.bu-side { font-size: 11px; font-weight: 600; }
.bu-stats { display: flex; flex-direction: column; gap: 4px; }
.stat-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #94a3b8; }
.stat-label { width: 100px; flex-shrink: 0; }
.stat-value { width: 40px; text-align: right; color: #cbd5e1; font-weight: 600; }
.stat-bar-bg { flex: 1; height: 4px; background: #0f172a; border-radius: 2px; overflow: hidden; }
.stat-bar { height: 100%; border-radius: 2px; transition: width 0.3s; }
.bu-position { margin-top: 6px; font-size: 10px; color: #64748b; }
</style>
