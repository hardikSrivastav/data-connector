# GA4 Implementation for Ceneca Agent

This document details the end-to-end moving parts of the Google Analytics 4 (GA4) adapter in the Ceneca on-prem data-analysis agent, incorporating schema ingestion, FAISS indexing, introspection, and schema-registry integration, plus key technical considerations.

---

## 1. Adapter Interface Conformance

1. **Base Interface Implementation**

   * GA4 adapter implements the same `AdapterInterface`:

     ```python
     class GA4Adapter(AdapterInterface):
         def __init__(self, config, schema_registry, faiss_index): ...
         def connect(self): ...
         def ingest_schema(self): ...
         def run_query(self, payload): ...
     ```
2. **Adapter Registration**

   * Register in the central factory:

     ```python
     from .ga4_adapter import GA4Adapter
     AdapterFactory.register('ga4', GA4Adapter)
     ```
   * Ensures `data-connector --db ga4` resolves to `GA4Adapter`.

---

## 2. Configuration Structure

1. **`config.yaml` Definition**
   
   ```yaml
   ga4:
     key_file: /etc/data-connector/credentials/ga4-service-account.json
     property_id: 123456789
     scopes:
       - https://www.googleapis.com/auth/analytics.readonly
     token_cache_db: /var/lib/data-connector/ga4_tokens.sqlite  # optional
     # Optional multi-property list:
     properties:
       - id: 123456789
         alias: production
       - id: 987654321
         alias: staging
   ```
2. **`settings.py` Parsing**

   * Extend `Settings` dataclass:

     ```python
     class Settings(BaseSettings):
         ga4_key_file: Path
         ga4_property_id: int
         ga4_scopes: List[str]
         ga4_token_cache_db: Optional[Path]
         ga4_properties: List[GA4PropertyConfig]
     ```
   * Load via:

     ```python
     GA4Config = settings.ga4
     ```
   * Validate presence of `ga4.key_file` and `ga4.property_id`.

---

## 3. Connection & Client Initialization

1. **Load Service-Account Credentials**

   * Read JSON key path from `config.yaml` (`ga4.key_file`).
   * Use `google.oauth2.service_account.Credentials.from_service_account_file(...)` with scopes `analytics.readonly`.
2. **Instantiate GA4 Client**

   ```python
   from google.analytics.data_v1beta import BetaAnalyticsDataClient
   client = BetaAnalyticsDataClient(credentials=creds)
   ```
3. **Health Check**

   * Call `client.get_property(name=f"properties/{property_id}")` on startup.
   * Verify IAM permissions and network reachability.
4. **Token Management**

   * On expiry (buffered), call `creds.refresh(Request())`.
   * (Optional) Persist `{ token, expiry }` to `ga4.token_cache_db` (SQLite) to limit token endpoint calls.

> **Technical Concerns:**
>
> * **Network latency** in on-prem vs GCP: consider local caching of metadata.
> * **Token TTL**: avoid token-thundering by adding jitter to refresh logic.

---

## 4. Schema & Metadata Ingestion

1. **Fetch Full Metadata**

   * Endpoint: `client.get_metadata(name=f"properties/{property_id}/metadata")`.
   * Retrieves lists of dimensions, metrics, custom definitions, segments.
2. **Normalize Metadata**

   * Map each field to: `{ name, type, description, possibleValues? }`.
3. **Persist to Schema Registry**

   * SQLite table `ga4_fields`: columns for `property_id`, `field_name`, `field_type`, `domain`, `description`, `version_hash`, `last_updated`.
4. **Version Control**

   * Compute `version_hash = sha256(json_metadata)`; only rewrite rows when hash changes.

> **Technical Concerns:**
>
> * **Metadata size** can grow; prune deprecated fields based on `last_updated`.
> * **Schema drift**: schedule daily metadata-sync jobs and alert on removed fields.

---

## 5. FAISS Indexing & Introspection

1. **Embed Field Definitions**

   * Use LLM to generate embeddings for each field's `name + description`.
   * Example: `embed("averageSessionDuration: The average length of sessions in seconds")`.
2. **Build FAISS Index**

   * Index embeddings with identifiers pointing to registry rows.
3. **Introspection Routines**

   * **Sample Query Runner**: for each field, run a `runReport` fetching top N values or first M rows.
   * **Aggregation Snapshot**: numeric metrics → min/max/avg/count; categorical → unique-value list.
4. **Attach Introspection Data**

   * Store snapshots in a parallel SQLite table `ga4_field_inspection(field_name, sample_values, stats_json)`.

> **Technical Concerns:**
>
> * **API Quotas**: introspection can consume high quota; throttle or run during off-peak.
> * **Embedding cost**: batch embeddings to reduce LLM calls; cache embedding vectors.

---

## 6. Schema Registry Mapping & Constraints Handling

1. **Mapping GA4 Types**

   * Map GA4 data types to registry schema types:
     * `STRING` → `text`
     * `INTEGER` → `integer` 
     * `FLOAT` → `float`
     * etc.
2. **Constraint Rules**

   * Record valid dimension–metric pairings in schema registry.
   * Example: `sessionDuration` metric only valid with `date`, `country`, etc. dimensions.
3. **Registry Schema Extension**

   * Add `valid_dimensions` or `valid_metrics` JSON columns to `ga4_fields`.
   * Use constraints for query validation.
4. **Custom Dimension/Metric Handling**

   * Tag custom fields with `is_custom: true` in registry.
   * Document custom field naming conventions (`customEvent:*`, `customDimension:*`).

> **Technical Concerns:**
>
> * **Constraint complexity**: GA4 has complex compatibility rules.
> * **Metadata updates**: re-validate constraints when schema changes.

---

## 7. Query Translation Engine

1. **Field Candidates via FAISS**

   * On user query, embed the NL prompt, find nearest field-embeddings to suggest relevant dimensions/metrics.
2. **Prompt Template**

   ```text
   Translate the following question into a GA4 runReport payload.
   Property: {property_id}
   Candidate fields: {list from FAISS}
   Introspection hints: {aggregate stats/examples}
   Question: "{user_question}"
   ```
3. **Generate Payload**

   * LLM outputs JSON with `dateRanges`, `dimensions`, `metrics`, `dimensionFilterClauses`, and possible `orderBys`.
4. **Date & Filter Resolution**

   * Convert "last 7 days" → `startDate`, `endDate` with Asia/Kolkata local dates.
   * Use introspection sample values to map "country = India" to filter value.

> **Technical Concerns:**
>
> * **Prompt length**: keep candidate lists to top-10 fields to fit LLM context window.
> * **Ambiguity**: validate LLM-generated JSON against allowed fields in schema registry; fallback to manual error.

---

## 8. Cross-Database Query Integration

1. **Planning Agent Integration**

   ```python
   plan = planner.plan_query(nl_query)
   if 'ga4' in plan.sources:
       ga4_data = adapters['ga4'].run_query(plan.ga4_payload)
   if 'postgres' in plan.sources:
       pg_data = adapters['postgres'].run_query(plan.sql)
   combined = merge_sources(ga4_data, pg_data, plan.join_keys)
   ```
2. **Hybrid NL-to-Plan Generation**

   * LLM system prompt splits tasks into GA4 payload and SQL with join strategy.
   * For example: "Join GA4 user metrics with product sales from Postgres".
3. **Merge Logic**

   * `merge_sources()` handles dataframe joins, null fills, type coercion.
   * Support for inner/left/right/outer joins based on plan specifications.
4. **Post-Join Aggregations** 

   * Apply specified aggregations (sum, avg, etc.) after data merging.
   * Handle dimensional alignment for hierarchical aggregations.

> **Technical Concerns:**
>
> * **Data volume**: GA4 & DB joins may produce large result sets.
> * **Type compatibility**: GA4 strings vs DB enums/types.
> * **Shared keys**: ensure natural join keys exist between systems.

---

## 9. API Quota Management & Sampling Limitations

1. **Rate-Limit Handling**

   * Exponential back-off on `429`/`5xx` with jitter.
   * Configurable retry limits and cooldown periods.
2. **Quota Tracking**

   * Read headers for remaining quota; log/alert at <10%.
   * Daily/hourly quota budgets with priority queue.
3. **Sampling Warnings**

   * Detect sampled data in response metadata; notify users.
   * Optionally split date ranges to reduce sampling impact.
4. **Pre-Aggregation**

   * Nightly ETL to pre-aggregate high-volume reports.
   * Scheduled data pulls during low-traffic periods.

> **Technical Concerns:**
>
> * **Quota exhaustion**: graceful degradation when limits reached.
> * **Sampling bias**: document sampling methodology to users.

---

## 10. Data Freshness & Cache Invalidation

1. **Data Lag Awareness**

   * GA4 data typically lags 24–48 hours; tag caches with `dataTimestamp`.
   * Align cache TTL with GA4 processing latency.
2. **Cache Expiry**

   * Expire caches older than configured `max_data_age` (e.g., 2 days).
   * Separate TTLs for real-time vs historical data.
3. **User Feedback**

   * Return freshness metadata alongside data.
   * LLM summary includes: "Data as of May 15, 2024 (48 hours ago)".
4. **Incremental Refreshes**

   * Periodic background processes to refresh recent date ranges.
   * Prioritize refresh of most-queried reports.

> **Technical Concerns:**
>
> * **Data arrival windows**: GA4 processing times vary by data volume.
> * **Incremental consistency**: ensure partial refreshes don't create gaps.

---

## 11. Property Selection & Multi-Property Queries

1. **Single vs. Multi-Property Mode**

   * Default to `ga4.property_id`; override with `--property` flag.
   * Support property aliases from configuration.
2. **Aggregating Across Properties**

   ```python
   frames = []
   for prop in settings.ga4_properties:
       df = client.runReport(property=prop.id, ...)
       df['property_alias'] = prop.alias
       frames.append(df)
   combined = pd.concat(frames)
   ```
3. **Property-Specific Schema**

   * Track dimensions/metrics per property ID in registry.
   * Handle property-specific custom dimensions/metrics.
4. **User Selection**

   * CLI: `data-connector ga4 --property=production "Last week's sessions"`
   * API: `{"question": "...", "property": "production"}`

> **Technical Concerns:**
>
> * **Property mapping**: robust logging of which property was queried.
> * **Dimensional consistency**: ensure properties have comparable schemas.

---

## 12. GA4 Semantic Translation

1. **Event Model Concepts**

   * Map sessions, users, events to GA4 fields:
     * "sessions" → `sessionStart`
     * "pageviews" → `pageViewEventCount`
     * "events" → `eventName` dimensions
2. **Alias Presentation**

   * Provide semantic aliases and examples from introspection in prompts.
   * Example: When user asks for "page visits", map to `screenPageViews`.
3. **Domain-Specific Mappings**

   * E-commerce: "purchases" → `transactions`, "revenue" → `totalRevenue`
   * Content: "articles viewed" → event with `eventName` = "page_view" + content dimension
4. **Terminology Standardization**

   * Documentation with standard vocabulary mapping to GA4 concepts.
   * LLM training to recognize common analytics terms.

> **Technical Concerns:**
>
> * **Conceptual drift**: GA4 event model differs from Universal Analytics.
> * **Business language**: map domain-specific terms to technical GA4 fields.

---

## 13. Data Fetch & Caching

1. **Batch Requests**

   * Coalesce multiple metrics into single `runReport` when user asks combined stats.
2. **Result Cache**

   * Key: `sha256(runReport_payload_string)`.
   * Store response JSON + `fetched_at` in SQLite table `ga4_report_cache`.
3. **Cache TTL & Invalidation**

   * Default TTL = 15 minutes; supports per-report override via CLI flag.
4. **Incremental Loading**

   * For sliding windows, detect cached ranges and fetch only missing dates, then merge.

> **Technical Concerns:**
>
> * **Cache consistency**: when metadata version changes, invalidate all dependent caches.
> * **Storage size**: prune old cache entries based on retention policy.

---

## 14. Result Processing & Transformation

1. **JSON → Pandas DataFrame**

   * Flatten nested rows; coerce metric types to numeric, dimensions to strings/datetimes.
2. **Derived Metrics & Post-Aggregation**

   * Compute percent changes, moving averages, ratio metrics using DataFrame methods.
3. **Attach Introspection Snapshots**

   * Embed sample rows or aggregation stats from `ga4_field_inspection` into DataFrame metadata.
4. **Error Handling**

   * Capture and surface GA4 API errors (quotaExceeded, invalidArgument) with actionable messages.

> **Technical Concerns:**
>
> * **Large result sets**: stream pages of data via `runReport` pagination; convert in chunks.
> * **Type mismatches**: enforce strict schema registry types to avoid runtime coercion errors.

---

## 15. Human-Readable Summaries

1. **Narrative Prompt**

   ```text
   Given the following DataFrame columns and a summary of its first few rows,
   write a concise analysis: {DataFrame.head().to_dict()}.
   ```
2. **LLM Generation**

   * Outputs plain-language summary, highlighting key trends, anomalies, or recommendations.
3. **Augmented with Introspection**

   * Preface summary with context: "Based on typical session lengths (~180s), your reported average of 210s is 17% higher."

> **Technical Concerns:**
>
> * **LLM hallucinations**: validate references (e.g. numeric statements) against DataFrame values.
> * **Prompt cost**: minimize size by sending only aggregated snapshots, not full raw data.

---

## 16. Advanced Embeddings & Cohort Search

1. **Segment Definition Embedding**

   * Extract GA4 segment definition JSON; embed via LLM.
   * Index in FAISS or Qdrant.
2. **Similarity Queries**

   * On user request ("find cohorts like premium subscribers"), embed query then NN search in segment index.
3. **Index Refresh**

   * Schedule nightly jobs to re-embed segments when GA4 definitions evolve.

> **Technical Concerns:**
>
> * **Data privacy**: ensure embedded segment definitions contain no PII.
> * **Index drift**: incorporate TTL and alerts if segment count changes unexpectedly.

---

## 17. Testing, Monitoring & Alerts

1. **Unit & Integration Tests**

   * Mock GA4 metadata and report endpoints; assert registry, FAISS, and cache are populated correctly.
2. **CI End-to-End Pipeline**

   * Use a GA4 demo property: full flow from `ga4:auth` → ingestion → translation → reporting → summary.
3. **Monitoring Dashboards**

   * Track ingestion success rates, API latencies, token-refresh failures, cache hit ratios.
4. **Alerting Rules**

   * Alert if >10% of translation prompts error, if metadata-sync fails >12 hours, or if API quota <10% remaining.

> **Technical Concerns:**
>
> * **Test environment parity**: ensure sandbox property mirrors production schema.
> * **Alert fatigue**: tune thresholds to balance noise vs coverage.

---

*End of GA4 Implementation Details.*
