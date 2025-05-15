# Planning Agent vs. Implementation Agent

This document defines the architecture, responsibilities, and best practices for a two-agent system:

1. **Planning Agent (Thinker)**
2. **Implementation Agent (Doer)**

By cleanly separating concerns, we optimize for maintainability, auditability, and extensibility.

---

## 1. Agent Roles & Responsibilities

| Aspect               | Planning Agent (Thinker)                                                                                  | Implementation Agent (Doer)                                                                      |
| -------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Primary Goal**     | Generate a detailed, step-by-step plan (including code snippets) for fulfilling a user’s NL data query.   | Execute the plan: run queries, handle errors/retries, and return results in the expected format. |
| **Schema Awareness** | Reads and reasons over adapter-provided schema metadata; chooses relevant tables/collections and indices. | Receives concrete code blocks or commands; does *not* rediscover schema or plan logic.           |
| **Plan Artifacts**   | - High-level subgoals and stakeholder summary                                                             |                                                                                                  |

* Annotated pseudocode or real code snippets for each step             | - Executes snippets via appropriate clients/drivers (asyncpg, pymongo, FAISS search, Slack API, etc.)                 |
  \| **Error Handling**              | Assumes ideal execution; may suggest validation or dry-run steps.                                                           | Implements retries, backoff, timeouts; converts runtime errors into warnings or failures for upstream visibility.     |
  \| **User Visibility**             | Surface plan to users or domain experts for review, inline feedback, and audit.                                            | Operates behind-the-scenes; returns only final data payload and any plan-level warnings.                              |
  \| **Extensibility**               | Plug in new schema sources, ontologies, or stakeholder prompts without touching execution logic.                           | Swap out database clients, change drivers, or adjust concurrency limits without changing planning logic.               |
  \| **Performance Concerns**        | Focus on correctness, clarity, and completeness of steps rather than raw speed.                                             | Focus on parallelism, batching, streaming, and resource management.                                                   |

---

## 2. End-to-End Workflow Sketch

1. **User Query**:

   * “Show me total sales per VIP customer in February.”
2. **Planning Agent**:

   * **Stakeholder Analysis**: Identify Sales and Finance roles; note compliance filters.
   * **Subgoal Decomposition**:

     * Gather schema summaries.
     * Identify VIP customers.
     * Aggregate order data for given date range.
     * Format results.
   * **Generated Plan** (YAML + code snippets):

     ```yaml
     plan_id: 67890
     stakeholders:
       - Sales: needs per-customer totals
       - Finance: needs audit log of filters
     steps:
       - step: Load customer schema
         code: |
           customers_schema = await doer.get_schema('postgres', 'customer_table')
       - step: Find VIP IDs
         code: |
           vip_ids = await doer.run(
             "SELECT id FROM customer_table WHERE tier = 'VIP'"
           )
       - step: Sum February orders
         code: |
           sales = await doer.run(
             "SELECT customer_id, SUM(amount) AS total "
             "FROM orders WHERE date >= '2025-02-01' AND date < '2025-03-01' "
             "AND customer_id IN :vip_ids GROUP BY customer_id"
           )
       - step: Return JSON
         code: |
           return {'sales_by_customer': sales}
     ```
3. **Review (Optional)**: Stakeholders or user adjust date or filters in the plan.
4. **Implementation Agent** (Doer):

   * Loads plan.
   * Iterates through each step’s `code` block.
   * Executes via correct adapter, handling retries and timeouts.
   * Streams intermediate results if configured.
   * Assembles final JSON and returns to user.

---

## 3. Techniques for an Optimal Planning Agent

1. **Deep Stakeholder Analysis**

   * Prompt: “List all roles impacted, their data needs, constraints, and security/privacy requirements.”
2. **Schema-Centric Prompting**

   * Include a concise schema summary (field names/types, permissions) for each source.
3. **Hierarchical Task Decomposition**

   * First outline subgoals; then expand each into code-level actions using chain-of-thought.
4. **Validation Checkpoints**

   * After each step, self-check alignment with stakeholder needs and schema constraints.
5. **Domain Ontologies & Glossaries**

   * Ground plans in real-world entities (e.g., Customer, Order, Revenue).
6. **Template & Snippet Libraries**

   * Reuse vetted code templates for common patterns (aggregations, vector searches).
7. **Interactive Human-in-the-Loop Feedback**

   * Expose plan for expert review; re-ingest edits automatically.
8. **Progressive Refinement Passes**

   * Multiple planning passes: outline → detail → polish.
9. **Dry-Run & Simulation**

   * Run EXPLAIN or metadata-only calls to catch plan errors early.
10. **Explainability & Annotation**

* Annotate code blocks with rationale for auditability (e.g., “-- Filter by compliance clause”).

---

## 4. Summary of Responsibilities

* **Planning Agent**: Thinks, reasons, and generates a clear, validated roadmap with code snippets. Focuses on *what* and *why*.
* **Implementation Agent**: Executes steps reliably, manages *how* (performance, errors, streaming), and returns data. Focuses on *execution details*.

---

*End of planning-agent spec.*
