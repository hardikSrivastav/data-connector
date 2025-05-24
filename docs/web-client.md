## 1. High-Level Architecture

```
┌────────────┐        HTTPS          ┌───────────────────┐
│  Analyst   │ ←—[1]→ Login & Query  │  admin.ceneca.ai  │
│  (Browser) │                       │   (Cloud Portal)  │
└────────────┘                       └───────────────────┘
                                          │   ▲
         ┌────────────────────────────────┘   │
         │  Secure mTLS Tunnel (outbound)  │
         ▼                                  │
┌─────────────────┐   Local Network/Tunnel ┌─┴─────────────────┐
│  on-prem “Edge” │ ────Persistent mTLS───▶ │  Ceneca Agent   │
│  Connector      │                         │  (Docker/K8s)   │
└─────────────────┘                         └─────────────────┘
```

1. **Analyst** logs into `admin.ceneca.ai` via SSO.
2. **Portal** verifies identity, loads that user’s roles/permissions, and looks up which on-prem agent (“Connector”) is registered for their company.
3. The **Connector** (a tiny agent you install once on-prem) maintains a persistent, mutual-TLS–encrypted outbound connection to the portal—so no firewall holes need opening.
4. When the analyst issues a query, the portal sends it over that secure channel to the on-prem Ceneca Agent, which runs the query locally and streams results back to the portal.
5. Results are displayed in the browser UI—no local installs, everything happens in the cloud UI, but data never leaves the company network unencrypted.

---

## 2. Identity Management (SSO)

1. **Choose an IdP**

   * Pick SAML or OpenID Connect (OIDC)–compliant IdP your enterprise already uses (Okta, Azure AD, Keycloak, Google Workspace, etc.).
2. **Register the Portal as an OIDC Client**

   * In your IdP, create a new application:

     * Redirect URI: `https://admin.ceneca.ai/oauth/callback`
     * Allowed scopes: `openid email profile groups` (or equivalent).
3. **Implement the OIDC Flow in admin.ceneca.ai**

   * Use a standard library (e.g. `passport.js` or `openid-client` in Node, or your framework’s OIDC plugin).
   * On successful login, extract the user’s unique ID (`sub`), email, and group/role claims.
4. **Map IdP Groups → Ceneca Roles**

   * In your portal’s minimal metadata store (see §5), map groups like `HR-Analyst` or `Finance-Manager` to Ceneca roles (`hr_read`, `finance_read`, etc.).

---

## 3. Secure Connector vs. Direct Inbound

We have two main options for connecting your on-prem agent to the cloud portal:

| Option                    | Pros                                                    | Cons                                                          |
| ------------------------- | ------------------------------------------------------- | ------------------------------------------------------------- |
| **A. Exposed HTTPS**      | Simpler (portal talks directly to agent)                | Requires inbound firewall rules or VPN; higher attack surface |
| **B. Outbound Connector** | Most secure (agent initiates a tunnel); zero open ports | Slightly more complex initial setup                           |

> **Recommendation:** **Option B** (Outbound Connector)
>
> * **Security:** No need to punch firewall holes.
> * **Speed:** Persistent TLS tunnel (low latency).
> * **Ease:** A single “install and run” step for your IT team.

**How it works:**

* You install a lightweight Connector on-prem (e.g. a small Go or Python service).
* It authenticates with the portal using a client certificate or long-lived token.
* It establishes a **gRPC or WebSocket** over mTLS back to `admin.ceneca.ai`.
* The portal keeps that connection alive; when there’s a query, it is forwarded instantly over the same channel.

---

## 4. Authorization & Row-Level Security

1. **Portal-side Authorization**

   * After OIDC login, your portal keeps a session cookie with the user’s roles.
   * On each incoming query request, verify the user’s role (e.g. `finance_read`) matches the resource they’re querying.

2. **Database Enforcement**

   * **Postgres Row-Level Security (RLS):**

     * Create RLS policies on each table:

       ```sql
       ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
       CREATE POLICY hr_policy ON employees
         FOR SELECT
         USING ( current_setting('ceneca.user_role') = 'hr_read' );
       ```
     * The Connector, before running any query, sets `SET LOCAL ceneca.user_role = '<user-role>';`.
     * Postgres will then automatically filter rows based on your policy.
   * **MongoDB & Others:**

     * Wrap queries in a filter object:

       ```js
       // e.g., if user_role==='finance_read'
       const queryFilter = { department: 'finance' };
       db.collection('invoices').find(queryFilter);
       ```
     * The Connector injects these filters based on the user’s role.

3. **Table-Level Fallback**

   * If RLS is too complex, you can enforce at the Connector layer:

     * Maintain a map: `role → allowed_tables`.
     * Reject any query referencing disallowed tables before execution.

---

## 5. Minimal, Secure Metadata Storage

You only need to store **three pieces** of metadata per company:

1. **Company ID** (e.g. `acme-corp`)
2. **Connector Credentials** (client certificate public-key or a long-lived token).
3. **Role Mappings** (which IdP groups map to which Ceneca roles).

> **Where to store it:**
>
> * A small, encrypted database (Postgres, MySQL, or even SQLite) in your cloud portal.
> * **Encryption at Rest:** Use AWS KMS or HashiCorp Vault to encrypt the entire database or column-level encryption for the credentials.
> * **Access Controls:** Only the portal service account should have decryption rights.

You **never** store:

* Raw database credentials of your customers.
* Any PII beyond corporate ID or group names.

---

## 6. End-to-End Flow

1. **Connector Setup (one-time)**

   * IT admin on-prem installs Connector:

     ```bash
     curl -fsSL https://download.ceneca.ai/connector.sh | bash
     ceneca-connector register \
       --portal https://admin.ceneca.ai \
       --company-id acme-corp \
       --tls-cert /etc/ceneca/connector.crt \
       --tls-key /etc/ceneca/connector.key
     systemctl start ceneca-connector
     ```
   * Connector establishes mTLS to the portal and registers itself.

2. **Admin Portal Configuration**

   * Portal admin logs into `admin.ceneca.ai` (with OIDC).
   * Under **“Integrations”**, they see a pending request from `acme-corp` connector.
   * They approve it and map IdP groups → Ceneca roles.

3. **User Login & Query**

   * Business Analyst visits `admin.ceneca.ai`, clicks “Login”.
   * SSO kicks in; user is redirected back with a session cookie.
   * Analyst types a natural-language question in the UI.
   * Portal checks:

     * Is user’s role allowed to ask this question?
     * Which Connector is registered for this company?
   * Portal serializes the request over the **persistent TLS tunnel** to the Connector.

4. **On-Prem Execution**

   * Connector receives the request, extracts user role, and:

     * For Postgres: runs `SET LOCAL ceneca.user_role = '<role>'`
     * Executes the generated SQL/adapter logic
   * Streams results back over the same TLS channel.

5. **Results Display**

   * Portal presents the results in a friendly UI (table, chart, or narrative).
   * Analyst sees live insights—no local installs or direct DB access required.

---

## 7. Implementation Roadmap

1. **Build the Connector**

   * gRPC server in Python/Go that:
   * Initiates an mTLS connection to `admin.ceneca.ai:443`.
   * Listens for `QueryRequest { user_id, role, query_nl }`.
   * Sets up DB connections per `config.yaml`.
   * Executes with RLS or filters.
   * Returns `QueryResponse { data, logs }`.
2. **Extend the Portal**

   * Add OIDC login flow.
   * Create **Connector registration** UI & API (approve/deny).
   * Map IdP groups → Ceneca roles.
   * Persist minimal metadata in encrypted store.
   * Maintain WebSocket/mTLS listener for incoming Connector connections.
   * Forward user queries to the correct Connector session.
3. **Enforce Authorization**

   * On each query: check session → roles → allowed tables/rows.
   * Reject unauthorized requests with HTTP 403.
4. **Test & Iterate**

   * Pilot with one department (e.g. HR).
   * Validate RLS policies in Postgres.
   * Measure latency end-to-end (should be <200 ms for typical queries).
5. **Rollout**

   * Document for enterprise IT: one-liner install script.
   * Developer docs for IdP setup.
   * Training for business analysts on the portal UI.

---

By following this design, you achieve **security (no inbound ports, mTLS, RLS)**, **speed (persistent connections, local execution)**, and **ease of setup (one installer, zero client installs for analysts)**—all critical for non-technical users and SOC2 compliance.
