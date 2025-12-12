
# VecMind – Semantic Knowledge Search Engine

VecMind is a semantic search system that lets you query documentation and notes **by meaning**, not just exact keywords. Documents are ingested from a local folder, chunked, embedded via the OpenAI API, and stored in PostgreSQL with the `pgvector` extension for fast vector similarity search. A small Python backend exposes REST endpoints (`/index`, `/search`) and a lightweight web UI so non-technical users can ask natural language questions and browse ranked passages with source context.

---

## Features

-  **Semantic search over docs** – query by intent instead of fragile keyword matches.
-  **Chunked document storage** – splits long docs into manageable, context-rich chunks.
-  **OpenAI embeddings** – uses `text-embedding-3-small` to represent text as vectors.
-  **PostgreSQL + pgvector** – vector similarity search (`<=>`) for top relevant chunks.
-  **Python fallback** – automatic fallback to Python-based cosine similarity if pgvector has issues.
-  **REST API** – `/index` and `/search` endpoints for easy integration with other tools.
-  **Simple web UI** – single-page interface with usage guide for non-technical users.

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd VecMind

# 2. Start PostgreSQL with pgvector (using Docker)
docker-compose up -d

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Copy environment variables template
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 5. Start the application
uvicorn app.main:app --reload

# 6. Open browser to http://localhost:8000
```

---

## Installation

### Prerequisites

- **Python 3.8+** – Required for the backend
- **PostgreSQL 12+** with `pgvector` extension – For vector storage and search
- **Docker & Docker Compose** (recommended) – For easy database setup
- **OpenAI API Key** (optional) – For semantic embeddings. Without it, VecMind uses a fallback hash-based embedding.

### Step-by-Step Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd VecMind
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start PostgreSQL database**
   
   Using Docker Compose (recommended):
   ```bash
   docker-compose up -d
   ```
   
   This starts a PostgreSQL 16 instance with pgvector extension on port 5432.
   
   Or use your own PostgreSQL instance:
   - Install PostgreSQL and enable the pgvector extension
   - Create a database named `vecmind`
   - Update `DATABASE_URL` in your `.env` file

4. **Configure environment variables**
   
   Create a `.env` file in the root directory:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vecmind
   ```

5. **Index your documents**
   
   Place your `.md` or `.txt` files in the `data/` directory, then:
   
   Via API:
   ```bash
   curl -X POST http://localhost:8000/index
   ```
   
   Or via Python:
   ```bash
   python -m app.ingest
   ```

6. **Start the application**
   ```bash
   uvicorn app.main:app --reload
   ```
   
   The web UI will be available at `http://localhost:8000`

---

## Environment Variables

Create a `.env` file in the root directory with the following variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | `None` | Your OpenAI API key for generating embeddings. Get it from [OpenAI Platform](https://platform.openai.com/api-keys). If not provided, VecMind uses a hash-based fallback embedding (not semantic). |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@localhost:5432/vecmind` | PostgreSQL connection string. Format: `postgresql://user:password@host:port/database` |

### Example `.env` file

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vecmind
```

---

## Usage

### Web UI

1. Open `http://localhost:8000` in your browser
2. Type your question in natural language (e.g., "What is VecMind for?")
3. Press Enter or click Search
4. View ranked results with similarity scores

The UI includes:
- Usage guide (click "How to Use VecMind")
- Example queries to try
- Keyboard shortcuts (Enter to search, Esc to clear)
- Visual score indicators

### API Endpoints

#### Index Documents
```bash
POST /index
```
Indexes all `.md` and `.txt` files in the `data/` directory.

**Response:**
```json
{
  "status": "ok"
}
```

#### Search
```bash
POST /search
Content-Type: application/json

{
  "query": "What is VecMind for?",
  "top_k": 5
}
```

**Response:**
```json
[
  {
    "document_title": "sample.md",
    "source_path": "/path/to/data/sample.md",
    "chunk_index": 0,
    "content": "VecMind is a semantic knowledge search engine...",
    "score": 0.758566
  }
]
```

#### Debug Endpoints

- `GET /debug/count` – Returns document and chunk counts
- `GET /debug/test-vector` – Tests vector queries for debugging

---

## Troubleshooting

### Empty Search Results

**Symptom:** Search returns 0 results even though documents are indexed.

**Solutions:**
1. **Check if documents are indexed:**
   ```bash
   curl http://localhost:8000/debug/count
   ```
   If chunk count is 0, run indexing: `POST /index`

2. **Python fallback is active:** VecMind automatically falls back to Python-based similarity search if pgvector queries fail. Check server logs for `[INFO] Falling back to Python-based similarity search`. This is normal and will still return results.

3. **Query too specific:** Try rephrasing your question or using more general terms.

### Database Connection Issues

**Symptom:** `Database connection failed` error.

**Solutions:**
1. **Check if PostgreSQL is running:**
   ```bash
   docker-compose ps
   # or
   psql -h localhost -U postgres -d vecmind
   ```

2. **Verify DATABASE_URL:** Ensure your `.env` file has the correct connection string matching your PostgreSQL setup.

3. **Check pgvector extension:**
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```
   If not installed, run: `CREATE EXTENSION vector;`

### OpenAI API Errors

**Symptom:** `OpenAI quota exceeded` or API errors.

**Solutions:**
1. **Check API key:** Verify `OPENAI_API_KEY` in your `.env` file is correct.

2. **Quota exceeded:** VecMind automatically uses a fallback hash-based embedding when OpenAI quota is exceeded. This works but isn't semantic. Check your OpenAI usage at [platform.openai.com](https://platform.openai.com).

3. **Rate limiting:** Wait a few minutes and try again, or upgrade your OpenAI plan.

### pgvector Issues

**Symptom:** pgvector queries return 0 rows (check server logs).

**Solutions:**
1. **Check pgvector version:**
   ```sql
   SELECT extversion FROM pg_extension WHERE extname = 'vector';
   ```
   Ensure you're using a compatible version (0.5.0+).

2. **Index may need rebuilding:** If you've changed the vector dimension or format:
   ```sql
   DROP INDEX IF EXISTS chunks_embedding_idx;
   CREATE INDEX chunks_embedding_idx ON chunks 
   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```

3. **Python fallback:** VecMind automatically uses Python-based similarity when pgvector fails. This is slower but works correctly.

### Port Already in Use

**Symptom:** `Address already in use` when starting the server.

**Solutions:**
1. **Change port:**
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

2. **Kill existing process:**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   # Kill it
   kill -9 <PID>
   ```

---

## Performance Optimization

### pgvector Performance Tips

VecMind uses pgvector for fast vector similarity search. Here are ways to optimize performance:

#### 1. Index Tuning

The current index uses `ivfflat` with `lists = 100`. Adjust based on your data size:

```sql
-- For smaller datasets (< 10k chunks)
DROP INDEX chunks_embedding_idx;
CREATE INDEX chunks_embedding_idx ON chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

-- For larger datasets (> 100k chunks)
DROP INDEX chunks_embedding_idx;
CREATE INDEX chunks_embedding_idx ON chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1000);
```

**Rule of thumb:** `lists` should be approximately `rows / 1000` for optimal performance.

#### 2. Query Optimization

- **Limit results:** Always use `top_k` parameter (default: 5-10) to avoid processing too many results
- **Use exact search when possible:** pgvector's `<=>` operator is optimized for cosine distance
- **Monitor query performance:** Check server logs for query execution time

#### 3. When Python Fallback is Used

VecMind automatically falls back to Python-based cosine similarity when:
- pgvector queries return 0 rows (known issue being debugged)
- Database connection issues occur
- Vector format mismatches

**Performance impact:**
- Python fallback: O(n) where n = number of chunks (slower for large datasets)
- pgvector: O(log n) with index (much faster)

**To improve fallback performance:**
- Limit the number of chunks processed
- Consider caching frequently searched queries
- Use smaller `top_k` values

#### 4. Database Optimization

```sql
-- Analyze tables for better query planning
ANALYZE chunks;
ANALYZE documents;

-- Check index usage
EXPLAIN ANALYZE SELECT * FROM chunks ORDER BY embedding <=> '[...]'::vector LIMIT 5;
```

#### 5. Embedding Model Considerations

- Current model: `text-embedding-3-small` (1536 dimensions)
- For better accuracy (slower): Use `text-embedding-3-large` (3072 dimensions)
- For faster queries: Consider `text-embedding-ada-002` (1536 dimensions, older model)

**Note:** Changing embedding models requires re-indexing all documents.

---

## Future Plans

VecMind is actively being improved. Here's the roadmap:

### High Priority

- **Fix pgvector issue** – Debug and resolve why `<=>` operator returns 0 rows in some cases. This will improve search performance by leveraging pgvector's optimized vector search instead of Python fallback.

### Planned Features

- **Document Management**
  - View all indexed documents
  - Delete documents and their chunks
  - Update/re-index individual documents
  - Document metadata (upload date, file size, etc.)

- **Search Filters**
  - Filter by document name/source
  - Filter by date range (if document timestamps are added)
  - Filter by minimum similarity score threshold
  - Filter by document type (`.md`, `.txt`, etc.)

- **Batch Indexing Improvements**
  - Progress indicator for large document sets
  - Background/async indexing
  - Resume interrupted indexing
  - Index status endpoint

- **Export Functionality**
  - Download search results as JSON
  - Export results as CSV
  - Export indexed documents list
  - Export search history (if implemented)

### Potential Enhancements

- **Search History** – Save and replay recent queries
- **Advanced Chunking** – Smarter chunking strategies (sentence-aware, overlap, etc.)
- **Multi-language Support** – Support for non-English documents
- **Authentication** – User authentication for multi-user deployments
- **Performance Monitoring** – Track search performance metrics
- **API Rate Limiting** – Protect against abuse
- **Webhook Support** – Notify on document updates

---

## Tech Stack

- **Backend:** Python, FastAPI, Uvicorn
- **Database:** PostgreSQL + `pgvector`
- **AI:** OpenAI Embeddings (`text-embedding-3-small`)
- **Frontend:** Vanilla JS + Tailwind CSS (CDN)
- **Other:** `psycopg`, `python-dotenv`

---

## Deployment

VecMind can be deployed to various platforms. Choose the option that best fits your needs:

### Option 1: Railway (Recommended)

Railway provides PostgreSQL with pgvector and easy deployment:

1. **Sign up** at [railway.app](https://railway.app)
2. **Create a new project** and connect your GitHub repository
3. **Add PostgreSQL service**:
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway automatically provides `DATABASE_URL`
4. **Add pgvector extension**:
   - Go to your PostgreSQL service → "Query"
   - Run: `CREATE EXTENSION vector;`
5. **Deploy the app**:
   - Click "New" → "GitHub Repo" → Select VecMind
   - Railway will auto-detect the Dockerfile
6. **Set environment variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `DATABASE_URL`: Automatically set by Railway
7. **Deploy** and access your app!

### Option 2: Render

1. **Sign up** at [render.com](https://render.com)
2. **Create a new Web Service** from your GitHub repo
3. **Add PostgreSQL database**:
   - Create a new PostgreSQL database
   - Note: You'll need to manually enable pgvector extension
4. **Configure environment variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `DATABASE_URL`: From your PostgreSQL database
5. **Set build command**: `pip install -r requirements.txt`
6. **Set start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
7. **Deploy**

### Option 3: Heroku

1. **Install Heroku CLI** and login
2. **Create app**: `heroku create your-app-name`
3. **Add PostgreSQL**: `heroku addons:create heroku-postgresql:mini`
4. **Enable pgvector**: Connect to database and run `CREATE EXTENSION vector;`
5. **Set environment variables**:
   ```bash
   heroku config:set OPENAI_API_KEY=your_key_here
   ```
6. **Deploy**: `git push heroku main`

### Option 4: Docker Deployment

For self-hosted deployment:

```bash
# Build the image
docker build -t vecmind .

# Run with docker-compose (includes PostgreSQL)
docker-compose up -d

# Or run standalone (requires external PostgreSQL)
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e DATABASE_URL=postgresql://user:pass@host:5432/vecmind \
  vecmind
```

### Environment Variables for Production

Make sure to set these in your deployment platform:

- `OPENAI_API_KEY`: Your OpenAI API key (required for semantic search)
- `DATABASE_URL`: PostgreSQL connection string with pgvector enabled
- `PORT`: Usually set automatically by the platform

### Post-Deployment Steps

1. **Index your documents**:
   ```bash
   curl -X POST https://your-app-url.com/index
   ```

2. **Verify deployment**:
   ```bash
   curl https://your-app-url.com/debug/count
   ```

3. **Test search**:
   ```bash
   curl -X POST https://your-app-url.com/search \
     -H "Content-Type: application/json" \
     -d '{"query": "test query", "top_k": 5}'
   ```

---

## Project Structure

```bash
vecmind/
  app/
    __init__.py
    config.py        # env + constants (API keys, DB URL, model name, etc.)
    db.py            # Postgres connection helper
    models.sql       # schema + pgvector index setup
    embeddings.py    # OpenAI embedding helper
    ingest.py        # ingest + chunk + embed + insert into DB
    main.py          # FastAPI app + REST endpoints
  static/
    index.html       # web UI with usage guide
  data/
    sample.md        # docs to be indexed (.md or .txt)
  .env               # environment variables (create from .env.example)
  .env.example       # environment variables template
  requirements.txt
  docker-compose.yml # PostgreSQL + pgvector setup
  Dockerfile         # Container image for deployment
  Procfile           # Process file for Heroku/Railway
  README.md
```
