# VecMind   

Semantic search for your docs, built the way real internal tools actually look.

VecMind lets you ask _“What is our billing flow doing?”_ instead of grepping for `BillingFlowManagerV2`.  
It ingests `.md` / `.txt` docs from a folder, chunks them, turns them into embeddings, stores them in Postgres with `pgvector`, and exposes a tiny FastAPI backend + web UI on top.

Think: “internal knowledge search for support / GTM / eng” – but small enough to read in an afternoon.

---

## What it actually does

- **Semantic search over docs**  
  Ask questions in natural language and rank doc chunks by meaning, not keyword overlap.

- **Chunked document store**  
  Long files are split into smaller, context-rich passages so results don’t dump a 5k-line README on you.

- **Embeddings pipeline**
  - Uses **OpenAI** (`text-embedding-3-small`) when you have an API key + quota.
  - Falls back to a **deterministic local hash-based embedding** so the app still runs on an empty wallet.

- **Vector storage in Postgres**  
  Each chunk gets a `vector(1536)` embedding in a `chunks` table using `pgvector`.

- **Similarity search**  
  - Current implementation: fetch embeddings from Postgres and compute **cosine similarity in Python**.
  - pgvector index is set up and ready if you want to swap to pure SQL `<=>` later.

- **REST API + Web UI**
  - `POST /index` → crawl `data/`, chunk, embed, and store.
  - `POST /search` → semantic search and ranked results.
  - `GET /debug/count` → how many docs/chunks are indexed.
  - `/` → a simple Tailwind-styled frontend for non-technical users.

---

## Quick Start (dev mode)

```bash
# 1. Clone
git clone <repository-url>
cd VecMind

# 2. Python env (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Start Postgres + pgvector via Docker
docker compose up -d     # or: docker-compose up -d

# 5. Set up environment
cp .env.example .env
# open .env and set OPENAI_API_KEY (optional) + DATABASE_URL

# 6. Add some docs
mkdir -p data
# drop a few .md / .txt files into data/

# 7. Run the API
python3 -m uvicorn app.main:app

# 8. Open the UI
# http://localhost:8000

```

If you don’t set an OPENAI_API_KEY, VecMind still works using the local embedding fallback – it’s just “semantic-ish” instead of truly semantic.

# How it’s wired (for humans who care about architecture)
	•	Backend: FastAPI + uvicorn
	•	DB: PostgreSQL + pgvector
	•	Client: Tiny HTML/JS page with Tailwind via CDN
	•	Embedding layer:
	•	app/embeddings.py wraps OpenAI’s embedding API.
	•	When the API says “lol no quota”, it falls back to a local deterministic embedding so your demo doesn’t die.
	•	Indexing (app/ingest.py):
	1.	Reads .md / .txt from data/.
	2.	Splits text into paragraphs and wraps long ones to manageable chunks.
	3.	Creates a row in documents.
	4.	Embeds each chunk and inserts into chunks (content, embedding vector(1536), chunk_index, document_id).
	•	Searching (/search):
	1.	Embed the query text.
	2.	Pull all (document_title, path, chunk_index, content, embedding) rows.
	3.	Parse embeddings into Python lists.
	4.	Compute cosine similarity in Python.
	5.	Return the top-k chunks + scores.

Yes, the pgvector index is there. No, I’m not pretending its quirks didn’t fight me. 
FYI : The code is set up so swapping to pure SQL similarity is one query change away.

Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | `None` | Your OpenAI API key for generating embeddings. Get it from [OpenAI Platform](https://platform.openai.com/api-keys). If not provided, VecMind uses a hash-based fallback embedding (not semantic). |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@localhost:5432/vecmind` | PostgreSQL connection string. Format: `postgresql://user:password@host:port/database` |

### Example `.env` file

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vecmind
```
# Using VecMind

1. Indexing docs
Drop some .md / .txt files into data/, then either:

Via API:

```
curl -X POST http://localhost:8000/index
```
or 

```
python3 -m app.ingest

```

2. Searching

From the web UI:
	•	Go to http://localhost:8000
	•	Type something like: What is VecMind for?
	•	Hit Search
	•	Results show:
	•	document title
	•	chunk index
	•	cosine score
	•	highlighted passage

From the API:

```
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do we handle authentication?",
    "top_k": 5
  }'
```


Response: 
```JSON
[
  {
    "document_title": "sample.md",
    "source_path": "data/sample.md",
    "chunk_index": 0,
    "content": "VecMind is a semantic knowledge search engine for internal documentation...",
    "score": 0.81234
  }
]
```

Troubleshooting (aka “things I broke while building this”)

Search returns []
	•	Check if anything is indexed:
   
```
curl http://localhost:8000/debug/count
#documents > 0 and chunks > 0 ? good.

```
-
	•	If chunks are 0, you forgot to index. Run POST /index again.
	•	If chunks > 0 and you still get [], make sure you’re on the Python-similarity branch of /search (the current code).

Database connection failed
	•	Is Docker running? ``` docker compose ps```
   •	Does DATABASE_URL actually match your DB?
	   If you’re running your own Postgres, make sure you created the extension: 
      SQL```
      CREATE EXTENSION IF NOT EXISTS vector; 
      ```
# OpenAI quota / key issues
	•	If logs say OpenAI quota exceeded → that’s expected on a free or maxed account.
	•	VecMind will print a warning and silently switch to the local embedding fallback.
	•	You can still demo everything; scores just aren’t “true” semantic distance.

# Why I built this

I wanted something close to what internal support / GTM teams actually use:
	•	Real database, not “everything in memory”
	•	Real API endpoints you could plug into Slack / dashboards
	•	A UI that a non-engineer could open and understand in 30 seconds

It’s intentionally small and opinionated. If this were production, I’d add:
	•	auth
	•	better chunking (overlap, headings, etc.)
	•	filters (by doc, tag, time)
	•	evals / feedback loop for relevance

…but this version shows the full semantic-search pipeline end-to-end without 15 microservices.


# Project Layout 

```
vecmind/
  app/
    __init__.py
    config.py        # env + constants (API keys, DB URL, embedding model, etc.)
    db.py            # Postgres connection helper (psycopg2)
    models.sql       # schema + pgvector index
    embeddings.py    # OpenAI + local-fallback embedding helper
    ingest.py        # read docs, chunk, embed, insert into DB
    main.py          # FastAPI app, endpoints, and search logic
  static/
    index.html       # Tailwind UI for searching
  data/
    sample.md        # example docs (you can replace these)
  .env.example       # template for local env vars
  requirements.txt
  docker-compose.yml # Postgres + pgvector setup for local dev
  README.md
```
  If you’re reading this because you’re reviewing my resume: i know its not perfect - looking a little rough but :) hope its somewhat pass-able 

anywhom... Thank you for your interest. 
