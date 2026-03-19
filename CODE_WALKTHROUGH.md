# Code Walkthrough Plan (4 People)

Goal: onboard a team of 4 people who are not familiar with the codebase. Each person should be able to explain how the system works end-to-end within their assigned scope.

## Architecture Overview

```
Frontend (Next.js 15 / React)       :3000
  ├─ /login          — Auth UI
  ├─ /                — Home (notebook list)
  ├─ /notebooks/[id] — Notebook detail + chat
  ├─ /sources/[id]   — Source detail + chat
  ├─ /podcasts       — Podcast generation
  ├─ /search         — Semantic search
  ├─ /settings       — AI provider config
  └─ /api/chat/*     — SSE proxy routes
        │
        │  HTTP (JWT Bearer)
        ▼
API (FastAPI / Uvicorn)              :5056 (or :5055)
  ├─ api/routers/     — REST endpoints
  ├─ api/*_service.py — Business logic
  ├─ core/graphs/     — LLM chat pipelines
  ├─ core/ai/         — Model provisioning
  └─ core/domain/     — ORM-like models
        │
        │  WebSocket (SurrealQL)
        ▼
SurrealDB                            :8000
  └─ rocksdb://surreal_data/mydb.db
```

## Roles & Coverage

---

### Person 1: Frontend UI + State + Routing

What they explain:
- Next.js app structure: layout, pages, API routes.
- Zustand auth state management and JWT token flow.
- Page-level logic: login/register, home (notebook CRUD), notebook detail (tabs: chat/notes/sources), source detail.
- Settings page: AI provider/model configuration saved to backend.
- Search page: semantic search across all content.
- How `logo.png` is used as favicon and in headers.

Key code files:
- `frontend/src/app/layout.tsx`
  - Root layout, Inter font, metadata (title "DocChat", favicon `/logo.png`).
- `frontend/src/app/login/page.tsx`
  - Login / register toggle, JWT token storage, redirect to home.
  - `Image` component renders `/logo.png` for branding (desktop + mobile).
- `frontend/src/app/page.tsx`
  - Home page: notebook list, "Create Notebook" modal, navigation to search/podcasts/settings.
  - Header with `logo.png`, logout button.
- `frontend/src/app/notebooks/[id]/page.tsx`
  - Notebook detail: 3-column layout with sources, chat (session dropdown + streaming), notes.
  - Source upload (file/URL), note CRUD, source guide preview.
- `frontend/src/app/sources/[id]/page.tsx`
  - Source detail: left panel (source guide markdown), right panel (source-scoped chat).
- `frontend/src/app/search/page.tsx`
  - Semantic search input, results list with source/note links.
- `frontend/src/app/settings/page.tsx`
  - AI config form: default provider, model, API keys (Google/OpenAI).
  - Reads from / writes to `GET/PUT /api/config`.
- `frontend/src/lib/store.ts`
  - Zustand store: `useAuthStore` with `user`, `token`, `loading`, `setAuth`, `logout`, `checkAuth`.
- `frontend/src/lib/api.ts`
  - Axios instance (`baseURL: "/api"`), request interceptor adds `Authorization: Bearer`.
  - Response interceptor: 401 → clear token → redirect `/login`.
  - All API wrappers: `authAPI`, `notebooksAPI`, `sourcesAPI`, `notesAPI`, `chatAPI`, `sessionsAPI`, `searchAPI`, `podcastsAPI`, `configAPI`.
- `frontend/next.config.ts`
  - `rewrites`: proxies `/api/*` to backend (`API_PORT` env var, default 5055).
  - `devIndicators: false` disables the Next.js dev overlay.

Comment expectations:
- How `checkAuth()` on page load determines logged-in state.
- Where the rewrite proxy maps frontend `/api/*` to the backend.

Suggested mini-demo:
- Register a new account, observe redirect to home.
- Create a notebook, navigate into it, verify tabs.
- Open Settings, change default model, confirm save.

---

### Person 2: Streaming Chat + Citations + RAG Pipeline

What they explain:
- Frontend SSE consumption: how streamed chunks build the chat message in real time.
- Citation rendering: `[N]` markers → clickable popovers with source content.
- Backend streaming endpoints: how references are emitted first, then content chunks, then `[DONE]`.
- Chat service: notebook context building, semantic search for RAG, message history.
- The LLM invocation pipeline (`core/graphs/chat.py`).

Key code files:
- `frontend/src/app/api/chat/stream/route.ts`
  - Next.js API route: forwards `POST` to backend `POST /api/chat/stream`, pipes SSE back.
  - `API_BASE` env var for upstream URL.
- `frontend/src/app/api/chat/source-stream/route.ts`
  - Same pattern for source-scoped chat → `POST /api/chat/source/stream`.
- `frontend/src/components/MarkdownWithCitations.tsx`
  - Parses rendered markdown text, finds `[N]` patterns, injects `CitationPopover` inline.
- `frontend/src/components/CitationPopover.tsx`
  - Hover/click button → floating popover rendering source chunk as Markdown.
- `frontend/src/components/ThinkingIndicator.tsx`
  - Animated "model is thinking…" shown while waiting for first chunk.
- `frontend/src/components/Markdown.tsx`
  - `ReactMarkdown` wrapper with `remark-gfm`, code highlighting.
- `api/routers/chat.py`
  - `POST /api/chat/stream`: loads notebook context + session history → `run_chat_stream()` → yields SSE.
  - `POST /api/chat/source/stream`: loads single source → `run_chat_stream()` → yields SSE.
  - References emitted as `data: {"references": [...]}` before content chunks.
  - Messages auto-saved to `ChatMessage` when `session_id` is provided.
- `api/chat_service.py`
  - `search_relevant_chunks()`: generates query embedding → vector search in SurrealDB → returns ranked chunks.
  - `build_notebook_context()`: aggregates source content for a notebook.
  - `build_source_context()`: single source content extraction.
- `core/graphs/chat.py`
  - `run_chat()` / `run_chat_stream()`: builds LangChain message list (system + history + human), invokes LLM.
  - `provision_chat_model()` selects provider/model per user config or env defaults.

Comment expectations:
- The SSE payload sequence: `{references}` → `{content: chunk}` × N → `[DONE]`.
- How `session_id` presence triggers history loading and message saving.
- Where citation indices in `[1]`, `[2]` map back to the `references` array positions.

Suggested mini-demo:
- Open a notebook with sources, ask a question in chat.
- Watch streamed text appear word-by-word with ThinkingIndicator.
- Click a `[1]` citation to see the source chunk in a popover.

---

### Person 3: Data Layer + Domain Models + Migrations + Podcast Subsystem

What they explain:
- SurrealDB connection pool and query wrapper.
- Domain model base class (`ObjectModel`) and entity CRUD pattern.
- Migration system: auto-run on API startup.
- Podcast two-phase workflow: text generation → user review/edit → TTS audio.
- Episode/Speaker Profile management, progress tracking, orphan recovery.

Key code files:
- `core/database/repository.py`
  - `ConnectionPool`: async WebSocket connections to SurrealDB with acquire/release.
  - `repo_query()`: central query helper with retry, `RecordID` → string normalization.
  - `repo_create()`, `repo_upsert()`, `repo_update()`, `repo_delete()`: CRUD wrappers.
  - `ensure_record_id()`: converts `"table:id"` string to proper format.
- `core/database/migrate.py`
  - `MigrationManager`: reads `migrations/*.surql`, compares with stored `db_version`, runs pending ones in order.
- `core/domain/base.py`
  - `ObjectModel`: Pydantic base with `save()`, `get()`, `get_all()`, `delete()`.
  - Auto-sets `created`/`updated` timestamps, `user_id` scoping.
- `core/domain/user.py`
  - `User` model: bcrypt password hashing, `create()`, `get_by_username()`, `verify_password()`.
- `core/domain/notebook.py`
  - `Notebook`, `Source`, `Note` entities.
  - `ChatSession`: `get_by_notebook()`, `get_by_source()`.
  - `ChatMessage`: `get_messages(session_id)` returns ordered history.
- `core/domain/podcast.py`
  - `EpisodeProfile`: `name`, `num_segments` (3-20), `speaker_config`, `default_briefing`.
  - `SpeakerProfile`: `name`, `voice_model`, `speakers[]` with `voice_id`.
  - `PodcastEpisode`: `status`, `progress` (stage/detail/pct), `transcript`, `outline`, `audio_file`.
- `migrations/001_initial.surql` — Core tables: user, notebook, source, note, chunk, embedding.
- `migrations/002_chat_messages.surql` — `chat_session` and `chat_message` tables.
- `migrations/003_user_config.surql` — `user_config` table for AI settings.
- `api/podcast_service.py`
  - `generate_text_task()` (Phase 1): builds LangGraph sub-graph with only outline + transcript nodes → status becomes `review`.
  - `generate_audio_task()` (Phase 2): builds LangGraph sub-graph with TTS + combine nodes → status becomes `completed`.
  - Progress hooks: loguru sink parses podcast-creator log lines, persists progress to DB in real time.
  - `_build_configs()`: converts DB profiles to podcast-creator `configure()` calls, handles `provider:model` voice model format.
  - Length constraint auto-appended to briefing to keep output concise.
- `api/routers/podcasts.py`
  - `GET/POST/PUT/DELETE` for EpisodeProfile and SpeakerProfile.
  - `POST /generate` → `generate_text_task` (Phase 1).
  - `PUT /episodes/{id}/transcript` → save user-edited transcript.
  - `POST /episodes/{id}/generate-audio` → `generate_audio_task` (Phase 2).
  - `GET /episodes/{id}/audio` → `FileResponse` for the generated mp3.
- `frontend/src/app/podcasts/page.tsx`
  - Profiles tab: create + inline edit (pencil icon) for both profile types, voice model dropdown (Google/OpenAI TTS options).
  - Episodes tab: Generate form with Content/Briefing fields, transcript preview (collapsed) and full editor (expanded with add/delete turns), progress bar component, inline `<audio>` player with JWT auth fetch.
  - Auto-polling: `setInterval` every 3s when any episode has `processing`/`pending` status.
- `api/main.py` (lifespan startup)
  - Orphan recovery: episodes with `audio_file` but stuck `processing` → `completed`; without audio → `failed`.

Comment expectations:
- How `RecordID` normalization works and why it's needed.
- Episode status lifecycle: `pending` → `processing` → `review` → (user edits) → `processing` → `completed` | `failed`.
- `TTS_BATCH_SIZE` env var (default 5, set to 2 for Google free tier) controls concurrent TTS requests per batch.

Suggested mini-demo:
- Create a Speaker Profile (Google TTS) and Episode Profile (3 segments).
- Generate an episode → watch progress bar (outline → transcript).
- Edit transcript (modify text, delete a turn, add a turn), Save.
- Click "Generate Audio" → watch TTS progress → play inline.

---

### Person 4: AI Provisioning + Source Processing + Embeddings

What they explain:
- Multi-provider AI model selection (Google, OpenAI) for chat and embeddings.
- Source processing pipeline: upload/URL → content extraction → chunking → embedding → storage.
- Source guide generation (summary + keywords via LLM).
- Config system: user-level AI settings stored in `user_config` table.

Key code files:
- `core/ai/provision.py`
  - `provision_chat_model()`: reads `DEFAULT_AI_PROVIDER` / `DEFAULT_AI_MODEL` from env, supports per-request override.
  - `provision_embedding_model()`: selects embedding model by provider.
  - Provider mapping: `google` → Gemini, `openai` → GPT.
- `api/sources_service.py`
  - `process_source()` flow: extract content (file/URL) → generate source guide → chunk text → generate embeddings → store chunks with vectors.
  - `generate_source_guide()`: LLM prompt that returns `SUMMARY:` and `KEYWORDS:` sections, parsed and saved to source record.
- `core/utils/chunking.py`
  - Text splitting strategy: chunk size, overlap configuration.
  - Returns list of text chunks for embedding.
- `core/utils/embedding.py`
  - `generate_embedding()`: calls embedding model, returns vector.
  - Batch processing for multiple chunks.
- `api/routers/config.py`
  - `GET /api/config` → returns user's AI settings + env-level API key availability.
  - `PUT /api/config` → upserts `user_config` record with provider/model/keys.
  - `GET /api/config/providers` → lists available providers with their models.
- `api/routers/sources.py`
  - `POST /api/sources/upload` → file upload.
  - `POST /api/sources/url` → URL-based source creation.
  - `POST /api/sources/{id}/process` → triggers `process_source()` in background.
  - `POST /api/sources/{id}/generate-guide` → triggers `generate_source_guide()` in background.
- `api/auth.py`
  - JWT token creation (`create_access_token`) and decoding (`decode_access_token`).
  - Config: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` from env.
- `api/deps.py`
  - `get_current_user()`: FastAPI dependency that extracts JWT → loads `User` → returns or 401.
- `api/routers/auth.py`
  - `POST /auth/register` and `POST /auth/login` → returns `access_token`.
  - `GET /auth/me` → returns current user info.

Comment expectations:
- How user-level AI config (from Settings page) overrides env-level defaults.
- Where vector similarity search happens in SurrealDB and how results become RAG context.
- The source processing async flow: why it runs in `BackgroundTasks`.

Suggested mini-demo:
- Open Settings, configure Google as default provider.
- Upload a PDF source into a notebook, watch processing status.
- Verify the source guide (summary + keywords) appears.
- Run a search query, confirm relevant chunks are returned.

---

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SURREAL_URL` | `ws://localhost:8000/rpc` | SurrealDB connection |
| `SURREAL_USER` / `SURREAL_PASSWORD` | `root` / `root` | DB credentials |
| `SURREAL_NAMESPACE` / `SURREAL_DATABASE` | `my_notebook` | DB namespace/database |
| `JWT_SECRET_KEY` | `change-me-in-production` | JWT signing secret |
| `GOOGLE_API_KEY` | — | Google AI (Gemini) API key |
| `OPENAI_API_KEY` | — | OpenAI API key (optional) |
| `DEFAULT_AI_PROVIDER` | `google` | Default LLM provider |
| `DEFAULT_AI_MODEL` | `gemini-2.5-flash` | Default LLM model |
| `API_PORT` | `5055` | API server port |
| `TTS_BATCH_SIZE` | `5` | Concurrent TTS clips per batch |
| `UVICORN_RELOAD` | `false` | Enable hot-reload (dev only) |

## Startup Sequence

1. `run_api.py` → Uvicorn starts FastAPI app (single process by default).
2. `api/main.py` lifespan:
   - Connect to SurrealDB.
   - Run pending migrations from `migrations/`.
   - Recover orphaned `processing` episodes.
3. Frontend: `npm run dev` → Next.js on :3000, proxies `/api/*` to backend.

## Handoff Checklist

Each person should deliver:
1. A 10-15 minute walkthrough of their section.
2. A 1-page cheat sheet summarizing "entry point → key functions → output shape".
3. Code comments added/verified in the files listed above, so a new developer can follow the flow without reverse-engineering.
