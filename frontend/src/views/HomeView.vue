<template>
  <div class="home">
    <div class="hero">
      <div class="hero-badge">AI-Powered Wargame Engine</div>
      <h1>STRATEGOS</h1>
      <p class="hero-sub">Command your forces in a modern warfare simulation powered by multi-agent AI decision making</p>
      <div class="hero-actions">
        <router-link to="/setup" class="btn-primary">
          <span class="btn-icon">&#9654;</span> New Game
        </router-link>
        <router-link to="/batch" class="btn-secondary">Batch Analysis</router-link>
      </div>
    </div>

    <div class="features">
      <div class="feature-card">
        <div class="feature-icon">&#x2694;</div>
        <h3>CRT Combat</h3>
        <p>Combat Results Table resolution with terrain, supply, and air support modifiers</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">&#x21C4;</div>
        <h3>WEGO Turns</h3>
        <p>Simultaneous execution model — Command, Execute, Resolve in each turn</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">&#x2699;</div>
        <h3>AI Commanders</h3>
        <p>LLM-driven theater and battalion commanders with OODA decision loops</p>
      </div>
    </div>

    <div v-if="scenarios.length" class="scenarios-section">
      <div class="section-header">
        <span class="section-line"></span>
        <h2>Scenarios</h2>
        <span class="section-line"></span>
      </div>
      <div class="scenario-grid">
        <div
          v-for="scenario in scenarios"
          :key="scenario.name"
          class="scenario-card"
          @click="launchScenario(scenario)"
        >
          <div class="scenario-top">
            <span class="scenario-name">{{ scenario.display_name || scenario.name }}</span>
            <span class="domain-tag" :class="scenario.domain">
              {{ scenario.domain === 'business' ? 'Business' : 'Military' }}
            </span>
          </div>
          <p v-if="scenario.description" class="scenario-desc">{{ scenario.description }}</p>
          <div class="scenario-arrow">&#x2192;</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getScenarios, createSimulation } from '../api/client'

const router = useRouter()
const scenarios = ref([])

onMounted(async () => {
  try { scenarios.value = await getScenarios() } catch {}
})

async function launchScenario(scenario) {
  try {
    const { simulation_id } = await createSimulation(scenario.name)
    if (scenario.domain === 'business') {
      router.push({ name: 'business-simulation', params: { id: simulation_id } })
    } else {
      router.push({ name: 'simulation', params: { id: simulation_id } })
    }
  } catch { router.push('/setup') }
}
</script>

<style scoped>
.home { max-width: 960px; margin: 0 auto; }

.hero {
  text-align: center;
  padding: 4rem 1rem 3rem;
}
.hero-badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-glow);
  padding: 0.3rem 0.9rem;
  border-radius: 20px;
  margin-bottom: 1.25rem;
  border: 1px solid rgba(76, 201, 240, 0.2);
}
.hero h1 {
  font-size: 3.2rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  background: linear-gradient(135deg, #f1f5f9 0%, #4cc9f0 60%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.75rem;
}
.hero-sub {
  color: var(--text-secondary);
  font-size: 1rem;
  line-height: 1.6;
  max-width: 520px;
  margin: 0 auto 2rem;
}
.hero-actions { display: flex; gap: 0.75rem; justify-content: center; }

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.75rem;
  background: linear-gradient(135deg, var(--accent), #3b82f6);
  color: #0a0e1a;
  text-decoration: none;
  border-radius: var(--radius-md);
  font-weight: 700;
  font-size: 0.9rem;
  transition: all 0.2s;
  box-shadow: 0 0 20px rgba(76, 201, 240, 0.2);
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 30px rgba(76, 201, 240, 0.35);
}
.btn-icon { font-size: 0.75rem; }
.btn-secondary {
  display: inline-flex;
  align-items: center;
  padding: 0.65rem 1.75rem;
  background: var(--bg-card);
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 0.9rem;
  border: 1px solid var(--border-default);
  transition: all 0.2s;
}
.btn-secondary:hover { background: var(--bg-card-hover); color: var(--text-primary); }

.features {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 3.5rem;
}
.feature-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  transition: all 0.2s;
}
.feature-card:hover {
  border-color: var(--border-default);
  background: var(--bg-card-hover);
}
.feature-icon {
  font-size: 1.5rem;
  margin-bottom: 0.75rem;
  opacity: 0.7;
}
.feature-card h3 {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.4rem;
}
.feature-card p {
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.scenarios-section { margin-bottom: 2rem; }
.section-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
}
.section-line { flex: 1; height: 1px; background: var(--border-subtle); }
.section-header h2 {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}
.scenario-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.scenario-card:hover {
  border-color: var(--border-active);
  background: var(--bg-card-hover);
}
.scenario-card:hover .scenario-arrow { opacity: 1; transform: translateX(0); }
.scenario-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}
.scenario-name { font-weight: 700; font-size: 0.85rem; color: var(--text-primary); }
.domain-tag {
  font-size: 0.6rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.domain-tag.military { background: var(--blue-bg); color: var(--blue); }
.domain-tag.business { background: rgba(74, 222, 128, 0.12); color: #4ade80; }
.scenario-desc { font-size: 0.75rem; color: var(--text-muted); line-height: 1.4; }
.scenario-arrow {
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateX(-4px) translateY(-50%);
  opacity: 0;
  color: var(--accent);
  font-size: 1rem;
  transition: all 0.2s;
}
</style>
