<template>
  <div class="market-graph">
    <svg :width="width" :height="height" class="graph-svg">
      <!-- Connections -->
      <line
        v-for="(edge, i) in edges"
        :key="'edge-' + i"
        :x1="edge.x1" :y1="edge.y1"
        :x2="edge.x2" :y2="edge.y2"
        stroke="#334155" stroke-width="2" stroke-dasharray="4,4"
      />
      <!-- Market Nodes -->
      <g v-for="node in nodes" :key="node.id" :transform="`translate(${node.x}, ${node.y})`">
        <rect
          :width="nodeWidth" :height="nodeHeight"
          :x="-nodeWidth/2" :y="-nodeHeight/2"
          rx="8" ry="8"
          :fill="node.contested ? '#1e293b' : '#0f172a'"
          :stroke="node.contested ? '#f59e0b' : '#334155'"
          stroke-width="2"
        />
        <text text-anchor="middle" y="-20" fill="#94a3b8" font-size="11" font-weight="600">
          {{ node.region }}
        </text>
        <text text-anchor="middle" y="-6" fill="#e2e8f0" font-size="13" font-weight="700">
          {{ node.segment }}
        </text>
        <!-- Units in this market -->
        <g v-for="(unit, j) in node.units" :key="unit.id" :transform="`translate(${(j - node.units.length/2 + 0.5) * 60}, 18)`">
          <rect
            width="52" height="28" x="-26" y="-4" rx="4"
            :fill="sideColor(unit.side)"
            opacity="0.9"
          />
          <text text-anchor="middle" y="10" :fill="sideTextColor(unit.side)" font-size="9" font-weight="600">
            {{ unit.name.length > 8 ? unit.name.substring(0, 8) : unit.name }}
          </text>
          <text text-anchor="middle" y="20" fill="#cbd5e1" font-size="8">
            {{ (unit.market_share * 100).toFixed(0) }}%
          </text>
        </g>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  markets: { type: Array, default: () => [] },
  units: { type: Object, default: () => ({}) },
  width: { type: Number, default: 900 },
  height: { type: Number, default: 500 },
})

const nodeWidth = 160
const nodeHeight = 70

const nodes = computed(() => {
  const regions = [...new Set(props.markets.map(m => m.region))]
  const segments = [...new Set(props.markets.map(m => m.segment))]

  return props.markets.map(market => {
    const ri = regions.indexOf(market.region)
    const si = segments.indexOf(market.segment)
    const x = 100 + ri * (props.width - 200) / Math.max(regions.length - 1, 1)
    const y = 60 + si * (props.height - 120) / Math.max(segments.length - 1, 1)

    const marketUnits = Object.values(props.units).filter(u => {
      if (u.position && u.position.region) {
        return u.position.region === market.region && u.position.segment === market.segment
      }
      return false
    })

    const sides = new Set(marketUnits.map(u => u.side))

    return {
      id: `${market.region}:${market.segment}`,
      region: market.region,
      segment: market.segment,
      x, y,
      units: marketUnits,
      contested: sides.size > 1,
      connections: market.connections || [],
    }
  })
})

const edges = computed(() => {
  const nodeMap = {}
  nodes.value.forEach(n => { nodeMap[n.id] = n })

  const edgeSet = new Set()
  const result = []

  nodes.value.forEach(node => {
    ;(node.connections || []).forEach(connId => {
      const target = nodeMap[connId]
      if (target) {
        const key = [node.id, connId].sort().join('--')
        if (!edgeSet.has(key)) {
          edgeSet.add(key)
          result.push({ x1: node.x, y1: node.y, x2: target.x, y2: target.y })
        }
      }
    })
  })
  return result
})

function sideColor(side) {
  const colors = {
    'Netflix': '#e50914', 'DisneyPlus': '#113ccf', 'Disney+': '#113ccf',
    'LGES': '#1e40af', 'CATL': '#991b1b',
    'AWS': '#ff9900', 'Azure': '#0078d4',
    'BLUE': '#1e40af', 'RED': '#991b1b',
  }
  return colors[side] || '#475569'
}

function sideTextColor() {
  return '#ffffff'
}
</script>

<style scoped>
.market-graph {
  background: #0a0f1a;
  border-radius: 8px;
  overflow: hidden;
}
.graph-svg {
  display: block;
}
</style>
