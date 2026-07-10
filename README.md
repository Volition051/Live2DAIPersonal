<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)">
    <img width="520" alt="景区导览服务AI数字人" src="https://img.shields.io/badge/景区导览服务-AI数字人-667eea?style=for-the-badge&logo=robot&logoColor=white">
  </picture>
</p>

<p align="center">
  <b>Scenic Area RAG Intelligent Q&A System with Live2D Digital Human</b>
  <br>
  <sub>灵山胜境 · 拈花湾 — 24/7 AI 导游，沉浸式智能导览体验</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue">
  <img src="https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/PostgreSQL-14+-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Electron-42-47848F?logo=electron&logoColor=white" alt="Electron">
  <img src="https://img.shields.io/badge/Live2D-Cubism_4-EC407A" alt="Live2D">
  <img src="https://img.shields.io/badge/License-Proprietary-red" alt="License">
</p>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Screenshots](#-screenshots)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Deployment](#-deployment)
- [API Reference](#-api-reference)
- [Skill System](#-skill-system)
- [Database Schema](#-database-schema)
- [Troubleshooting](#-troubleshooting)
- [Documentation](#-documentation)

---

## 🌄 Overview

**景区导览服务AI数字人** is a multi-terminal, AI-powered scenic area guide system built for **灵山胜境 (Lingshan Grand Buddha Scenic Area)** and **拈花湾 (Nianhua Bay Zen Town)** in Wuxi, China. It combines **RAG** (Retrieval-Augmented Generation), **LLM Agents**, **GPS geo-awareness**, **Live2D digital humans**, and **TTS speech synthesis** into a single cohesive platform.

### Who is this for?

| Audience | Product | Experience |
|----------|---------|-------------|
| 🧳 **Tourists** | Touch-screen kiosk / Mobile web app | Talk to a Live2D AI guide about attractions, get route planning, watch introduction videos |
| 🏢 **Park managers** | Web admin dashboard | Upload knowledge docs, view visitor analytics, manage POI data, customize UI appearance |

---

## 📸 Screenshots

<div align="center">

| Desktop (Kiosk) | Mobile | Admin Dashboard |
|:---:|:---:|:---:|
| *Touch-screen terminal with Live2D digital human, chat panel, and Leaflet map* | *Phone-optimized with 4-tab navigation (Guide / Map / Discover / Profile)* | *ECharts-powered analytics, knowledge base management, system config* |

</div>

---

## ✨ Features

### 🤖 AI Smart Guide

- **Dual-mode Q&A**: `normal` (lightweight RAG, fast) and `agent` (full toolchain with skills)
- **10 built-in skills**: route planning, multi-point TSP optimization, personalized recommendations, weather queries, knowledge Q&A, casual chat, visitor statistics, KB management, system health check, project explorer
- **Plan-Execute + ReAct hybrid engine**: structured multi-step plans for complex tasks, graceful fallback to ReAct for open-ended queries
- **Auto attraction intro**: GPS geo-fence triggers automatic AI-generated attraction introductions with video playback
- **Real-time thought streaming**: users see the AI's reasoning process as it happens (polling endpoint)

### 🗺️ Intelligent Map

- **pgRouting-powered pathfinding**: shortest-path routing between any POIs with distance and walking time
- **TSP optimization**: optimal visit order for multi-point tours (up to 8 points, exhaustive permutation)
- **Interactive Leaflet map**: POI markers, route overlays, touch gestures (pinch-zoom, pan)
- **OSM data**: `lingshan.osm` contains the full scenic area road network

### 👩‍💼 Live2D Digital Human

- **Cubism SDK 4**: model loading, expression switching, motion playback
- **Viseme lip-sync**: Edge-TTS audio → pypinyin phoneme mapping → 8 viseme types → real-time mouth animation
- **8 action markers**: nod, wave, invite, reject, think, explain, celebrate, sad — AI decides when to use each
- **Model hot-swap**: upload and switch models from the admin panel, applies to all terminals instantly

### 📍 GPS Geo-Awareness

- **Real-time GPS upload**: continuous position tracking every 3 seconds
- **Geo-fence detection**: automatic scenic area boundary detection (configurable lat/lng)
- **Multi-source priority**: user simulation > test config > real GPS > request payload
- **Auto visit tracking**: enter → create record → switch attraction → close record → calculate stay duration

### 🎤 TTS Voice Synthesis

- **Edge-TTS engine**: high-quality Chinese speech, multiple voice personas
- **Adjustable parameters**: voice, rate, volume, pitch — configurable from admin panel
- **Viseme output**: returns viseme sequence + subtitle timeline for Live2D lip-sync
- **Subtitle data**: character-level timing for sentence and word-level highlighting in UI

### 📊 Data Analytics Dashboard

- **Real-time KPIs**: total visitors, today's visitors, satisfaction rates, popular questions
- **Multi-dimensional stats**: gender distribution, age brackets, satisfaction intervals, spending breakdown
- **Sentiment report**: AI-powered analysis of visitor conversations — positive/negative/neutral distribution
- **ECharts 6 visualization**: interactive charts with dark mode support

### 📚 Knowledge Base Management

- **5 document formats**: PDF, Word (.docx), Excel (.xlsx), TXT, Markdown
- **Semantic chunking**: heading detection, paragraph merging, sentence splitting with overlap
- **Metadata enrichment**: 8 fields auto-detected (scenic area, category, attractions, quality score, etc.)
- **Hybrid retrieval**: vector (ChromaDB) + BM25 keyword search with query expansion and TTL caching
- **Quality scoring**: 4-dimension filter (length, density, entity count, sentence completeness)

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Client Layer                           │
│  ┌──────────────────┐       ┌────────────────────────┐   │
│  │   Tourist App     │       │     Admin Panel         │   │
│  │  Vue 3 + Vite     │       │   Vue 3 + Element Plus  │   │
│  │  Live2D + Leaflet │       │   ECharts 6 + Router    │   │
│  │  + Vant (mobile)  │       │                          │   │
│  │  + Electron (kiosk)│       │                          │   │
│  └────────┬─────────┘       └───────────┬──────────────┘   │
└───────────┼─────────────────────────────┼──────────────────┘
            │       HTTP REST + WebSocket  │
┌───────────┴─────────────────────────────┴──────────────────┐
│                    Server Layer                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              FastAPI (Python 3.10+)                    │  │
│  │  ┌──────────────┐ ┌───────────┐ ┌──────────────────┐ │  │
│  │  │  Admin Router │ │ Tourist   │ │  Map Router      │ │  │
│  │  │  (/admin)     │ │ (/tourist)│ │  (/map)          │ │  │
│  │  └──────────────┘ └───────────┘ └──────────────────┘ │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │            AI Agent Engine                        │ │  │
│  │  │  ┌────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │ │  │
│  │  │  │ Skill   │ │  Context  │ │  Memory  │ │ Tool  │ │ │  │
│  │  │  │ System  │ │  Builder  │ │  Manager │ │System │ │ │  │
│  │  │  │(10 skills)│ │          │ │(compress)│ │(20+   │ │ │  │
│  │  │  └────────┘ └──────────┘ └──────────┘ │ tools) │ │ │  │
│  │  └────────────────────────────────────────└───────┘ │ │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │            RAG Engine                             │ │  │
│  │  │  ┌────────────────┐  ┌─────────────────────────┐ │ │  │
│  │  │  │ Vector Search   │  │  BM25 Keyword Search    │ │ │  │
│  │  │  │ (ChromaDB)      │  │  (jieba tokenizer)     │ │ │  │
│  │  │  └────────────────┘  └─────────────────────────┘ │ │  │
│  │  │       Query Expansion + Merge + Rerank            │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │            TTS Engine (Edge-TTS)                   │ │  │
│  │  │  Text → Pinyin → Viseme Mapping → Lip Sync        │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │
│  │ PostgreSQL│  │ ChromaDB │  │   LLM API                │ │
│  │ + PostGIS │  │ Vector DB│  │   DeepSeek / DashScope   │ │
│  │ +pgRouting│  │          │  │   (OpenAI-compatible)     │ │
│  └──────────┘  └──────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Question
  → Skill Matching (keyword + fuzzy matching)
  → Context Builder (compressed history + RAG retrieval + memory summary)
  → Plan-Execute (structured multi-step) or ReAct (Thought/Action/Observation loop)
  → Tool Calls (RAG search, route planning, weather, stats, etc.)
  → LLM Generation (DeepSeek / DashScope via OpenAI-compatible API)
  → Post-processing (punctuation cleaning, action marker injection)
  → TTS Synthesis (Edge-TTS + viseme + subtitle timeline)
  → Response (text + audio + viseme data)
```

---

## 🛠 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend Framework** | FastAPI + Uvicorn | 0.115 / 0.32 |
| **Frontend (Tourist)** | Vue 3 + Vite + Vant 4 | 3.5 / 8 / 4.9 |
| **Frontend (Admin)** | Vue 3 + Element Plus + ECharts 6 | 3.5 / 2.13 / 6.0 |
| **Desktop Shell** | Electron + electron-builder | 42 / 26 |
| **Database** | PostgreSQL + PostGIS + pgRouting | 14+ |
| **Vector Database** | ChromaDB | 0.5 |
| **Embedding Model** | sentence-transformers (BAAI/bge-small-zh-v1.5) | 3.2 |
| **LLM Providers** | DeepSeek (deepseek-chat) / DashScope (qwen3.6-flash) | — |
| **TTS Engine** | edge-tts | 7.2 |
| **Map Rendering** | Leaflet | 1.9 |
| **Live2D SDK** | Cubism SDK 4 + pixi-live2d-display | 0.4 |
| **Auth** | JWT (python-jose) + bcrypt (passlib) | HS256 |
| **Document Parsing** | PyPDF2, python-docx, openpyxl, lxml | — |
| **Async** | asyncio, httpx, aiohttp | — |

---

## 📁 Project Structure

```
project_root/
├── backend/                         # Python FastAPI backend
│   ├── app/
│   │   ├── main.py                  # Entry point, middleware, startup events
│   │   ├── config.py                # pydantic-settings (env-based)
│   │   ├── database.py              # SQLAlchemy engine + session factory
│   │   ├── models.py                # ORM models (9 tables)
│   │   ├── schemas.py               # Pydantic request/response models
│   │   ├── routers/                 # API routes
│   │   │   ├── admin.py             # Admin endpoints
│   │   │   ├── tourist.py           # Tourist endpoints
│   │   │   └── map.py               # Map/Routing endpoints
│   │   ├── core/                    # AI engine
│   │   │   ├── base_agent.py        # Unified Plan-Execute + ReAct engine
│   │   │   ├── agent.py             # TouristAgent
│   │   │   ├── admin_agent.py       # AdminAgent
│   │   │   ├── tools.py             # Agent tools (20+)
│   │   │   ├── base_tool.py         # Tool abstraction
│   │   │   ├── memory.py            # Conversation memory + compression
│   │   │   ├── context_builder.py   # LLM context assembly
│   │   │   ├── client.py            # OpenAI-compatible client
│   │   │   └── skills/              # Skill system (4 files, 10 skills)
│   │   ├── services/                # Business services
│   │   │   ├── rag.py               # Hybrid retrieval (vector + BM25)
│   │   │   ├── indexer.py           # Document indexer (semantic chunking)
│   │   │   ├── tts_service.py       # TTS + Viseme lip-sync
│   │   │   └── recommender.py       # Personalized recommendation
│   │   ├── utils/security.py        # JWT + bcrypt
│   │   └── config/poi_data.yaml     # 22 POI definitions
│   ├── static/                      # Static assets (images, tiles, videos)
│   ├── chroma_db/                   # Vector store persistence
│   ├── requirements.txt
│   └── .env
├── frontend-tourist/                # Tourist SPA (Vue 3)
│   ├── src/
│   │   ├── views/                   # Page components
│   │   ├── components/              # Reusable components (Live2DViewers)
│   │   ├── composables/             # Composition functions
│   │   ├── stores/                  # Pinia stores (auth)
│   │   ├── router/                  # Vue Router config
│   │   └── utils/                   # Request, session, mobile helpers
│   ├── public/Resources/            # Live2D Cubism model files
│   ├── electron/                    # Electron main process
│   ├── package.json                 # + electron-builder config
│   └── vite.config.js
├── frontend-admin/                  # Admin SPA (Vue 3)
│   ├── src/views/                   # 17 admin pages
│   ├── package.json
│   └── vite.config.js
├── run.bat                          # One-click launcher (Windows)
├── lingshan.osm                     # Scenic area OSM road network data
└── 产品部署与使用手册.docx           # Deployment & User Manual (Chinese)
```

---

## 🚀 Quick Start

### Prerequisites

- **Python** ≥ 3.10
- **Node.js** ≥ 18 LTS
- **PostgreSQL** ≥ 14 with **PostGIS** and **pgRouting** extensions
- A DeepSeek or Alibaba DashScope **API key**

### 1. Clone & Setup Python

```bash
git clone <repo-url>
cd project_root

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# or
.venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r backend/requirements.txt
```

### 2. Setup Database

```sql
-- Run in psql
CREATE DATABASE my_db;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;
```

### 3. Configure Environment

```bash
# Edit backend/.env — fill in the required fields:
cp backend/.env.example backend/.env   # if template exists
```

Minimal `.env`:

```ini
DATABASE_URL="postgresql://postgres:your_password@localhost:5432/my_db"
SECRET_KEY="$(openssl rand -hex 32)"
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-api-key
```

### 4. Install Frontend Dependencies

```bash
cd frontend-tourist && npm install
cd ../frontend-admin && npm install
cd ..
```

### 5. Launch

**One-click (Windows):**

```batch
run.bat
```

**Manual:**

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Tourist Frontend
cd frontend-tourist
npm run dev

# Terminal 3 — Admin Frontend
cd frontend-admin
npm run dev
```

### 6. Access

| Service | URL | Credentials |
|---------|-----|-------------|
| 🧳 Tourist App | `http://localhost:3001` | Register or Login |
| 📊 Admin Panel | `http://localhost:3000` | `admin` / `admin123` |
| 📖 API Docs (Swagger) | `http://localhost:8000/docs` | — |

> ⚠️ **Change the default admin password immediately after first login.**

---

## ⚙️ Configuration

All backend configuration is managed via `backend/.env`:

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (use `openssl rand -hex 32`) |
| `LLM_PROVIDER` | `deepseek` or `dashscope` |
| `DEEPSEEK_API_KEY` | DeepSeek API key (if using DeepSeek) |
| `DASHSCOPE_API_KEY` | Alibaba DashScope API key (if using DashScope) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MAX_ITERATIONS` | `500` | Max ReAct iterations per query |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | JWT token lifetime |
| `GPS_SIMULATION_ENABLED` | `False` | Auto-roam simulation |
| `GPS_SIMULATION_INTERVAL_SEC` | `3.0` | Position update interval |
| `SCENIC_LON_MIN` / `MAX` | `120.0950` / `120.1060` | Geo-fence longitude bounds |
| `SCENIC_LAT_MIN` / `MAX` | `31.4200` / `31.4317` | Geo-fence latitude bounds |
| `CHROMA_PATH` | `./chroma_db` | Vector DB storage path |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | Sentence embedding model |

See `backend/app/config.py` for the complete list.

### Frontend Environment Variables

| File | Variable | Value |
|------|----------|-------|
| `frontend-tourist/.env.development` | `VITE_API_BASE_URL` | `/api` (proxied) |
| `frontend-tourist/.env.production` | `VITE_API_BASE_URL` | `http://127.0.0.1:8000` |
| `frontend-admin/.env.development` | `VITE_API_BASE_URL` | `/` (proxied) |

---

## 🚢 Deployment

### Development

```bash
# Backend with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend dev servers
cd frontend-tourist && npm run dev    # :3001
cd frontend-admin && npm run dev      # :3000
```

### Production

```bash
# Backend with Gunicorn
cd backend
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 --timeout 300

# Build static frontends
cd frontend-tourist && npm run build   # → backend/web/
cd frontend-admin && npm run build     # → backend/web-admin/
```

### Electron Desktop App (Windows)

```bash
cd frontend-tourist
npm run electron:build:win
# Output: release/景区智能导览终端 Setup x64.exe
```

| Config | Value |
|--------|-------|
| App ID | `com.scenicspot.terminal` |
| Installer | NSIS (per-machine, desktop shortcut) |
| Architecture | Windows x64 |

### Service Daemonization

**Windows (NSSM):**
```bash
nssm install ScenicAI ".venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
nssm set ScenicAI AppDirectory "C:\project_root\backend"
nssm start ScenicAI
```

**Linux (systemd):**
```ini
# /etc/systemd/system/scenic-ai.service
[Unit]
Description=Scenic AI Guide
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory=/opt/project_root/backend
Environment=PATH=/opt/project_root/.venv/bin
ExecStart=/opt/project_root/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
TimeoutSec=300

[Install]
WantedBy=multi-user.target
```

---

## 📡 API Reference

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/tourist/register` | — | Register tourist account |
| `POST` | `/tourist/login` | — | Login, returns JWT + user_info |
| `POST` | `/admin/login` | — | Admin login |

### Tourist APIs

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tourist/text-chat` | AI Q&A (supports `normal` and `agent` modes) |
| `GET` | `/tourist/streaming-thoughts/{user_id}` | Real-time AI thought stream (poll) |
| `POST` | `/tourist/gps` | Upload GPS coordinates (auto match attraction) |
| `POST` | `/tourist/attraction-auto-intro` | AI-generated attraction introduction |
| `POST` | `/tourist/text-to-speech` | TTS (returns MP3 stream) |
| `POST` | `/tourist/text-to-speech-with-visemes` | TTS + Viseme data + subtitle timeline |
| `GET` | `/tourist/visits` | Get visit records |
| `GET` | `/tourist/conversations` | Get conversation history (paginated) |
| `PUT` | `/tourist/profile` | Update username |
| `GET` | `/tourist/live2d/current-model` | Get current Live2D model config |
| `GET` | `/tourist/appearance` | Get UI appearance settings |

### Admin APIs

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/chat` | Admin AI Q&A |
| `GET` | `/admin/dashboard` | Dashboard analytics data |
| `GET` | `/admin/knowledge-docs` | List knowledge documents |
| `POST` | `/admin/upload-doc` | Upload document (PDF/Word/Excel/TXT/MD) |
| `DELETE` | `/admin/delete-doc/{id}` | Delete document |
| `GET`/`POST`/`PUT` | `/admin/attractions` | CRUD attraction POIs |
| `GET` | `/admin/visitor-stats` | Visitor statistics |
| `GET` | `/admin/database/tables` | List database tables |
| `GET` | `/admin/database/{table}` | Browse table data |
| `GET`/`POST`/`PUT` | `/admin/live2d*` | Live2D model management |
| `GET`/`PUT` | `/admin/system-configs` | System configuration |

Full Swagger docs available at `http://localhost:8000/docs`.

---

## 🎯 Skill System

The AI agent uses a **Skill-based Plan-Execute** engine. When a user asks a question, the system matches it to one of 10 predefined skills, then executes a structured plan.

### Tourist Skills (6)

| Skill | Triggers | Steps | Purpose |
|-------|----------|-------|---------|
| `route_planning` | 怎么走, 路线, 导航 | 3 | Single-point route planning |
| `personalized_recommendation` | 推荐, 有什么好玩, 一日游 | 3 | Smart attraction recommendations |
| `multi_route_planning` | 游览顺序, 怎么逛, 先去 | 4 | Multi-point route with TSP optimization |
| `weather_query` | 天气, 温度, 下雨, 带伞 | 2 | Real-time weather |
| `knowledge_qa` | 介绍, 门票, 灵山, 大佛 | 2 | General attraction Q&A |
| `casual_chat` | 你好, 谢谢, 再见 | 0 | Greetings (direct response) |

### Admin Skills (4)

| Skill | Triggers | Steps | Purpose |
|-------|----------|-------|---------|
| `visitor_stats_report` | 统计, 客流, 热门 | 3 | Visitor data analytics |
| `knowledge_base_management` | 知识库, 文档, 向量 | 0 | KB operations |
| `system_health_check` | 健康, 状态, 系统 | 2 | System diagnostics |
| `project_explorer` | 文件, 代码, 目录 | 3 | Project structure explorer |

### Matching Strategy

```
Layer 1: Exact keyword match (zero-cost, trigger words in question)
Layer 2: Fuzzy substring match (3-5 char sliding window, excludes stop words)
Sort: Priority descending → trigger count ascending (more specific wins)
```

---

## 🗃 Database Schema

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `user` | Admin accounts | `username`, `hashed_password`, `is_superadmin` |
| `tourist` | Tourist accounts | `username`, `display_id`, `hashed_password` |
| `tourist_visit` | Visit records | `tourist_id`, `attraction_name`, `visit_date`, `stay_duration`, costs |
| `interaction_log` | Chat history | `tourist_pk`, `question`, `answer`, `created_at` |
| `knowledge_doc` | Knowledge documents | `filename`, `file_size`, `doc_type` |
| `attraction` | POI data | `attraction_id`, `name`, `scenic_area`, coordinates, `video_url` |
| `system_config` | Key-value config store | `config_key`, `config_value`, `updated_at` |
| `task_plan` | Agent task plans | `plan_id`, `title`, `status` |
| `task_step` | Plan steps | `step_id`, `plan_id`, `description`, `status` |

---

## 🔧 Troubleshooting

<details>
<summary><b>Backend fails to start (ModuleNotFoundError)</b></summary>

Activate the virtual environment and reinstall dependencies:
```bash
.venv\Scripts\activate  # Windows
pip install -r backend/requirements.txt
```
</details>

<details>
<summary><b>SECRET_KEY not set</b></summary>

Generate and add to `backend/.env`:
```bash
openssl rand -hex 32
# Copy output to: SECRET_KEY=<output>
```
</details>

<details>
<summary><b>Database connection fails</b></summary>

1. Ensure PostgreSQL service is running
2. Verify `DATABASE_URL` credentials in `.env`
3. Confirm database `my_db` exists
</details>

<details>
<summary><b>LLM API calls timeout or fail</b></summary>

1. Verify `LLM_PROVIDER` and `*_API_KEY` are correct
2. Check server has internet access to API endpoints
3. Consider reducing `AGENT_MAX_ITERATIONS` if responses are too slow
</details>

<details>
<summary><b>Embedding model downloads slowly on first run</b></summary>

The `BAAI/bge-small-zh-v1.5` model is ~400 MB. For users in China, set a mirror:
```bash
export HF_ENDPOINT=https://hf-mirror.com  # macOS/Linux
set HF_ENDPOINT=https://hf-mirror.com     # Windows
```
</details>

<details>
<summary><b>Knowledge base documents not retrievable</b></summary>

1. Verify format is PDF/Word/Excel/TXT/Markdown
2. Ensure content is >100 characters (quality filter threshold: 0.15)
3. Rebuild BM25 index: `POST /admin/rebuild-bm25`
4. Clear retrieval cache: `POST /admin/clear-retrieval-cache`
</details>

<details>
<summary><b>Map not rendering</b></summary>

1. Confirm PostGIS + pgRouting extensions are installed in PostgreSQL
2. Ensure `lingshan.osm` data is loaded into the road network table
3. In dev mode, verify Vite proxies `/tiles` to the backend
</details>

<details>
<summary><b>Live2D digital human not appearing</b></summary>

1. Verify model files exist in `public/Resources/`
2. Confirm Cubism SDK is loaded in `index.html`
3. Check browser console for CORS or loading errors
4. Admin panel → Live2D Management → verify current model path is valid
</details>

<details>
<summary><b>Voice recognition not working</b></summary>

- Requires Chrome or Edge browser
- Ensure microphone permission is granted
- Requires HTTPS (except `localhost`)
</details>

<details>
<summary><b>Electron build fails</b></summary>

1. Ensure `npm run build` succeeds first (generates `dist/`)
2. Verify `public/app-icon.png` exists
3. For slow downloads, set mirror:
   ```bash
   set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
   ```
</details>

---

## 📚 Documentation

- **[产品部署与使用手册.docx](产品部署与使用手册.docx)** — Full deployment and usage guide (Chinese)
- **[backend/CHANGELOG.md](backend/CHANGELOG.md)** — Architecture upgrade changelog (2026-06-06)
- **[POI Data](backend/app/config/poi_data.yaml)** — 22 attraction definitions (Lingshan + Nianhua Bay)
- **Swagger UI** — `http://localhost:8000/docs` (interactive API docs)
- **Swagger JSON** — `http://localhost:8000/openapi.json`

---

<p align="center">
  <sub>Built with ❤️ for 灵山胜境 · 拈花湾</sub>
  <br>
  <sub>© 2026 Scenic AI Guide Project. All rights reserved.</sub>
</p>
