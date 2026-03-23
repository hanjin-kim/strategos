<template>
  <div class="home">
    <h1>Wargame Simulation Platform</h1>
    <p class="subtitle">AI-powered modern warfare simulation with multi-agent decision making</p>
    <div class="features">
      <div class="feature">
        <h3>CRT Combat</h3>
        <p>Combat Results Table based resolution with terrain modifiers</p>
      </div>
      <div class="feature">
        <h3>WEGO Turns</h3>
        <p>Simultaneous execution with 3-phase turn model</p>
      </div>
      <div class="feature">
        <h3>AI Commanders</h3>
        <p>LLM-powered theater and battalion commanders with OODA loops</p>
      </div>
    </div>
    <div class="actions">
      <router-link to="/setup" class="start-btn">Start Simulation</router-link>
      <router-link to="/batch" class="batch-btn">Batch Analysis</router-link>
    </div>
  </div>
</template>

<style scoped>
.home { text-align: center; padding: 3rem 1rem; }
h1 { font-size: 2.5rem; margin-bottom: 0.5rem; color: #4cc9f0; }
.subtitle { color: #888; margin-bottom: 3rem; font-size: 1.1rem; }
.features { display: flex; gap: 2rem; justify-content: center; margin-bottom: 3rem; flex-wrap: wrap; }
.feature { background: #16213e; padding: 1.5rem; border-radius: 8px; width: 250px; border: 1px solid #0f3460; }
.feature h3 { color: #4cc9f0; margin-bottom: 0.5rem; }
.actions { display: flex; gap: 1rem; justify-content: center; }
.start-btn { display: inline-block; padding: 0.75rem 2rem; background: #4cc9f0; color: #1a1a2e; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 1.1rem; }
.start-btn:hover { background: #3db8df; }
.batch-btn { display: inline-block; padding: 0.75rem 2rem; background: #334155; color: #e2e8f0; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 1.1rem; }
.batch-btn:hover { background: #475569; }
</style>
