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
