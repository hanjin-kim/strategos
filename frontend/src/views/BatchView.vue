<template>
  <div class="batch-view">
    <header class="batch-header">
      <h1>Batch Simulation Analysis</h1>
      <button @click="showConfig = !showConfig" class="btn-config">
        {{ showConfig ? 'Hide Config' : 'New Batch' }}
      </button>
    </header>

    <!-- Config Panel -->
    <div v-if="showConfig" class="config-panel">
      <h2>Configure Batch Run</h2>
      <div class="config-form">
        <label>Scenario: <select v-model="selectedScenario">
          <option v-for="s in scenarios" :key="s.name" :value="s.name">{{ s.display_name || s.name }}</option>
        </select></label>
        <label>Number of Runs: <input type="number" v-model.number="numRuns" min="1" max="100" /></label>
        <label>Max Turns: <input type="number" v-model.number="maxTurns" min="1" max="72" /></label>
        <button @click="startBatch" class="btn-start" :disabled="loading">
          {{ loading ? 'Running...' : 'Start Batch' }}
        </button>
      </div>
    </div>

    <!-- Active Batch Status -->
    <div v-if="activeBatch" class="active-batch">
      <h2>Running: {{ activeBatch.batch_id }}</h2>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <p>{{ activeBatch.completed_runs }} / {{ activeBatch.total_runs }} runs completed</p>
    </div>

    <!-- Report -->
    <div v-if="report" class="report-section">
      <h2>Analysis Report</h2>
      <div class="report-card">
        <h3>Executive Summary</h3>
        <p>{{ report.executive_summary }}</p>
      </div>
      <div class="report-card">
        <h3>Strategy Comparison</h3>
        <p>{{ report.strategy_comparison }}</p>
      </div>
      <div class="report-card">
        <h3>Risk Assessment</h3>
        <p>{{ report.risk_assessment }}</p>
      </div>
      <div class="report-card">
        <h3>Recommendations</h3>
        <p>{{ report.recommendations }}</p>
      </div>
      <div v-if="report.key_decision_points?.length" class="report-card">
        <h3>Key Decision Points</h3>
        <ul>
          <li v-for="(point, i) in report.key_decision_points" :key="i">{{ point }}</li>
        </ul>
      </div>
    </div>

    <!-- Run Results Table -->
    <div v-if="runs.length" class="runs-table">
      <h2>Individual Runs</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Parameter Set</th>
            <th>Seed</th>
            <th>Winner</th>
            <th>Turns</th>
            <th>BLUE Remaining</th>
            <th>RED Remaining</th>
            <th>Time (ms)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in runs" :key="run.run_index" :class="winnerClass(run.winner)">
            <td>{{ run.run_index }}</td>
            <td>{{ run.parameter_set_name }}</td>
            <td>{{ run.rng_seed }}</td>
            <td>{{ run.winner }}</td>
            <td>{{ run.total_turns }}</td>
            <td>{{ run.blue_units_remaining }}</td>
            <td>{{ run.red_units_remaining }}</td>
            <td>{{ run.execution_time_ms }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Batch History -->
    <div v-if="batches.length" class="batch-history">
      <h2>Previous Batches</h2>
      <div v-for="b in batches" :key="b.batch_id" class="batch-item" @click="loadBatch(b.batch_id)">
        <span>{{ b.batch_id }}</span>
        <span>{{ b.scenario_name }}</span>
        <span>{{ b.status }}</span>
        <span>{{ b.completed_runs }}/{{ b.total_runs }} runs</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getScenarios, createBatch, getBatchStatus, getBatchReport, getBatchRuns, listBatches } from '../api/client'

const scenarios = ref([])
const selectedScenario = ref('')
const numRuns = ref(5)
const maxTurns = ref(10)
const showConfig = ref(true)
const loading = ref(false)
const activeBatch = ref(null)
const report = ref(null)
const runs = ref([])
const batches = ref([])

const progressPercent = computed(() => {
  if (!activeBatch.value) return 0
  return (activeBatch.value.completed_runs / activeBatch.value.total_runs * 100).toFixed(0)
})

onMounted(async () => {
  scenarios.value = await getScenarios()
  if (scenarios.value.length) selectedScenario.value = scenarios.value[0].name
  batches.value = await listBatches()
})

async function startBatch() {
  loading.value = true
  const params = Array.from({ length: numRuns.value }, (_, i) => ({
    name: `run_${i}`,
    rng_seed: 42 + i,
    max_turns: maxTurns.value,
    use_llm: false,
  }))
  const result = await createBatch(selectedScenario.value, params)
  activeBatch.value = result
  showConfig.value = false
  pollStatus(result.batch_id)
}

async function pollStatus(batchId) {
  const interval = setInterval(async () => {
    const status = await getBatchStatus(batchId)
    activeBatch.value = status
    if (status.status !== 'RUNNING') {
      clearInterval(interval)
      loading.value = false
      await loadBatch(batchId)
    }
  }, 2000)
}

async function loadBatch(batchId) {
  try {
    const [reportData, runData] = await Promise.all([
      getBatchReport(batchId),
      getBatchRuns(batchId),
    ])
    report.value = reportData.report
    runs.value = runData
    activeBatch.value = null
  } catch (e) {
    console.error('Failed to load batch:', e)
  }
}

function winnerClass(winner) {
  return { 'win-blue': winner === 'BLUE', 'win-red': winner === 'RED', 'win-draw': winner === 'DRAW' }
}
</script>

<style scoped>
.batch-view { padding: 20px; max-width: 1200px; margin: 0 auto; color: #e2e8f0; }
.batch-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
h1 { font-size: 24px; }
h2 { font-size: 18px; margin: 16px 0 8px; }
.btn-config, .btn-start { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
.btn-config { background: #334155; color: #e2e8f0; }
.btn-start { background: #2563eb; color: #fff; }
.btn-start:disabled { opacity: 0.5; }
.config-panel { background: #1e293b; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.config-form { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.config-form label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.config-form input, .config-form select { padding: 6px 10px; border: 1px solid #475569; border-radius: 4px; background: #0f172a; color: #e2e8f0; }
.progress-bar { height: 8px; background: #1e293b; border-radius: 4px; overflow: hidden; margin: 8px 0; }
.progress-fill { height: 100%; background: #2563eb; transition: width 0.3s; }
.report-section { margin: 16px 0; }
.report-card { background: #1e293b; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; }
.report-card h3 { font-size: 14px; color: #94a3b8; margin-bottom: 4px; }
.report-card p { font-size: 14px; line-height: 1.5; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #1e293b; }
th { background: #1e293b; color: #94a3b8; font-weight: 600; }
.win-blue { background: rgba(37, 99, 235, 0.1); }
.win-red { background: rgba(239, 68, 68, 0.1); }
.win-draw { background: rgba(107, 114, 128, 0.1); }
.batch-history { margin-top: 24px; }
.batch-item { display: flex; gap: 16px; padding: 8px 12px; background: #1e293b; border-radius: 6px; margin-bottom: 4px; cursor: pointer; font-size: 13px; }
.batch-item:hover { background: #334155; }
</style>
