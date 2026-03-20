<template>
  <div id="app">
    <nav class="nav-bar">
      <router-link to="/" class="nav-link">Home</router-link>
      <router-link to="/setup" class="nav-link">New Simulation</router-link>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; }
.nav-bar { display: flex; gap: 1rem; padding: 0.75rem 1.5rem; background: #16213e; border-bottom: 1px solid #0f3460; }
.nav-link { color: #e0e0e0; text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; }
.nav-link:hover { background: #0f3460; }
.nav-link.router-link-active { background: #0f3460; color: #4cc9f0; }
.main-content { padding: 1.5rem; max-width: 1400px; margin: 0 auto; }
</style>
