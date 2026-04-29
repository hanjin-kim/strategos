import { defineStore } from 'pinia'
import {
  getScenarios, createSimulation, startSimulation,
  getSimulationStatus, getSimulationState, stopSimulation,
  connectStream, submitCommands, stepTurn, getAvailableActions,
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

    // Player mode state
    gameConfig: null,
    mode: 'observer',
    availableActions: null,
    pendingCommands: [],
    selectedUnit: null,
    commandIntent: 'MOVE',
    lastTurnResult: null,
    showTurnResult: false,
    isSteppingTurn: false,
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
    isPlayerMode: (state) => state.mode === 'player',
    playerSide: (state) => state.gameConfig?.player_side ?? null,
    commandMode: (state) => state.gameConfig?.command_mode ?? 'HYBRID',
    fogMode: (state) => state.gameConfig?.fog_mode ?? 'OMNISCIENT',

    playerUnits: (state) => {
      if (!state.gameConfig?.player_side || !state.gameState?.units) return []
      return Object.values(state.gameState.units).filter(
        u => u.side === state.gameConfig.player_side && u.status !== 'DESTROYED'
      )
    },

    selectedUnitActions: (state) => {
      if (!state.selectedUnit || !state.availableActions) return null
      return state.availableActions.units?.find(u => u.unit_id === state.selectedUnit.id)
    },

    pendingCommandForUnit: (state) => (unitId) => {
      return state.pendingCommands.find(c => c.unit_id === unitId)
    },

    reachableHexes: (state) => {
      if (!state.selectedUnit || !state.availableActions) return new Set()
      const unitActions = state.availableActions.units?.find(
        u => u.unit_id === state.selectedUnit.id
      )
      if (!unitActions) return new Set()
      const moveAction = unitActions.available_actions.find(a => a.type === 'MOVE')
      if (!moveAction) return new Set()
      return new Set(moveAction.valid_hexes.map(h => `${h.q},${h.r}`))
    },

    attackTargets: (state) => {
      if (!state.selectedUnit || !state.availableActions) return []
      const unitActions = state.availableActions.units?.find(
        u => u.unit_id === state.selectedUnit.id
      )
      if (!unitActions) return []
      const atkAction = unitActions.available_actions.find(a => a.type === 'ATTACK')
      return atkAction?.valid_targets ?? []
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

    // Observer mode: auto-play
    async createAndStart(scenarioName, maxTurns = 72) {
      try {
        this.error = null
        const { simulation_id } = await createSimulation(scenarioName)
        this.currentSimulationId = simulation_id
        this.maxTurns = maxTurns
        this.mode = 'observer'
        this.gameConfig = null
        await startSimulation(simulation_id, maxTurns)
        this.isRunning = true
        this.startPolling()
      } catch (e) {
        this.error = e.message
      }
    },

    // Player mode: step-by-step
    async createGame(scenarioName, config) {
      try {
        this.error = null
        const result = await createSimulation(scenarioName, config)
        this.currentSimulationId = result.simulation_id
        this.gameConfig = result.game_config
        this.mode = result.mode
        this.maxTurns = config.max_turns || 72
        this.status = 'waiting_for_commands'
        this.pendingCommands = []
        this.selectedUnit = null
        this.lastTurnResult = null
        await this.fetchState()
        await this.fetchAvailableActions()
      } catch (e) {
        this.error = e.message
      }
    },

    async fetchAvailableActions() {
      if (!this.currentSimulationId || this.mode !== 'player') return
      try {
        this.availableActions = await getAvailableActions(this.currentSimulationId)
      } catch (e) {
        this.error = e.message
      }
    },

    selectUnit(unit) {
      if (!unit || unit.side !== this.playerSide) {
        this.selectedUnit = null
        return
      }
      this.selectedUnit = unit
      this.commandIntent = 'MOVE'
    },

    setCommandIntent(intent) {
      this.commandIntent = intent
    },

    addCommand(command) {
      const existing = this.pendingCommands.findIndex(c => c.unit_id === command.unit_id)
      if (existing >= 0) {
        this.pendingCommands[existing] = command
      } else {
        this.pendingCommands.push(command)
      }
    },

    removeCommand(unitId) {
      this.pendingCommands = this.pendingCommands.filter(c => c.unit_id !== unitId)
    },

    clearCommands() {
      this.pendingCommands = []
    },

    async submitAndStep() {
      if (!this.currentSimulationId) return
      this.isSteppingTurn = true
      this.error = null

      try {
        const orders = []
        const actions = []

        for (const cmd of this.pendingCommands) {
          if (cmd.type === 'order') {
            orders.push({
              target_unit_id: cmd.unit_id,
              mission: cmd.mission,
              objective_hex: cmd.target_hex ?? null,
              priority: cmd.priority ?? 3,
            })
          } else {
            actions.push({
              unit_id: cmd.unit_id,
              action_type: cmd.action_type,
              target_hex: cmd.target_hex ?? null,
              target_unit_id: cmd.target_unit_id ?? null,
            })
          }
        }

        if (orders.length || actions.length) {
          await submitCommands(this.currentSimulationId, { orders, actions })
        }

        const result = await stepTurn(this.currentSimulationId)
        this.lastTurnResult = result
        this.currentTurn = result.turn
        this.status = result.status
        this.showTurnResult = true
        this.currentNarrative = {
          summary: result.narrative || '',
          enemy_dialogue: result.enemy_dialogue || [],
          staff_briefing: result.staff_briefing || '',
          event_reactions: result.event_reactions || [],
        }

        this.pendingCommands = []
        this.selectedUnit = null
        await this.fetchState()
        await this.fetchAvailableActions()
      } catch (e) {
        this.error = e.response?.data?.error ?? e.message
      } finally {
        this.isSteppingTurn = false
      }
    },

    dismissTurnResult() {
      this.showTurnResult = false
    },

    // Shared actions (observer + player)
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
        this.maxTurns = data.max_turns
        this.isRunning = data.status === 'running'
        if (data.game_config) {
          this.gameConfig = data.game_config
          this.mode = data.mode
        }
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
