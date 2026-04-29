# STRATEGOS

**AI-Powered Wargame Simulation Platform**

A playable hex-based wargame where LLM-driven commanders make decisions through OODA loops, execute simultaneous WEGO turns, and generate in-character battlefield narratives. Play against AI or watch AI vs AI.

<!-- ![Screenshot](docs/screenshot.png) -->

## Features

- **3-Tier Command Hierarchy** — Theater, Division, and Battalion commanders each with distinct decision scope
- **WEGO Turn Model** — Simultaneous execution: Command → Execution → Resolution phases per turn
- **LLM Agent OODA Loops** — Commanders observe, orient, decide, and act using OpenAI-compatible LLMs with rolling memory
- **Player Command Modes** — Strategic (mission orders), Tactical (direct control), or Hybrid (both)
- **Configurable Fog of War** — Full, Soft, or Omniscient intel with confidence-based degradation
- **AI Difficulty Tiers** — Easy (rule-based), Medium (LLM balanced), Hard (LLM aggressive doctrine)
- **Combat Resolution** — CRT-based with terrain, supply, morale, and CAS modifiers
- **Narrative Engine** — LLM-generated battle reports, intercepted enemy comms, and staff briefings with commander personalities
- **Supply & Air Operations** — Supply chain simulation and Close Air Support missions
- **Relationship Graph** — NetworkX-backed command/supply chain with real-time adjacency
- **Batch Analysis** — Parameter sweeps across scenarios with statistical output
- **Extensible Domains** — Protocol-based engine supports military and business simulations via DomainRegistry

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Pinia)                               │
│  Game View │ Observer View │ Setup │ Batch Analysis      │
└──────────────────────┬──────────────────────────────────┘
                       │ /api/
┌──────────────────────┴──────────────────────────────────┐
│  Flask Backend                                          │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Turn Manager │  │ Human        │  │ Adjudicator   │  │
│  │ (WEGO Loop)  │  │ Commander    │  │ + Dialogue    │  │
│  └──────┬───────┘  └──────────────┘  └───────────────┘  │
│         │                                               │
│  ┌──────┴────────────────────────────────────────────┐  │
│  │ Agents (LLM + Fallback)                           │  │
│  │  Theater Cmd ──→ Division Cmd ──→ Battalion Cmd   │  │
│  │  OrderDirectives    Orders      MilitaryActions    │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌────────┐ ┌────────┐ ┌───────┐ ┌───────┐ ┌────────┐  │
│  │Movement│ │Combat  │ │Intel  │ │Supply │ │  Air   │  │
│  │Engine  │ │Resolver│ │Engine │ │Engine │ │Engine  │  │
│  └────────┘ └────────┘ └───────┘ └───────┘ └────────┘  │
│                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ Constraint       │  │ Relationship Graph (NetworkX)│  │
│  │ Engine           │  │ Command + Supply chains      │  │
│  └─────────────────┘  └──────────────────────────────┘  │
│                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ Replay Store    │  │ Rolling Memory (per agent)   │  │
│  │ (SQLite)        │  │                              │  │
│  └─────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Turn Flow (WEGO)

```
 COMMAND PHASE              EXECUTION PHASE         RESOLUTION PHASE
 ┌───────────┐              ┌──────────────┐        ┌──────────────┐
 │ Theater   │──orders──→   │              │        │              │
 │ Commanders│              │  Movement    │        │   Combat     │
 ├───────────┤              │  Engine      │        │   Resolver   │
 │ Division  │──orders──→   │  (WEGO       │        │   (CRT +     │
 │ Commanders│              │   2-pass)    │        │    modifiers)│
 ├───────────┤              │              │        │              │
 │ Battalion │──actions──→  │              │──→     │              │──→ Turn Result
 │ Commanders│              └──────────────┘        └──────────────┘
 └───────────┘                                             │
       ↑                                            Narrative Gen
  Player input                                     + Dialogue Gen
  (if player mode)
```

## Quick Start

### Without Docker

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install .
python run.py                    # http://localhost:5001

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Open http://localhost:5173 and start a new game.

### With Docker

```bash
cp .env.example .env
# Optionally configure LLM_API_KEY or SGLANG_BASE_URL in .env
docker compose up --build
```

Open http://localhost:8080.

> The game works without any LLM configured — agents fall back to rule-based AI. Set `SGLANG_BASE_URL` for a local LLM server or `LLM_API_KEY` for a cloud provider to enable LLM-powered commanders and narrative generation.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | *(empty)* | API key for OpenAI-compatible LLM provider |
| `LLM_BASE_URL` | `dashscope-intl...` | LLM API endpoint |
| `LLM_MODEL_NAME` | `qwen-plus` | Model identifier |
| `SGLANG_BASE_URL` | *(empty)* | Local sGLang/vLLM server URL (takes priority) |
| `SGLANG_MODEL_NAME` | *(empty)* | Model name for local server |
| `DB_PATH` | `data/wargame.db` | SQLite replay store path |
| `LOG_DIR` | `data/logs` | JSONL turn log directory |
| `TURN_TIMEOUT_SEC` | `30` | Agent decision timeout |

## Project Structure

```
strategos/
├── backend/
│   ├── app/
│   │   ├── agents/          # LLM commander agents (Theater, Division, Battalion)
│   │   ├── api/             # Flask REST endpoints
│   │   ├── core/            # Domain-agnostic protocols and turn loop
│   │   ├── engine/          # Game engine (movement, combat, intel, supply, air)
│   │   ├── graph/           # NetworkX relationship graph
│   │   ├── memory/          # Rolling memory + SQLite replay store
│   │   ├── models/          # Pydantic domain models (frozen, immutable)
│   │   ├── narrative/       # Commander personalities + dialogue generation
│   │   └── utils/           # Hex grid math (axial coords, BFS, A*)
│   ├── tests/               # 999+ tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/             # Axios API client
│   │   ├── components/      # Vue components (Map, Units, Panels, Overlays)
│   │   ├── store/           # Pinia state management
│   │   └── views/           # Game, Observer, Setup, Home views
│   └── package.json
├── scripts/seed_scenarios/   # Scenario JSON definitions
├── docker-compose.yml
├── Dockerfile
└── nginx.conf
```

## Tech Stack

**Backend**: Python 3.11+ · Flask · Pydantic · NetworkX · SQLite · OpenAI SDK · Gunicorn

**Frontend**: Vue 3 · Pinia · Vite · Axios

## License

[MIT](LICENSE)
