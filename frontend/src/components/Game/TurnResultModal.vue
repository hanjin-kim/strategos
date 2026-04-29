<template>
  <Transition name="modal">
    <div class="modal-overlay" @click.self="$emit('dismiss')">
      <div class="modal">
        <div class="modal-header">
          <h3>Turn {{ result.turn }}</h3>
          <span v-if="result.victory" class="victory-badge">Game Over</span>
        </div>

        <div class="stat-grid">
          <div class="stat">
            <div class="stat-val">{{ result.movements }}</div>
            <div class="stat-lbl">Movements</div>
          </div>
          <div class="stat">
            <div class="stat-val">{{ result.combats }}</div>
            <div class="stat-lbl">Combats</div>
          </div>
          <div class="stat">
            <div class="stat-val">{{ result.destroyed_units?.length ?? 0 }}</div>
            <div class="stat-lbl">Destroyed</div>
          </div>
        </div>

        <div v-if="result.staff_briefing" class="section briefing">
          <div class="section-lbl">Staff Briefing</div>
          <div class="briefing-box">
            <span class="star">&#x2605;</span>
            <p>{{ result.staff_briefing }}</p>
          </div>
        </div>

        <div v-if="result.enemy_dialogue?.length" class="section">
          <div class="section-lbl">Intercepted Enemy Communications</div>
          <div v-for="(msg, i) in result.enemy_dialogue" :key="i" class="comm" :class="msg.tone">
            <span class="comm-who">{{ msg.speaker }}:</span>
            <span class="comm-msg">"{{ msg.text }}"</span>
          </div>
        </div>

        <div v-if="result.destroyed_units?.length" class="section">
          <div class="section-lbl">Units Destroyed</div>
          <div v-for="uid in result.destroyed_units" :key="uid" class="destroyed">{{ uid }}</div>
        </div>

        <div v-if="result.narrative" class="section">
          <div class="section-lbl">Battle Report</div>
          <p class="narrative-text">{{ result.narrative }}</p>
        </div>

        <button class="btn-continue" @click="$emit('dismiss')">
          {{ result.victory ? 'View Final State' : 'Continue' }}
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
defineProps({ result: Object })
defineEmits(['dismiss'])
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.65);
  display: flex; align-items: center; justify-content: center; z-index: 50;
  backdrop-filter: blur(4px);
}
.modal {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  width: 460px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.modal-header h3 { font-size: 1.1rem; font-weight: 800; color: var(--text-primary); }
.victory-badge {
  padding: 0.2rem 0.65rem; border-radius: 6px;
  background: rgba(234, 179, 8, 0.15); color: var(--yellow);
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
}

.stat-grid { display: flex; gap: 0.6rem; margin-bottom: 1rem; }
.stat {
  flex: 1; text-align: center; background: var(--bg-secondary);
  border-radius: var(--radius-sm); padding: 0.6rem;
}
.stat-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.4rem; font-weight: 700; color: var(--text-primary);
}
.stat-lbl { font-size: 0.6rem; color: var(--text-muted); text-transform: uppercase; margin-top: 0.15rem; letter-spacing: 0.04em; }

.section { margin-bottom: 0.85rem; }
.section-lbl {
  font-size: 0.6rem; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem;
}

.briefing-box {
  display: flex; gap: 0.5rem; align-items: flex-start;
  background: rgba(76, 201, 240, 0.06); border-radius: var(--radius-sm); padding: 0.65rem 0.8rem;
  border: 1px solid rgba(76, 201, 240, 0.1);
}
.star { color: var(--yellow); font-size: 0.85rem; flex-shrink: 0; }
.briefing-box p { color: var(--text-secondary); margin: 0; font-size: 0.82rem; line-height: 1.5; }

.comm {
  padding: 0.4rem 0.65rem; background: var(--bg-secondary); border-radius: var(--radius-sm);
  border-left: 3px solid var(--text-muted); margin-bottom: 0.35rem; font-size: 0.82rem;
}
.comm.defiant { border-left-color: var(--red); }
.comm.frustrated { border-left-color: var(--yellow); }
.comm.confident { border-left-color: var(--green); }
.comm.desperate { border-left-color: #a855f7; }
.comm-who { color: var(--text-primary); font-weight: 600; }
.comm-msg { color: var(--text-secondary); font-style: italic; }

.destroyed { color: var(--red); font-size: 0.82rem; padding: 0.15rem 0; }
.narrative-text { color: var(--text-secondary); font-size: 0.82rem; line-height: 1.5; }

.btn-continue {
  width: 100%; padding: 0.6rem; border: none; border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--accent), #3b82f6); color: #0a0e1a;
  font-weight: 700; font-size: 0.9rem; cursor: pointer; font-family: inherit;
  transition: all 0.15s;
}
.btn-continue:hover { box-shadow: 0 0 20px rgba(76, 201, 240, 0.25); }

.modal-enter-active, .modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal, .modal-leave-to .modal { transform: scale(0.95); }
</style>
