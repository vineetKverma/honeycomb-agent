# Honeycomb

> Turn YouTube transcripts into a self-linking knowledge graph — powered by Gemini and MongoDB Atlas Vector Search.

## What it does

1. Fetches transcripts from YouTube videos via URL or video ID.
2. Extracts discrete learning concepts (title, summary, tags) using Gemini.
3. Embeds each concept with Gemini's embedding model and stores them in MongoDB Atlas.
4. Links related concepts automatically via Atlas Vector Search, forming a knowledge graph.

## Setup

### Prerequisites

- Python 3.10+
- MongoDB Atlas cluster with Vector Search enabled
- Gemini API key

### Install

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Fill in all values in .env
```

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `MONGODB_URI` | Atlas connection string |
| `MONGODB_DB` | Database name (e.g. `honeycomb`) |
| `MONGODB_COLLECTION` | Collection name (e.g. `concepts`) |
| `VECTOR_INDEX_NAME` | Atlas Search index name (e.g. `concept_vector_index`) |

### Atlas Vector Search Index

Create a vector search index on the collection with the following definition:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 768,
      "similarity": "cosine"
    }
  ]
}
```

## How to run

```bash
# Ingest a single YouTube video
python main.py ingest <youtube_url_or_id>

# Query related concepts
python main.py query "<concept text>"
```

## POC Pass/Fail Criteria

| # | Metric | Pass |
|---|---|---|
| 1 | **Transcript fetch** | Successfully retrieves transcript for any public YouTube video |
| 2 | **Concept extraction** | Gemini returns ≥ 3 structured concepts per ~10 min video |
| 3 | **Storage** | All concepts persisted to MongoDB with embeddings (no write errors) |
| 4 | **Vector linking** | Each concept returns ≥ 2 related concepts via similarity search (cosine score > 0.75) |
| 5 | **End-to-end latency** | Full pipeline (fetch → extract → embed → store → link) completes in < 60 s per video |

## Troubleshooting

### Never drop the collection from the Atlas UI

**Do NOT use the Atlas UI "Drop Collection" action.** Dropping the collection also destroys the associated vector search index, and you'll have to recreate the index by hand before vector search works again.

To clear data safely (documents removed, collection and index preserved):

```bash
python scripts/wipe_concepts.py
```

### Vector search returns zero candidates

If `vector_search` unexpectedly returns no results:

1. Open the Atlas **Search Indexes** tab for the `honeycomb.concepts` collection.
2. Confirm the `concept_vector_index` index exists and is in **Active** status (a freshly created index takes a short while to build).
3. Run the sanity check:

   ```bash
   python scripts/check_vector_search.py
   ```

   It exits `0` if at least one candidate is returned, `1` otherwise.

## Phase A1 — MongoDB MCP Setup

Honeycomb talks to MongoDB through the official [MongoDB MCP server](https://github.com/mongodb-js/mongodb-mcp-server) (`mongodb-mcp-server` on npm), spawned locally as a subprocess over stdio. This is the hackathon's required partner integration.

### Prerequisite: Node.js

The MCP server is a Node.js package run via `npx`. Install **Node.js 18+** and verify:

```bash
node --version
```

### Run the smoke test

```bash
python scripts/test_mongo_mcp.py
```

This spawns the MongoDB MCP server (via `cmd /c npx -y mongodb-mcp-server` on Windows, `npx -y mongodb-mcp-server` on POSIX), performs the MCP `initialize` handshake using `MONGODB_URI` from your `.env`, lists the server's tools, then calls a read-only tool to confirm Atlas connectivity. The subprocess is closed automatically on exit. The first run may take a moment while `npx` downloads the package. The whole test times out after 60 seconds.

**Expected output:**

1. A list of MongoDB MCP tools, including `find`, `aggregate`, `count`, `list-collections`, `list-databases`, `insert-one`, `update-one`, `delete-one`, and others.
2. A successful `list-collections` call against the `honeycomb` database showing `["concepts"]`.

### Configuration

`agent/mcp_config.json` declares the server. Its `MDB_MCP_CONNECTION_STRING` value is a placeholder — at runtime it is replaced with `MONGODB_URI` from `.env`.

### Troubleshooting

- **`npx not found`:** Node.js is not on `PATH`. Reinstall Node.js (the installer adds it to `PATH`) and open a fresh PowerShell session.
- **Hang / timeout (60s):** the `MONGODB_URI` is likely wrong, or your current IP is not on the Atlas **Network Access** allowlist. Verify both, then retry.
- **`ENOENT` or shell errors on Windows:** `npx` is `npx.cmd` and cannot be exec'd directly. The smoke test routes through `cmd /c` on Windows for this reason; if you adapt the spawn code, preserve that.

## Phase A2 — Honeycomb Agent (ADK)

The Honeycomb agent is built on [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/). It plans multi-step learning workflows and calls Honeycomb's pipeline functions as tools.

The agent currently exposes five tools backed by direct Python functions (faster to iterate on): `ingest_learning_source`, `quiz_concept`, `grade_my_answer`, `list_my_concepts`, and `get_concept_details`. (The MongoDB MCP server is wired in separately in Phase A3.)

### Setup

```bash
pip install -r requirements.txt
```

Authentication: the CLI defaults `GOOGLE_API_KEY` to `GEMINI_API_KEY` from your `.env` (AI Studio backend). If you have Vertex AI / Express Mode env vars already set, those are respected and not overwritten.

### Run

```bash
python scripts/run_agent_cli.py
```

This opens a local REPL backed by ADK's `InMemoryRunner`. Type `exit` or press Ctrl+C to quit.

### Try these prompts

- `Ingest https://www.youtube.com/watch?v=aircAruvnKk`
- `What concepts do I know about neural networks?`
- `Quiz me on Backpropagation`

## Phase A3 — MongoDB MCP as an agent tool source

### Architecture: direct Python for writes, MCP for reads

The agent uses a hybrid tool set:

| Path | Mechanism | Tools |
|---|---|---|
| Write / study (performance-critical) | Direct Python functions | `ingest_learning_source`, `quiz_concept`, `grade_my_answer` |
| Graph queries (demo-visible) | **MongoDB MCP server** (read-only) | `find`, `aggregate`, `count`, `list-collections` |

The MCP server is launched read-only (`--readOnly`), and the toolset is further restricted via `tool_filter` to those four query tools — writes never go through MCP. This satisfies the hackathon's MongoDB MCP partner-integration requirement: the agent demonstrably calls MongoDB MCP tools to answer the user's questions.

`list_my_concepts` and `get_concept_details` from Phase A2 were **dropped** from the agent — those reads are now served by MCP `find`/`aggregate`. (The functions still exist in `agent/tools.py` but are no longer registered.)

### Run the MCP integration test

```bash
python scripts/test_agent_with_mcp.py
```

This auto-runs two scripted queries and prints the agent's responses plus the tool calls it made.

**Example run (tool calls are visible):**

```
you> How many concepts do I have in my knowledge graph?
  [tool call] count({'database': 'honeycomb', 'collection': 'concepts', 'query': {}})
  [tool done] count
honeycomb> You have 23 concepts in your knowledge graph.

you> Show me 3 concepts about philosophy.
  [tool call] find({'database': 'honeycomb', 'collection': 'concepts', 'filter': {...}, 'limit': 3})
  [tool done] find
honeycomb> Here are 3 concepts related to philosophy: ...
```

### Notes

- **Cleanup:** the `MCPToolset` owns a subprocess and stdio session. Both `run_agent_cli.py` and `test_agent_with_mcp.py` call `await mongo_mcp_toolset.close()` in a `finally` block on exit.
- **Windows:** the MCP server is spawned via `cmd /c mongodb-mcp-server --readOnly` (the binary is a `.cmd` shim); POSIX execs it directly.

## Phase A4 — Mastery tracking & spaced-repetition review

### Model: an event log, not an aggregate

Mastery is **derived**, never stored as a mutable number. Every quiz attempt appends one immutable document to the `mastery_events` collection:

```
{ concept_id, concept_name, score (0-5), user_answer_excerpt, missed_points, timestamp }
```

`mastery.compute_mastery(concept_id)` reads a concept's events and derives its current state on demand (attempts, latest score, rolling average of the last 5 attempts, days since last review, level, and whether it is due). Because it is an append-only log, history is preserved and the scoring rules can change without a migration. The collection has only ordinary indexes (a unique index on `(concept_id, timestamp)`) — no vector index.

### Mastery levels

Derived from the rolling average of the last 5 scores:

| Level | Rule |
|---|---|
| `untested` | no events recorded |
| `weak` | rolling avg < 2.5 |
| `developing` | 2.5 <= rolling avg < 4.0 |
| `solid` | rolling avg >= 4.0 |

### How `daily_review` prioritizes

`mastery.get_review_candidates(limit=5)` returns only concepts that are **due**, where due means:

- `untested` (never quizzed) — always due, or
- `weak` / `developing` and last reviewed >= 1 day ago, or
- `solid` and last reviewed >= 7 days ago.

Due concepts are ordered by priority tier: **weak → developing → untested → solid**, and within a tier the most overdue comes first. The agent calls `record_quiz_attempt` after every grade (so the log stays current) and `daily_review` when you ask what to study.

### Test (uses zero Gemini quota)

```bash
python scripts/test_mastery.py
```

Pure Python — no model calls. It seeds backdated events on existing concepts (Neural Network → weak, Backpropagation or Sigmoid Function → solid, Derivative → weak), then asserts the level classification and that review candidates are priority-sorted (weak before solid) and all flagged due.

## Phase A5 — Streamlit UI

A 4-page Streamlit app over the existing pipeline/agent functions. It adds no new Gemini logic — pages call `pipeline`, `quiz`, and `mastery` directly. Gemini is only invoked when you click **Quiz me on this** or **Submit Answer** on the Daily Review page.

### Pages

| Page | What it does |
|---|---|
| **Ingest** | Paste a YouTube URL, run the pipeline, see created-vs-merged concepts |
| **Graph** | Interactive concept graph (prerequisite edges) with node filter and node/edge/orphan stats |
| **Daily Review** | Spaced-repetition picks; quiz yourself and record the result |
| **Mastery** | Read-only stats: level counts, recent attempts, top prerequisites |

Custom sidebar navigation (`st.sidebar.radio`) dispatches to a `render_*()` function per page — Streamlit's built-in `pages/` folder is intentionally not used, so we keep full control over the nav.

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
streamlit run app/streamlit_app.py
```

or:

```bash
python scripts/run_streamlit.py
```

No extra environment variables are needed — the app reads `GEMINI_API_KEY` and the Mongo settings from `.env` via `config.py`.

### Performance / quota notes

- Pure DB reads (concept list, mastery counts, recent events) are wrapped in `st.cache_data(ttl=60)` to avoid hammering Atlas on every rerun.
- No Gemini calls happen on page load. Each **Quiz me** is 1 call (generate) and each **Submit Answer** is 1 call (grade) — mind the free-tier daily cap.

### Screenshots

_TODO: add screenshots for each page._

- Ingest: `docs/screenshots/ingest.png`
- Graph: `docs/screenshots/graph.png`
- Daily Review: `docs/screenshots/review.png`
- Mastery: `docs/screenshots/mastery.png`
