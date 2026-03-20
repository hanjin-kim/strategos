<template>
  <div class="battlefield" ref="container">
    <svg :viewBox="viewBox" class="hex-svg" @wheel.prevent="onZoom" @mousedown="onPanStart" @mousemove="onPanMove" @mouseup="onPanEnd">
      <g :transform="`translate(${panX},${panY}) scale(${zoom})`">
        <!-- Terrain hexes -->
        <g v-for="(hex, key) in terrainMap" :key="key">
          <polygon
            :points="hexPoints(hex.coord.q, hex.coord.r)"
            :fill="terrainColor(hex.terrain_type)"
            stroke="#2a2a4a"
            stroke-width="0.5"
            @click="selectHex(hex)"
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
        <!-- Unit markers -->
        <g v-for="unit in unitList" :key="unit.id">
          <UnitMarker :unit="unit" :center="hexCenter(unit.position.q, unit.position.r)" :size="hexSize * 0.6" />
        </g>
      </g>
    </svg>
    <!-- Selected hex info -->
    <div v-if="selectedHex" class="hex-info">
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
  PLAIN: '#3a5a40',
  MOUNTAIN: '#6b4423',
  URBAN: '#555566',
  FOREST: '#2d4a22',
  RIVER: '#1e6091',
  WATER: '#0a3055',
  BRIDGE: '#8a7a5a',
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

function selectHex(hex) { selectedHex.value = hex }

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
</script>

<style scoped>
.battlefield { position: relative; width: 100%; height: 100%; }
.hex-svg { width: 100%; height: 100%; background: #0d1117; cursor: grab; }
.hex-svg:active { cursor: grabbing; }
polygon { cursor: pointer; transition: opacity 0.15s; }
polygon:hover { opacity: 0.8; }
.hex-info { position: absolute; bottom: 1rem; left: 1rem; background: rgba(22, 33, 62, 0.95); padding: 0.75rem 1rem; border-radius: 6px; display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; border: 1px solid #0f3460; }
.unit-info { color: #4cc9f0; font-size: 0.8rem; }
</style>
