import { defineStore } from 'pinia'
import {
  getScenarios, createSimulation, startSimulation,
  getSimulationStatus, getSimulationState, stopSimulation,
  connectStream
} from '../api/client'

export const useSimulationStore = defineStore('simulation', {
  state: () => ({
    scenarios: [],
    currentSimulationId: null,
    gameState: null,
    status: null,
    currentTurn: 0,
    maxTurns: 72,
    isRunning: false,
    error: null,
    eventSource: null,
    viewSide: 'OMNISCIENT',
    currentNarrative: null,
    intelReports: {},
    supplyStatus: {},
    airMissions: [],
  }),
  getters: {
    units: (state) => {
      if (!state.gameState?.units) return []
      return Object.values(state.gameState.units)
    },
    unitsByHex: (state) => {
      const map = {}
      if (!state.gameState?.units) return map
      for (const unit of Object.values(state.gameState.units)) {
        const key = `${unit.position.q},${unit.position.r}`
        if (!map[key]) map[key] = []
        map[key].push(unit)
      }
      return map
    },
    terrain: (state) => {
      if (!state.gameState?.terrain) return {}
      return state.gameState.terrain
    },
  },
  actions: {
    async loadScenarios() {
      try {
        this.scenarios = await getScenarios()
      } catch (e) {
        this.error = e.message
      }
    },
    async createAndStart(scenarioName, maxTurns = 72) {
      try {
        this.error = null
        const { simulation_id } = await createSimulation(scenarioName)
        this.currentSimulationId = simulation_id
        this.maxTurns = maxTurns
        await startSimulation(simulation_id, maxTurns)
        this.isRunning = true
        this.startPolling()
      } catch (e) {
        this.error = e.message
      }
    },
    startPolling() {
      if (this.eventSource) this.eventSource.close()
      this.eventSource = connectStream(this.currentSimulationId, async (data) => {
        this.currentTurn = data.turn
        this.status = data.status
        if (data.status !== 'running') {
          this.isRunning = false
          this.eventSource?.close()
        }
        await this.fetchState()
      })
    },
    async fetchState(turn = null) {
      if (!this.currentSimulationId) return
      try {
        const data = await getSimulationState(this.currentSimulationId, turn)
        this.gameState = data
        if (data.intel_reports) this.intelReports = data.intel_reports
        if (data.supply_status) this.supplyStatus = data.supply_status
      } catch (e) {
        this.error = e.message
      }
    },
    setViewSide(side) {
      this.viewSide = side
    },
    setNarrative(narrative) {
      this.currentNarrative = narrative
    },
    async fetchStatus() {
      if (!this.currentSimulationId) return
      try {
        const data = await getSimulationStatus(this.currentSimulationId)
        this.status = data.status
        this.currentTurn = data.current_turn
        this.isRunning = data.status === 'running'
      } catch (e) {
        this.error = e.message
      }
    },
    async stop() {
      if (!this.currentSimulationId) return
      try {
        await stopSimulation(this.currentSimulationId)
        this.isRunning = false
        this.eventSource?.close()
      } catch (e) {
        this.error = e.message
      }
    },
  },
})
