# Implementation Guide: On-Prem Data Science Agent with Python + FastAPI + FAISS + asyncpg

This document consolidates the end-to-end blueprint and performance considerations for building a fully on-premises data‑science agent that:

* Connects to a Postgres database
* Persists schema metadata in an in-memory FAISS index
* Translates natural-language questions into SQL via an LLM
* Executes queries with asyncpg
* Exposes both HTTP (FastAPI) and CLI interfaces
* Runs entirely within the client’s network

---

## 1. Tech Stack & Core Libraries

* **Language & Framework**: Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/) for HTTP + CLI
* **Database Driver**: `asyncpg` for non-blocking Postgres connections
* **Vector Store**: [FAISS](https://github.com/facebookresearch/faiss) (HNSW or IVF+PQ index)
* **LLM Integration**:

  * **Local**: `llama-cpp-python` or similar for on-device inference
  * **Cloud**: `openai` Python SDK
* **Concurrency & Workers**:

  * Uvicorn/Gunicorn (`UvicornWorker`) with multiple workers
  * `asyncio` event loop + process pool for CPU-bound tasks
* **Configuration & Validation**: Pydantic settings models

---

## 2. Project Layout

```bash
/agent
├── cmd/               # CLI entrypoints
│   └── query.py
├── api/               # FastAPI routers & handlers
│   └── endpoints.py
├── config/            # Env-vars & config file parsing
│   └── settings.py
├── db/                # Schema introspection + asyncpg pool
│   ├── introspect.py
│   └── execute.py
├── llm/               # LLM wrappers (local & cloud)
│   └── client.py
├── meta/              # Metadata ingestion & FAISS index
│   ├── ingest.py
│   └── index.faiss     # persisted index file
├── prompts/           # Prompt templates (Jinja2/YAML)
│   └── nl2sql.tpl
├── performance/       # Caching layers & optimizations
│   └── cache.py
└── main.py            # Application startup, DI, load index, launch FastAPI
```

---

## 3. Configuration & Startup

* **Settings** (via Pydantic):

  * DB: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`, `SSL_MODE`
  * FAISS: `FAISS_INDEX_PATH`, quantization flags
  * LLM: `MODEL_PATH`/`MODEL_TYPE` or `LLM_API_URL`/`LLM_API_KEY`/`LLM_MODEL_NAME`
  * Server: `AGENT_PORT`, `LOG_LEVEL`, worker count
  * Caching: `CACHE_PATH`, hot-item LRU size

* **Startup sequence**:

  1. Load & validate settings
  2. Initialize asyncpg connection pool
  3. Load or build FAISS index from `meta/ingest.py`
  4. Spin up FastAPI app with router registrations

Launch with Gunicorn + UvicornWorker for high concurrency:

```bash
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:${AGENT_PORT}
```

Or via Docker entrypoint that sets `UVICORN_CMD`.

---

## 4. Core Pipelines

### 4.1 Schema Introspection & Metadata Ingestion

```python
# db/introspect.py
async def fetch_schema(pool):
    async with pool.acquire() as conn:
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        columns = await conn.fetch("SELECT table_name, column_name, data_type FROM information_schema.columns;")
        # join PK/FK from pg_constraint
```

* **Chunk documents**: one per table, one per column
* **Embed**: use LLM embedding endpoint or local embedder
* **Build FAISS**: quantize to 8-bit, save to `meta/index.faiss`

### 4.2 NL → SQL Translation

```python
# api/endpoints.py
@router.post('/query')
async def query(request: QueryRequest):
    chunks = meta.search(request.question, top_k=5)
    prompt = render_template('nl2sql.tpl', schema_chunks=chunks, user_question=request.question)
    sql = await llm_client.generate_sql(prompt)
    validated_sql = sanitize_sql(sql)
    rows = await db.execute(validated_sql)
    if request.analyze:
        analysis = await llm_client.analyze_results(rows)
        return { 'rows': rows, 'analysis': analysis }
    return { 'rows': rows }
```

* **Sanitize**: only allow `SELECT`, no updates or schema changes
* **Auto-LIMIT**: append `LIMIT 1000` if absent

### 4.3 CLI Interface

```bash
# cmd/query.py
import typer
from api.client import AgentClient

app = typer.Typer()
@app.command()
def query(q: str, analyze: bool = False):
    resp = AgentClient().query(q, analyze)
    print(resp)
```

---

## 5. Performance & Optimization

1. **FAISS in-memory**: load `index.faiss` into RAM; quantized embeddings → small memory footprint
2. **ANN library**: FAISS HNSW or IVF+PQ for sub-ms vector lookups
3. **LRU cache**: memoize schema chunks for hot tables/columns
4. **Async DB**: `asyncpg` connection pool (min\_size=5, max\_size=20)
5. **Process pool**: offload FAISS searches or local LLM inference to `run_in_executor`
6. **Uvicorn/Gunicorn tuning**: match `--workers` to CPU cores
7. **Docker image**: `python:3.11-slim`, `pip install --no-cache-dir`, copy prebuilt index
8. **Connection pooling & prepared statements**: reduce handshake & parse overhead
9. **Auto-pagination**: default `LIMIT 1000`

**Latency targets**:

* Metadata lookup: 1–5ms
* Prompt assembly: 5–10ms
* LLM call: 50–200ms
* SQL exec: 10–100ms
* Serialization: 1–5ms

---

## 6. Security, Testing & Deployment

* **SQL AST validation**: e.g. `sqlfluff` or custom parser to ensure only `SELECT`
* **Input sanitization**: escape identifiers, no raw interpolation
* **Local logs & cache wipe**: support `--wipe-on-exit`
* **Unit tests**: pytest for each module

### Integration Tests

* **Docker Compose Setup**: Define a `docker-compose.yml` that brings up both Postgres and your agent service on an isolated test network.
* **Test Fixtures**: Use pytest fixtures (or the `testcontainers` library) to programmatically start and stop containers for your agent and database.
* **HTTPX Client**: Employ `httpx.AsyncClient` in your tests to send HTTP requests to FastAPI endpoints and assert on JSON payloads and status codes.
* **Data Seeding & Teardown**: Before each test suite, seed the database using SQL scripts or ORM migrations. After tests, drop or truncate schemas to reset state.
* **Sample Test Case**:

  ```python
  @pytest.fixture(scope="session")
  async def test_app():
      # Start docker-compose services
      # Yield base URL
      # Teardown services

  @pytest.mark.asyncio
  async def test_query_endpoint(test_app):
      client = httpx.AsyncClient(base_url=test_app)
      response = await client.post("/query", json={"question": "SELECT 1","analyze": False})
      assert response.status_code == 200
      assert "rows" in response.json()
  ```
* **CI/CD Integration**: In GitHub Actions, include steps to invoke `docker-compose up --build -d`, run `pytest`, then `docker-compose down`.

## 7. Alternative Architectures

If Python overhead is too high:

* **Go** (Gin + pgx + cgo FAISS bindings) for single-binary performance
* **Rust** (Actix-Web + rust-postgres + vectordb crates)
* Use Python subprocess for pure-Python modules only

But for DB + LLM–dominated latency, Python + FastAPI is typically sufficient.

---

*Save this as* **implementation-guide.md** *and share with your team.*
