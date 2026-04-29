<template>
  <div id="app">
    <nav class="nav-bar">
      <router-link to="/" class="nav-brand">
        <span class="brand-icon">&#x2726;</span>
        <span class="brand-text">STRATEGOS</span>
      </router-link>
      <div class="nav-links">
        <router-link to="/setup" class="nav-link">New Game</router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-primary: #0a0e1a;
  --bg-secondary: #111827;
  --bg-card: #1a2235;
  --bg-card-hover: #1f2a40;
  --bg-elevated: #243049;
  --border-subtle: rgba(148, 163, 184, 0.08);
  --border-default: rgba(148, 163, 184, 0.12);
  --border-active: rgba(76, 201, 240, 0.4);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent: #4cc9f0;
  --accent-glow: rgba(76, 201, 240, 0.15);
  --blue: #3b82f6;
  --blue-bg: rgba(59, 130, 246, 0.12);
  --red: #ef4444;
  --red-bg: rgba(239, 68, 68, 0.12);
  --green: #22c55e;
  --yellow: #eab308;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
}

.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  height: 52px;
  background: rgba(17, 24, 39, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--text-primary);
}
.brand-icon {
  color: var(--accent);
  font-size: 1.1rem;
}
.brand-text {
  font-weight: 800;
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  color: var(--text-primary);
}

.nav-links { display: flex; gap: 0.25rem; }
.nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  padding: 0.4rem 0.85rem;
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.15s;
}
.nav-link:hover { background: var(--bg-card); color: var(--text-primary); }
.nav-link.router-link-active { background: var(--accent-glow); color: var(--accent); }

.main-content {
  padding: 1.25rem 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
  min-height: calc(100vh - 52px);
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bg-elevated); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
