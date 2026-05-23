# Honeycomb

> A multi-step learning agent that turns YouTube transcripts into a self-linking, mastery-tracked knowledge graph.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://honeycomb-agent-jpz3bblmwwytqhpkwwhvxu.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built with Gemini](https://img.shields.io/badge/Built_with-Gemini_2.5_Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)

**Live demo:** https://honeycomb-agent-jpz3bblmwwytqhpkwwhvxu.streamlit.app
**Repo:** https://github.com/vineetKverma/honeycomb-agent

## What is Honeycomb

Watching educational videos is easy; remembering and connecting what you learn is hard. Honeycomb is an agent that ingests a YouTube transcript, uses Gemini to extract atomic learning concepts, and links each one into a growing knowledge graph using MongoDB Atlas Vector Search — so related ideas connect automatically instead of living as isolated notes. It then quizzes you, grades your answers, and tracks per-concept mastery over time, surfacing a spaced-repetition daily review of your weakest and stalest concepts. The result is a living map of what you know, color-coded by how well you know it.

## Screenshots

| Knowledge graph | Daily review | Quiz |
|---|---|---|
| ![Graph](docs/screenshots/graph.png) | ![Review](docs/screenshots/review.png) | ![Quiz](docs/screenshots/quiz.png) |

## How it works

```mermaid
flowchart TD
    A[User gives a YouTube URL] --> B[Fetch transcript]
    B --> C[Gemini 2.5 Flash: extract atomic concepts]
    C --> D[Embed each concept - 768-dim]
    D --> E[Atlas Vector Search: find nearest concept]
    E -->|score >= 0.95 and name match| F[Merge into existing node]
    E -->|otherwise| G[Create new node]
    F --> H[Knowledge graph updated]
    G --> H
    H --> I[Quiz -> grade -> record mastery event]
    I --> J[Spaced-repetition daily review]
    J -->|study more| A
```

## Architecture

- **Agent** — Google Cloud Agent Builder (ADK) orchestrating Gemini 2.5 Flash with 6 tools and a multi-step instruction prompt.
- **Extraction & embeddings** — Gemini 2.5 Flash for structured concept extraction; `gemini-embedding-001` for 768-dim vectors.
- **Storage** — MongoDB Atlas: a `concepts` document collection plus an `mastery_events` append-only log.
- **Linking** — MongoDB Atlas Vector Search (cosine, 768-dim) with a name-normalization gate to merge duplicates instead of creating them.
- **Partner integration** — MongoDB MCP Server (stdio) gives the agent read-only `find` / `aggregate` / `count` / `list-collections` tools.
- **Frontend** — Streamlit (4 pages) on Streamlit Cloud; the knowledge-graph hero is rendered with `streamlit-agraph`, colored by mastery level.

## Multi-step agent in action

The ADK agent exposes six tools:

1. **`ingest_learning_source`** — fetch transcript, extract concepts, embed, and link into the graph.
2. **`quiz_concept`** — generate one understanding-focused question for a concept.
3. **`grade_my_answer`** — grade a free-text answer fairly and encouragingly.
4. **`record_quiz_attempt`** — append the outcome to the mastery event log.
5. **`daily_review`** — return the weakest / most-overdue concepts for spaced repetition.
6. **MongoDB MCP tools** — `find` / `aggregate` / `count` / `list-collections` for agent-mediated graph queries.

**Sample mission:** *"Ingest this 3Blue1Brown video, tell me where I'm weakest, and quiz me."*
The agent plans aloud, then chains: `ingest_learning_source` -> MCP `count`/`find` -> `daily_review` -> `quiz_concept` -> `grade_my_answer` -> `record_quiz_attempt`.

## Why MongoDB

- **Document model** fits concepts naturally — a node's definition, prerequisites, sources, and embedding live in one document, no joins.
- **Atlas Vector Search** powers the core USP: new concepts are linked by semantic similarity, turning isolated notes into a graph.
- **MongoDB MCP Server** is a first-class way to give an LLM agent safe, read-only database access as tools — the partner integration is in the agent's actual call path, not bolted on.

## Local setup

```bash
git clone https://github.com/vineetKverma/honeycomb-agent.git
cd honeycomb-agent

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in the values below
```

### Environment variables (`.env`)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `MONGODB_URI` | Atlas connection string |
| `MONGODB_DB` | Database name (e.g. `honeycomb`) |
| `MONGODB_COLLECTION` | Collection name (e.g. `concepts`) |
| `VECTOR_INDEX_NAME` | Atlas vector index name (e.g. `concept_vector_index`) |

### Atlas vector index

Create a Vector Search index named `concept_vector_index` on `honeycomb.concepts`:

```json
{
  "fields": [
    { "type": "vector", "path": "embedding", "numDimensions": 768, "similarity": "cosine" }
  ]
}
```

### Run

```bash
streamlit run app/streamlit_app.py      # the web app
python scripts/run_agent_cli.py         # the ADK agent in a local REPL
python scripts/test_mastery.py          # mastery logic test (zero Gemini quota)
```

## MongoDB MCP smoke test

The MCP server is a Node.js package. Install Node 18+, then:

```bash
npm install -g mongodb-mcp-server
python scripts/test_mongo_mcp.py
```

This spawns the server over stdio, runs the MCP `initialize` handshake, lists the tools, and reads one document back to prove an end-to-end agent -> MCP -> Atlas round trip.

## Project structure

```
honeycomb-agent/
├── agent/                 # ADK agent: tools, system prompt, MCP wiring
│   ├── agent.py
│   ├── tools.py
│   ├── system_prompt.py
│   └── mcp_config.json
├── app/                   # Streamlit UI (graph / ingest / review / mastery)
│   ├── streamlit_app.py
│   └── pages_*.py
├── scripts/               # smoke tests & utilities
├── data/                  # test source URLs
├── ingest.py              # transcript fetch
├── extract.py             # Gemini concept extraction
├── embed.py               # Gemini embeddings
├── link.py                # vector-search merge-or-create
├── quiz.py                # quiz generation + grading
├── mastery.py             # mastery + spaced repetition
├── pipeline.py            # ingest orchestration
├── db.py / config.py      # Atlas + settings
├── requirements.txt
└── runtime.txt
```

## Hackathon compliance

- [x] Multi-step agent built on Google Cloud Agent Builder (ADK)
- [x] Powered by Gemini 2.5 Flash
- [x] MongoDB Atlas as the data layer (documents + Vector Search)
- [x] MongoDB MCP Server partner integration in the agent's tool set
- [x] Publicly deployed live demo (Streamlit Cloud)
- [x] Public repository, MIT licensed

## Limitations

- **Hosted demo uses the direct DB path.** Streamlit Cloud cannot spawn the Node MCP subprocess, so the deployed app talks to Atlas directly via pymongo. The MongoDB MCP integration runs locally (via the agent CLI and `scripts/test_mongo_mcp.py`).
- **Free-tier Gemini quota** is ~20 requests/day on 2.5 Flash, so quizzing and ingesting are paced; production would move to Vertex AI.
- **Vector search** requires the Atlas index to be in `Active` status before linking works.

## What's next

- More source types (PDFs, articles, podcasts).
- Graph analytics: learning-path suggestions and prerequisite gap detection.
- Vertex AI backend for production-grade quota.
- Multi-user accounts and shareable graphs.

## Acknowledgments

- Google Cloud Rapid Agent Hackathon (MongoDB partner track).
- Google ADK, Gemini, and the MongoDB MCP Server team.
- `streamlit-agraph` for the graph visualization, and 3Blue1Brown for excellent test content.

## License

Released under the MIT License — see [LICENSE](LICENSE).
