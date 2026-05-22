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
