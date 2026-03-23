import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export async function getScenarios() {
  const { data } = await api.get('/scenarios/')
  return data
}

export async function getScenario(name) {
  const { data } = await api.get(`/scenarios/${name}`)
  return data
}

export async function createSimulation(scenarioName) {
  const { data } = await api.post('/simulations', { scenario_name: scenarioName })
  return data
}

export async function startSimulation(simId, maxTurns = 72) {
  const { data } = await api.post(`/simulations/${simId}/start`, { max_turns: maxTurns })
  return data
}

export async function getSimulationStatus(simId) {
  const { data } = await api.get(`/simulations/${simId}/status`)
  return data
}

export async function getSimulationState(simId, turn = null) {
  const params = turn !== null ? { turn } : {}
  const { data } = await api.get(`/simulations/${simId}/state`, { params })
  return data
}

export async function getSimulationLog(simId, turn = null) {
  const params = turn !== null ? { turn } : {}
  const { data } = await api.get(`/simulations/${simId}/log`, { params })
  return data
}

export async function stopSimulation(simId) {
  const { data } = await api.post(`/simulations/${simId}/stop`)
  return data
}

export async function getSimulationNarrative(simId, turn) {
  const { data } = await api.get(`/simulations/${simId}/narrative`, { params: { turn } })
  return data
}

export async function createBatch(scenarioName, parameterSets) {
  const { data } = await api.post('/batches', { scenario_name: scenarioName, parameter_sets: parameterSets })
  return data
}

export async function getBatchStatus(batchId) {
  const { data } = await api.get(`/batches/${batchId}/status`)
  return data
}

export async function getBatchReport(batchId) {
  const { data } = await api.get(`/batches/${batchId}/report`)
  return data
}

export async function getBatchRuns(batchId) {
  const { data } = await api.get(`/batches/${batchId}/runs`)
  return data
}

export async function listBatches() {
  const { data } = await api.get('/batches')
  return data
}

export function connectStream(simId, onUpdate) {
  const source = new EventSource(`/api/simulations/${simId}/stream`)
  source.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onUpdate(data)
  }
  source.onerror = () => {
    source.close()
  }
  return source
}
