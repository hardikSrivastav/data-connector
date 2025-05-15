## Cross‑DB Orchestration Think‑Through

This document explores key challenges and solutions for enabling an LLM to dynamically discover, plan, and execute queries across multiple heterogeneous data sources—MongoDB, PostgreSQL, Qdrant, Slack contexts, etc.—without requiring explicit `--type` flags. It also proposes a strategy for fast, accurate retrieval from multiple FAISS indices without unifying them.

---

### 1. Automatic Database Selection

**Challenge:** Without a `--type` flag, the orchestrator must infer which data sources are relevant to each NL query to avoid overwhelming every adapter.

**Solution Approach:**

1. **Classifier Module**

   * Implement `_classify_databases(question: str) -> List[str]` in `CrossDatabaseOrchestrator`.
   * Option A: LLM-based classification prompt that ranks supported DB types by relevance.
   * Option B: Rule-based keyword/entity mapping (e.g., SQL keywords → `postgres`, vector search terms → `qdrant`).

2. **Integration into Planning**

   ```python
   db_candidates = await self._classify_databases(user_question)
   await self.schema_searcher.initialize(db_types=db_candidates)
   plan = await self.llm.generate_plan(question, db_candidates)
   ```

   This ensures only prioritized sources enter the planning and schema-retrieval stages. citeturn0file0

3. **Fallback Logic**

   * If classifier confidence < threshold, default to a safe subset (e.g., only SQL or only vector stores) rather than *all* sources.

---

### 2. Preventing Unbounded Parallelism

**Challenge:** Dispatching queries to every adapter in parallel may exceed resource limits, especially under load.

**Solution Approach:**

1. **Configurable Concurrency**

   * Honor `max_parallel_queries` from PRD (§4.2) citeturn0file1.

2. **Semaphore-Based Batching**

   ```python
   semaphore = asyncio.Semaphore(self.config.max_parallel_queries)
   async def call_adapter(adapter, op):
       async with semaphore:
           return await adapter.execute(op)
   results = await asyncio.gather(*[call_adapter(ad, op) for ad, op in tasks])
   ```

3. **Dynamic Adjustment**

   * Monitor queue length and slow down dispatch if latencies spike.

---

### 3. Heterogeneous Schema Drift

**Challenge:** Independent schema evolution means FAISS indices and schema catalogs can become stale.

**Solution Approach:**

1. **Incremental Metadata Polling**

   * Each adapter exposes a `/metadata` endpoint with `last_updated` timestamps.
   * Poll hourly; if `last_updated > last_indexed`, trigger partial re-index. citeturn0file0

2. **On‑Demand Refresh**

   * Upon LLM-generated plan referencing unknown fields/tables, call:

     ```python
     await self.schema_searcher.refresh(db_type=adapter_type)
     ```
   * Limits rebuild scope to only affected adapters.

---

### 4. Cross‑DB Join Semantics

**Challenge:** Different systems use varying type encodings (BSON, SQL types, vector embeddings).

**Solution Approach:**

1. **Type Coercion Map**

   ```python
   type_coercers = {
       'date': lambda v: datetime.fromisoformat(v),
       'bson.Int32': int,
       # etc.
   }
   ```

2. **ResultAggregator.join**

   * Inject `type_coercers` to normalize each row before merging.
   * Ensure numeric and temporal comparisons align across sources. citeturn0file2

---

### 5. Prompt‑Engineering Hygiene

**Challenge:** The LLM may hallucinate operations on irrelevant or non‑existent databases.

**Solution Approach:**

1. **Constrained Planning Template**

   * In `cross_db_plan.tpl`, pass `db_candidates` list to the prompt so the LLM only references those.

2. **Post‑Plan Validation**

   ```python
   plan.operations = [op for op in plan.operations if op.database in db_candidates]
   if dropped := original_ops_count - len(plan.operations):
       log.warning(f"Dropped {dropped} ops outside candidates")
   ```

   Invalid operations are flagged or retried. citeturn0file0

---

### 6. Error Handling & Partial Failures

**Challenge:** Adapters might time out or error—should the pipeline abort or degrade gracefully?

**Solution Approach:**

1. **Retry with Backoff**

   * Wrap adapter calls in retry logic (configurable retries + exponential backoff).
   * Use `default_timeout` from PRD §5.3.2. citeturn0file1

2. **Partial Results**

   * Return successes immediately; attach warnings for failures in the final report.
   * Example final payload:

     ```json
     { "data": {...}, "warnings": ["Postgres query timed out"] }
     ```

---

### 7. Security & Auditing Across Sources

**Challenge:** Cross‑DB queries widen the security surface and require robust audit trails.

**Solution Approach:**

1. **Scoped Credentials**

   * Store credentials in a secure vault (e.g., HashiCorp Vault).
   * Load per-adapter creds only during operation; purge from memory immediately after use.

2. **Detailed Audit Logs**

   * Extend logging to include:

     * `query_plan_id`
     * `operation_id`
     * `db_type` & `db_endpoint`
   * Correlate logs for post‑mortem analysis. citeturn0file1

---

### 8. Observability & Metrics

**Challenge:** Hard to identify performance bottlenecks or most‑used sources.

**Solution Approach:**

1. **Metrics with Prometheus**

   * Instrument:

     * Per‑adapter request count & latencies
     * Error rates
   * Expose `/metrics` endpoint for scraping.

2. **Dashboards & Alerts**

   * Build Grafana dashboards to track hot DBs, slow queries, and failure spikes.

---

### 9. Progressive Result Streaming

**Challenge:** Waiting for all DBs to respond delays UX, especially for long joins.

**Solution Approach:**

1. **Chunked HTTP / WebSockets**

   * Stream each adapter’s result as it arrives.
   * Final join sent as a completion message.

2. **CLI-friendly Output**

   ```bash
   $ query "..."
   [Postgres] rows: 120
   [MongoDB] docs: 45
   [Qdrant] vectors: 10
   [JOINED] final rows: 98
   ```

---

### 10. Semantic Layer for Business Entities

**Challenge:** Users think in terms of domain concepts (e.g., “customers,” “sales events”) rather than raw tables.

**Solution Approach:**

1. **Define SemanticModel**

   * Map business entities to physical tables/collections across adapters.
   * Example:

     ```yaml
     Customer:
       postgres: customer_table
       mongo: customers
       qdrant: customer_embeddings
     ```

2. **LLM Plans in Semantic Terms**

   * Prompt the LLM with semantic definitions; post‑process plans to resolve physical sources. citeturn0file0

---

### 11. FAISS Multi‑Index Strategy

**Challenge:** You currently maintain separate FAISS indices per data type; a unified index is undesirable due to scale and heterogeneity.

**Solution Approach:**

1. **Parallel Index Routing**

   * Maintain per‑type indices (e.g., `faiss_users`, `faiss_orders`, `faiss_logs`).
   * At query time, use a **shard‑router** that classifies queries to one or more indices:

     ```python
     def route_to_indices(query_embedding):
         return index_classifier.predict(query_embedding)
     indices = route_to_indices(embed(query_text))
     results = [idx.search(embedding, k) for idx in indices]
     ```

2. **Result Fusion & Re‑Ranking**

   * Gather top-k from each index, then re‑rank via a small LLM pass (or TF‑IDF hybrid) to ensure global relevance.

3. **Metadata‑Aware Filtering**

   * Tag each vector with metadata (source type, timestamp, entity name).
   * Filter shards based on metadata hints from `_classify_databases` or semantic context.

4. **Approximate Global Neighborhood**

   * Use **IVF‑flat** or **HNSW** indices per shard to maintain sub‑linear search, then a final merge step.

5. **Latency Optimization**

   * Warm up hot shards, cache recent query embeddings and nearest neighbors in a tiny in‑memory LRU cache.

### 12. Two-Phase Schema Awareness

**Challenge:** Planning requires fast schema access while execution needs guaranteed correctness.

**Solution Approach:**

1. **Separation of Concerns**
   * Planning phase: Use FAISS indices for fast semantic schema search
   * Execution phase: Validate operations against Schema Registry
   * This creates a "lookahead planning, verified execution" pipeline

2. **Schema Drift Detection**
   * Compare FAISS search results with Registry validation
   * When discrepancies found, trigger FAISS reindexing
   * Log warnings for operations planned with outdated schema

3. **Implementation Pattern**
   ```python
   # Planning phase
   schema_info = await schema_searcher.search(query)  # Uses FAISS
   plan = await llm.generate_plan(query, schema_info)
   
   # Execution phase
   validation = plan.validate(registry_client)  # Uses Registry
   if validation["valid"]:
       result = await orchestrator.execute_plan(plan)
   ```

---

## Next Steps

1. Prototype `_classify_databases` and integrate into `schema_searcher`.
2. Implement semaphore‑based batching in `execute_plan`.
3. Add metadata polling and on‑demand schema refresh hooks.
4. Extend `ResultAggregator` with type coercion logic.
5. Update prompt templates to include only `db_candidates`.
6. Wrap adapter calls with retry/backoff and partial‑result warnings.
7. Secure credential loading and enhance audit logging.
8. Instrument Prometheus metrics and set up Grafana dashboards.
9. Support chunked streaming for CLI and HTTP clients.
10. Define a YAML‑based SemanticModel and update planning logic.
11. Build and test the FAISS shard‑router and result fusion pipeline.
