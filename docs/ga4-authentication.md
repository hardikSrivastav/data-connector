# GA4 Authentication & Implementation for Ceneca Agent

This document captures the full discussion on Google Analytics 4 (GA4) authentication and implementation in the on‑prem data-analysis agent (“Ceneca”). It covers both **authentication flows** (service-account vs user-consent OAuth) and the **moving parts** of the GA4 adapter.

---

## 1. High-Level GA4 Adapter Architecture

1. **Authentication & Credentials**

   * Service-account JSON key (for headless, per-application access)
2. **API Client Layer**

   * Wrapped Google Analytics Data API v1 (`google-analytics-data` SDK)
   * Rate-limit handling, batching, retry logic
3. **Schema Registry Integration**

   * Fetches GA4 dimensions/metrics metadata on first run
   * Persists to SQLite with versioning and user-defined aliases
4. **Query Translation**

   * LLM-driven NL→GA4 `runReport` payloads
   * Date-range normalization (relative → absolute, honoring Asia/Kolkata timezone)
5. **Data Fetch & Caching**

   * SQLite-backed result cache with TTL (default 15 minutes)
   * Incremental updates for rolling date ranges
6. **Result Processing**

   * JSON → Pandas DataFrame conversion
   * Derived metrics & post-aggregation in DataFrame
7. **Human-Readable Summaries**

   * Feed DataFrame into LLM to generate narratives (e.g. “Users in India grew by 12%.”)
8. **(Advanced) Embeddings & Vector Search**

   * Embed GA4 segments/properties into FAISS/Qdrant for similarity queries
9. **Testing & Monitoring**

   * HTTP replay fixtures, end-to-end CI tests, schema-registry validation
   * Structured logs, sampling alerts, usage metrics

---

## 2. Authentication Flows

### 2.1 Service-Account (Recommended for On‑Prem)

1. **Config File (****`config.yaml`****)**

   ```yaml
   ga4:
     key_file: /etc/data-connector/credentials/ga4-service-account.json
     property_id: 123456789
     scopes:
       - https://www.googleapis.com/auth/analytics.readonly
     token_cache_db: /var/lib/data-connector/ga4_tokens.sqlite  # optional
   ```
2. **Service Account Setup (Customer Responsibilities)**

   * Create SA in GCP with `Analytics Data Viewer` role
   * Download JSON key → `/etc/data-connector/credentials/ga4-service-account.json`
   * Secure with OS permissions (`chmod 640`, owner `root:data-connector`)
3. **Adapter Code Snippet**

   ```python
   from google.oauth2 import service_account
   from google.auth.transport.requests import Request

   # Load credentials
   creds = service_account.Credentials.from_service_account_file(
       config.ga4.key_file,
       scopes=config.ga4.scopes,
   )
   # Exchange JWT for access token
   creds.refresh(Request())
   token, expiry = creds.token, creds.expiry
   # (Optional) Persist token & expiry in SQLite for reuse
   ```
4. **Token Lifecycle**

   * Refresh when `expiry < now + buffer`
   * Cached tokens avoid redundant JWT exchanges
5. **Network & Access Control**

   * Agent deployed inside corporate VPN/SSO perimeter
   * Only on‑prem hosts can reach GA4 API via service account

### 2.2 User‑Consent OAuth (Per‑User)

1. **CLI Command**

   ```bash
   data-connector ga4 auth
   ```
2. **Browser Redirect Flow**

   * CLI spins up HTTP listener on `localhost:PORT` or prompts a code
   * Opens:

     ```text
     https://accounts.google.com/o/oauth2/v2/auth?
       client_id=<CLIENT_ID>&
       redirect_uri=http://localhost:PORT/callback&
       response_type=code&
       scope=https://www.googleapis.com/auth/analytics.readonly&
       state=<RANDOM>
     ```
3. **Token Exchange & Storage**

   * Exchange `code` for `{ access_token, refresh_token, expires_in }`
   * Persist to `~/.data-connector/ga4_credentials.json`:

     ```json
     {
       "access_token": "...",
       "refresh_token": "...",
       "expiry": "2025-05-17T21:15:00+05:30",
       "scopes": ["analytics.readonly"]
     }
     ```
4. **Adapter Usage**

   * On each call: load JSON, check expiry, refresh if needed, then hit GA4 API
5. **Use Cases**

   * When per-user data permissions matter
   * When service account isn’t allowed by org policy

---

## 3. Customer vs. Platform Responsibilities

| Responsibility                    | Customer (Data Admin)                                   | Platform Creator (You)               |
| --------------------------------- | ------------------------------------------------------- | ------------------------------------ |
| GA4 Service-Account creation      | Creates SA in their GCP project                         | Provides docs / Terraform snippets   |
| IAM Role binding                  | Grants `roles/analytics.dataViewer` to SA               | —                                    |
| JSON Key download & placement     | Puts file at path in `config.yaml`                      | —                                    |
| Key rotation & vault integration  | Rotates keys on their cadence, manages in Vault if used | —                                    |
| `config.yaml` guidance            | Updates `ga4.key_file`, `property_id`, `scopes`         | Supplies sample `config.yaml` schema |
| Adapter development & maintenance | —                                                       | Loads credentials, manages tokens    |

---

## 4. Optional Onboarding Helpers

1. **Terraform Example**

   ```hcl
   resource "google_service_account" "ga4" {
     account_id   = "data-connector-ga4"
     display_name = "Data Connector GA4 Reader"
   }
   resource "google_project_iam_member" "ga4_viewer" {
     project = var.project_id
     role    = "roles/analytics.dataViewer"
     member  = "serviceAccount:${google_service_account.ga4.email}"
   }
   ```
2. **CLI Wizard**

   ```bash
   data-connector ga4 init \
     --project my-gcp-project \
     --property 123456789 \
     --output /etc/data-connector/credentials/ga4-service-account.json
   ```

---

*End of **`ga4-authentication.md`**.*
