# Context Distiller UI

Clean, flat frontend console for testing and managing all Context Distiller capabilities.

## Features

| Tab | Function | Backend Endpoints |
|-----|----------|-------------------|
| **Distill** | Text/URL/file/data-URI compression | `POST /v1/distill`, `POST /v1/upload` |
| **Memory** | CRUD + search + list (with category, user/agent isolation) | `POST /v1/memory/{search,store,update,forget,get,list}` |
| **Session** | Conversation summary & context compact | `POST /v1/session/{summary,compact}` |
| **Proxy** | Chat completions transparent proxy test | `POST /v1/chat/completions` |
| **Config** | View runtime configuration (default.yaml) | `GET /v1/config` |

## Quick Start

### 1. Start Backend

```bash
cd <repo_root>
python -c "from context_distiller.api.server.app import start_server; start_server()"
```

The API server starts at `http://localhost:8080` with CORS enabled.

### 2. Start Frontend

```bash
cd context_distiller_ui
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 3. Verify

1. Click **Health** button in the top bar -- should return `{"status":"ok","version":"2.0.0"}`
2. Go to **Distill** tab, paste text, click **Distill** -- see compression stats in the response panel
3. Go to **Memory** tab, fill content and source, click **Store** -- see `chunk_id` in response
4. Click **List All** -- see the stored memory entry
5. Change `agent_id` in the scope bar, click **List All** again -- the memory is invisible (agent isolation works)
6. Go to **Config** tab, click **Load** -- see the full `default.yaml` configuration
