<template>
  <div class="battlefield" ref="container">
    <svg :viewBox="viewBox" class="hex-svg" @wheel.prevent="onZoom" @mousedown="onPanStart" @mousemove="onPanMove" @mouseup="onPanEnd" @contextmenu.prevent>
      <g :transform="`translate(${panX},${panY}) scale(${zoom})`">
        <!-- Terrain hexes -->
        <g v-for="(hex, key) in terrainMap" :key="key">
          <polygon
            :points="hexPoints(hex.coord.q, hex.coord.r)"
            :fill="terrainColor(hex.terrain_type)"
            stroke="#2a2a4a"
            stroke-width="0.5"
            :class="{ 'hex-clickable': interactive }"
            @click="onHexClick(hex)"
            @contextmenu.prevent="onHexRightClick(hex)"
          />
          <text
            v-if="hex.name"
            :x="hexCenter(hex.coord.q, hex.coord.r).x"
            :y="hexCenter(hex.coord.q, hex.coord.r).y + hexSize * 0.6"
            text-anchor="middle"
            fill="#888"
            :font-size="hexSize * 0.25"
          >{{ hex.name }}</text>
        </g>

        <!-- Movement overlay (reachable hexes) -->
        <MovementOverlay :hexPoints="hexPoints" />

        <!-- Command arrows (pending commands) -->
        <CommandArrow :hexCenter="hexCenter" />

        <!-- Unit markers -->
        <g v-for="unit in unitList" :key="unit.id">
          <UnitMarker
            :unit="unit"
            :center="hexCenter(unit.position.q, unit.position.r)"
            :size="hexSize * 0.6"
            :selected="store.selectedUnit?.id === unit.id"
            :hasPending="!!store.pendingCommandForUnit(unit.id)"
            :isPlayerUnit="interactive && unit.side === store.playerSide"
            @click.stop="onUnitClick(unit)"
          />
        </g>

        <!-- Phase 2 overlays -->
        <FogOverlay
          :hexToPixelX="(h) => hexCenter(h.q, h.r).x"
          :hexToPixelY="(h) => hexCenter(h.q, h.r).y"
          :hexWidth="hexSize * Math.sqrt(3)"
          :hexHeight="hexSize * 2"
          :allHexes="allHexList"
        />
        <SupplyOverlay
          :getUnitX="(id) => hexCenter(unitPosition(id).q, unitPosition(id).r).x"
          :getUnitY="(id) => hexCenter(unitPosition(id).q, unitPosition(id).r).y"
        />
        <AirMissionMarker
          :hexToPixelX="(h) => hexCenter(h.q, h.r).x"
          :hexToPixelY="(h) => hexCenter(h.q, h.r).y"
          :hexWidth="hexSize * Math.sqrt(3)"
        />
      </g>
    </svg>
    <!-- Selected hex info -->
    <div v-if="selectedHex && !interactive" class="hex-info">
      <strong>{{ selectedHex.name || `(${selectedHex.coord.q}, ${selectedHex.coord.r})` }}</strong>
      <span>{{ selectedHex.terrain_type }} | Elev: {{ selectedHex.elevation }}m</span>
      <div v-for="u in unitsAtSelected" :key="u.id" class="unit-info">
        {{ u.name }} ({{ u.side }}) - {{ Math.round(u.strength * 100) }}%
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useSimulationStore } from '../../store/simulation'
import UnitMarker from './UnitMarker.vue'
import FogOverlay from './FogOverlay.vue'
import SupplyOverlay from './SupplyOverlay.vue'
import AirMissionMarker from './AirMissionMarker.vue'
import MovementOverlay from './MovementOverlay.vue'
import CommandArrow from './CommandArrow.vue'

const props = defineProps({
  interactive: { type: Boolean, default: false },
})

const store = useSimulationStore()
const hexSize = 30
const zoom = ref(1)
const panX = ref(50)
const panY = ref(50)
const isPanning = ref(false)
const lastMouse = ref({ x: 0, y: 0 })
const selectedHex = ref(null)

const terrainMap = computed(() => store.terrain)
const unitList = computed(() => store.units.filter(u => u.status !== 'DESTROYED'))
const viewBox = computed(() => `0 0 800 600`)

const TERRAIN_COLORS = {
  PLAIN: '#2a4a32',
  MOUNTAIN: '#5a3a1a',
  URBAN: '#3d3d4f',
  FOREST: '#1e3a1a',
  RIVER: '#164870',
  WATER: '#0a2a48',
  BRIDGE: '#6a5a3a',
}

function terrainColor(type) { return TERRAIN_COLORS[type] || '#3a5a40' }

function hexCenter(q, r) {
  const x = hexSize * (Math.sqrt(3) * q + Math.sqrt(3) / 2 * r)
  const y = hexSize * (3 / 2 * r)
  return { x, y }
}

function hexPoints(q, r) {
  const { x: cx, y: cy } = hexCenter(q, r)
  const points = []
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 180) * (60 * i - 30)
    points.push(`${cx + hexSize * Math.cos(angle)},${cy + hexSize * Math.sin(angle)}`)
  }
  return points.join(' ')
}

function onUnitClick(unit) {
  if (!props.interactive) return
  if (unit.side === store.playerSide) {
    store.selectUnit(unit)
  } else if (store.selectedUnit) {
    issueAttackCommand(unit)
  }
}

function onHexClick(hex) {
  if (!props.interactive) {
    selectedHex.value = hex
    return
  }

  if (!store.selectedUnit) {
    selectedHex.value = hex
    return
  }

  const hexKey = `${hex.coord.q},${hex.coord.r}`
  const unitsHere = store.unitsByHex[hexKey] || []
  const enemyHere = unitsHere.find(u => u.side !== store.playerSide && u.status !== 'DESTROYED')

  if (store.commandIntent === 'ATTACK' && enemyHere) {
    issueAttackCommand(enemyHere)
  } else if (store.reachableHexes.has(hexKey)) {
    issueMoveCommand(hex.coord)
  } else {
    store.selectUnit(null)
    selectedHex.value = hex
  }
}

function onHexRightClick(hex) {
  if (!props.interactive || !store.selectedUnit) return
  const hexKey = `${hex.coord.q},${hex.coord.r}`
  const unitsHere = store.unitsByHex[hexKey] || []
  const enemyHere = unitsHere.find(u => u.side !== store.playerSide && u.status !== 'DESTROYED')

  if (enemyHere) {
    issueAttackCommand(enemyHere)
  } else if (store.reachableHexes.has(hexKey)) {
    issueMoveCommand(hex.coord)
  }
}

function issueMoveCommand(coord) {
  store.addCommand({
    type: 'action',
    unit_id: store.selectedUnit.id,
    action_type: 'MOVE',
    target_hex: { q: coord.q, r: coord.r },
  })
  store.selectUnit(null)
}

function issueAttackCommand(targetUnit) {
  store.addCommand({
    type: 'action',
    unit_id: store.selectedUnit.id,
    action_type: 'ATTACK',
    target_unit_id: targetUnit.id,
    target_hex: { q: targetUnit.position.q, r: targetUnit.position.r },
  })
  store.selectUnit(null)
}

const unitsAtSelected = computed(() => {
  if (!selectedHex.value) return []
  const { q, r } = selectedHex.value.coord
  return store.units.filter(u => u.position.q === q && u.position.r === r)
})

function onZoom(e) { zoom.value = Math.max(0.3, Math.min(3, zoom.value + (e.deltaY > 0 ? -0.1 : 0.1))) }
function onPanStart(e) { isPanning.value = true; lastMouse.value = { x: e.clientX, y: e.clientY } }
function onPanMove(e) {
  if (!isPanning.value) return
  panX.value += e.clientX - lastMouse.value.x
  panY.value += e.clientY - lastMouse.value.y
  lastMouse.value = { x: e.clientX, y: e.clientY }
}
function onPanEnd() { isPanning.value = false }

const allHexList = computed(() => Object.values(store.terrain).map(h => h.coord))

function unitPosition(unitId) {
  const unit = store.units.find(u => u.id === unitId)
  return unit ? unit.position : { q: 0, r: 0 }
}
</script>

<style scoped>
.battlefield { position: relative; width: 100%; height: 100%; }
.hex-svg { width: 100%; height: 100%; background: #080c14; cursor: grab; }
.hex-svg:active { cursor: grabbing; }
polygon { transition: opacity 0.15s; }
polygon:hover { opacity: 0.85; }
.hex-clickable { cursor: pointer; }
.hex-info {
  position: absolute; bottom: 0.75rem; left: 0.75rem;
  background: rgba(26, 34, 53, 0.92); backdrop-filter: blur(8px);
  padding: 0.6rem 0.85rem; border-radius: var(--radius-sm);
  display: flex; flex-direction: column; gap: 0.2rem;
  font-size: 0.78rem; border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}
.hex-info strong { color: var(--text-primary); font-size: 0.82rem; }
.unit-info { color: var(--accent); font-size: 0.75rem; }
</style>
