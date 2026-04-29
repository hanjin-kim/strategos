<template>
  <div class="setup">
    <div class="setup-header">
      <h2>New Game</h2>
      <p class="setup-sub">Configure your scenario and take command</p>
    </div>

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <!-- Scenario selection -->
    <div class="section">
      <div class="section-label">Select Scenario</div>
      <div class="scenario-list">
        <div
          v-for="s in militaryScenarios"
          :key="s.name"
          class="scenario-card"
          :class="{ selected: selected === s.name }"
          @click="selected = s.name"
        >
          <div class="sc-radio" :class="{ active: selected === s.name }">
            <div class="sc-radio-dot" v-if="selected === s.name"></div>
          </div>
          <div class="sc-info">
            <div class="sc-name">{{ s.display_name }}</div>
            <div class="sc-desc">{{ s.description }}</div>
          </div>
        </div>
        <div v-if="!store.scenarios.length" class="loading">Loading scenarios...</div>
      </div>
    </div>

    <!-- Game configuration -->
    <div class="config-section" v-if="selected">
      <div class="config-row">
        <div class="config-card">
          <div class="config-label">Play as</div>
          <div class="toggle-group">
            <button :class="{ active: playerSide === 'BLUE', blue: playerSide === 'BLUE' }" @click="playerSide = 'BLUE'">
              <span class="tg-dot blue-dot"></span> BLUE
            </button>
            <button :class="{ active: playerSide === 'RED', red: playerSide === 'RED' }" @click="playerSide = 'RED'">
              <span class="tg-dot red-dot"></span> RED
            </button>
          </div>
        </div>

        <div class="config-card">
          <div class="config-label">Command Mode</div>
          <div class="toggle-group triple">
            <button :class="{ active: commandMode === 'STRATEGIC' }" @click="commandMode = 'STRATEGIC'">Strategic</button>
            <button :class="{ active: commandMode === 'HYBRID' }" @click="commandMode = 'HYBRID'">Hybrid</button>
            <button :class="{ active: commandMode === 'TACTICAL' }" @click="commandMode = 'TACTICAL'">Tactical</button>
          </div>
          <div class="config-hint">{{ modeHint }}</div>
        </div>
      </div>

      <div class="config-row">
        <div class="config-card">
          <div class="config-label">Fog of War</div>
          <div class="toggle-group triple">
            <button :class="{ active: fogMode === 'FULL' }" @click="fogMode = 'FULL'">Full</button>
            <button :class="{ active: fogMode === 'SOFT' }" @click="fogMode = 'SOFT'">Soft</button>
            <button :class="{ active: fogMode === 'OMNISCIENT' }" @click="fogMode = 'OMNISCIENT'">None</button>
          </div>
        </div>

        <div class="config-card">
          <div class="config-label">AI Difficulty</div>
          <div class="toggle-group triple">
            <button :class="{ active: aiDifficulty === 'EASY' }" @click="aiDifficulty = 'EASY'">Easy</button>
            <button :class="{ active: aiDifficulty === 'MEDIUM' }" @click="aiDifficulty = 'MEDIUM'">Medium</button>
            <button :class="{ active: aiDifficulty === 'HARD' }" @click="aiDifficulty = 'HARD'">Hard</button>
          </div>
          <div class="config-hint">{{ diffHint }}</div>
        </div>
      </div>

      <div class="config-row single">
        <div class="config-card narrow">
          <div class="config-label">Max Turns</div>
          <input v-model.number="maxTurns" type="number" min="1" max="200" class="turns-input" />
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="actions" v-if="selected">
      <button class="btn-start" @click="startGame">
        <span class="btn-play">&#9654;</span> Start Game
      </button>
      <button class="btn-watch" @click="watchAI">Watch AI vs AI</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSimulationStore } from '../store/simulation'

const store = useSimulationStore()
const router = useRouter()

const selected = ref(null)
const playerSide = ref('BLUE')
const commandMode = ref('HYBRID')
const fogMode = ref('SOFT')
const aiDifficulty = ref('MEDIUM')
const maxTurns = ref(72)

const militaryScenarios = computed(() =>
  store.scenarios.filter(s => s.domain !== 'business')
)

const modeHint = computed(() => ({
  STRATEGIC: 'Issue mission orders to battalions',
  HYBRID: 'Mission orders + direct unit control',
  TACTICAL: 'Direct control of each unit',
}[commandMode.value]))

const diffHint = computed(() => ({
  EASY: 'Rule-based AI, cautious behavior',
  MEDIUM: 'LLM-powered, balanced doctrine',
  HARD: 'LLM-powered, aggressive & optimal',
}[aiDifficulty.value]))

onMounted(() => store.loadScenarios())

async function startGame() {
  await store.createGame(selected.value, {
    player_side: playerSide.value,
    command_mode: commandMode.value,
    fog_mode: fogMode.value,
    ai_difficulty: aiDifficulty.value,
    max_turns: maxTurns.value,
  })
  if (store.currentSimulationId) {
    router.push({ name: 'game', params: { id: store.currentSimulationId } })
  }
}

async function watchAI() {
  await store.createAndStart(selected.value, maxTurns.value)
  if (store.currentSimulationId) {
    router.push({ name: 'simulation', params: { id: store.currentSimulationId } })
  }
}
</script>

<style scoped>
.setup { max-width: 640px; margin: 0 auto; padding-top: 1rem; }

.setup-header { margin-bottom: 1.75rem; }
.setup-header h2 {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}
.setup-sub { color: var(--text-muted); font-size: 0.85rem; }

.section { margin-bottom: 1.5rem; }
.section-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.6rem;
}

.scenario-list { display: flex; flex-direction: column; gap: 0.5rem; }
.scenario-card {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: var(--bg-card);
  padding: 0.85rem 1rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid var(--border-subtle);
  transition: all 0.15s;
}
.scenario-card:hover { border-color: var(--border-default); background: var(--bg-card-hover); }
.scenario-card.selected { border-color: var(--border-active); background: rgba(76, 201, 240, 0.05); }

.sc-radio {
  width: 18px; height: 18px; border-radius: 50%;
  border: 2px solid var(--text-muted);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 1px;
  transition: border-color 0.15s;
}
.sc-radio.active { border-color: var(--accent); }
.sc-radio-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }

.sc-name { font-weight: 600; font-size: 0.85rem; color: var(--text-primary); margin-bottom: 0.15rem; }
.sc-desc { font-size: 0.75rem; color: var(--text-muted); line-height: 1.4; }

.config-section { margin-bottom: 1.5rem; }
.config-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.config-row.single { grid-template-columns: 1fr; }
.config-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
}
.config-card.narrow { max-width: 200px; }
.config-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.5rem;
}
.config-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 0.4rem;
  font-style: italic;
}

.toggle-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.3rem;
}
.toggle-group.triple { grid-template-columns: 1fr 1fr 1fr; }
.toggle-group button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
  font-family: inherit;
  transition: all 0.15s;
}
.toggle-group button:hover { background: var(--bg-elevated); color: var(--text-primary); }
.toggle-group button.active {
  background: var(--accent-glow);
  color: var(--accent);
  border-color: var(--border-active);
}
.toggle-group button.blue.active { background: var(--blue-bg); color: var(--blue); border-color: rgba(59, 130, 246, 0.3); }
.toggle-group button.red.active { background: var(--red-bg); color: var(--red); border-color: rgba(239, 68, 68, 0.3); }

.tg-dot { width: 8px; height: 8px; border-radius: 50%; }
.blue-dot { background: var(--blue); }
.red-dot { background: var(--red); }

.turns-input {
  width: 100%;
  padding: 0.4rem 0.6rem;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-family: 'JetBrains Mono', monospace;
  outline: none;
  transition: border-color 0.15s;
}
.turns-input:focus { border-color: var(--accent); }

.actions { display: flex; gap: 0.75rem; }
.btn-start {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  justify-content: center;
  padding: 0.7rem 1.5rem;
  background: linear-gradient(135deg, var(--accent), #3b82f6);
  color: #0a0e1a;
  border: none;
  border-radius: var(--radius-md);
  font-weight: 700;
  font-size: 0.9rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 0 20px rgba(76, 201, 240, 0.15);
}
.btn-start:hover { box-shadow: 0 0 30px rgba(76, 201, 240, 0.3); transform: translateY(-1px); }
.btn-play { font-size: 0.7rem; }
.btn-watch {
  padding: 0.7rem 1.5rem;
  background: var(--bg-card);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 0.85rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-watch:hover { background: var(--bg-card-hover); color: var(--text-primary); }

.error-banner {
  background: var(--red-bg);
  color: var(--red);
  padding: 0.65rem 1rem;
  border-radius: var(--radius-sm);
  margin-bottom: 1rem;
  font-size: 0.85rem;
  border: 1px solid rgba(239, 68, 68, 0.2);
}
.loading { color: var(--text-muted); text-align: center; padding: 2rem; font-size: 0.85rem; }
</style>
