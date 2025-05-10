# Adapter–Orchestrator Pattern for Extensible On‑Prem Data Analysis Agent

This document outlines a robust, extensible pattern to integrate multiple databases (Postgres, MongoDB, Firebase, etc.) into your on‑prem data analysis agent without modifying your existing Postgres implementation.

---

## 1. Overview

* **Goal:** Provide a single API (`Orchestrator`) that routes natural‑language queries via LLMs to any supported database, executes the generated queries on‑prem, and returns uniform results.
* **Key Benefits:**

  * **Separation of concerns:** DB‑specific logic lives in adapters.
  * **Extensibility:** Add new stores by writing new adapters only.
  * **Stability:** Your existing Postgres code remains untouched.

---

## 2. High‑Level Architecture

```text
┌────────────────┐        ┌──────────────┐        ┌───────────┐
│   User prompt  │ ──▶    │ Orchestrator │ ──▶    │  Adapter  │ ──▶   DB
│  (“show me…”)  │        │   (router)   │        │ (Postgres,│       (Postgres,
└────────────────┘        └──────────────┘        │  Mongo,   │       Mongo, …)
                                                   │  Firebase)│
                                                   └───────────┘
```

1. **User prompt**: Natural‑language question sent to your agent.
2. **Orchestrator**: Inspects the connection URI, picks the correct `Adapter`, then calls:

   1. `adapter.llm_to_query(nl_prompt)` → DB‑specific query representation.
   2. `adapter.execute(query)` → Executes on‑prem, returns list of dicts.
3. **Adapter**: Translates intent to query + executes it.

---

## 3. Common Adapter Interface

Create a base interface that all adapters must implement.

```python
# adapters/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class DBAdapter(ABC):
    def __init__(self, conn_uri: str):
        self.conn_uri = conn_uri

    @abstractmethod
    async def llm_to_query(self, nl_prompt: str) -> Any:
        """
        Convert natural‑language prompt into a DB‑specific query format.
        e.g. SQL string, MongoDB aggregation pipeline (list of dicts), etc.
        """
        pass

    @abstractmethod
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute the DB query on‑prem and return results as list of dicts.
        """
        pass
```

---

## 4. Existing PostgresAdapter (Unchanged)

```python
# adapters/postgres.py
import asyncpg
from adapters.base import DBAdapter

class PostgresAdapter(DBAdapter):
    async def llm_to_query(self, nl_prompt: str) -> str:
        # Your existing logic to call OpenAI and generate SQL
        return await call_openai_to_generate_sql(nl_prompt)

    async def execute(self, sql: str) -> list[dict]:
        conn = await asyncpg.connect(self.conn_uri)
        rows = await conn.fetch(sql)
        await conn.close()
        return [dict(r) for r in rows]
```

> **Note:** Leave this file as‑is. All new adapters follow the same pattern.

---

## 5. New: MongoAdapter

```python
# adapters/mongo.py
from pymongo import MongoClient
from adapters.base import DBAdapter

class MongoAdapter(DBAdapter):
    def __init__(self, conn_uri: str, db_name: str):
        super().__init__(conn_uri)
        self.client = MongoClient(conn_uri)
        self.db = self.client[db_name]

    async def llm_to_query(self, nl_prompt: str) -> list:
        """
        Prompt the LLM to output a MongoDB aggregation pipeline JSON array.
        E.g.:
        [
          {"$match": {"status": "active"}},
          {"$group": {"_id": "$region", "count": {"$sum": 1}}},
        ]
        """
        pipeline_json = await call_openai_to_generate_mongo_pipeline(nl_prompt)
        return pipeline_json

    async def execute(self, pipeline: list) -> list[dict]:
        # You may infer or parameterize the collection name
        coll = self.db.get_collection("your_collection")
        return list(coll.aggregate(pipeline))
```

> **Prompt Tip:**
> "Output only a valid MongoDB aggregation pipeline (JSON array) for this intent…"

---

## 6. Orchestrator & Registry

The orchestrator inspects the URI scheme and instantiates the correct adapter.

```python
# orchestrator.py
from adapters.postgres import PostgresAdapter
from adapters.mongo    import MongoAdapter

ADAPTERS = {
    "postgres": PostgresAdapter,
    "mongodb":  MongoAdapter,
    # add more as you implement…
}

class Orchestrator:
    def __init__(self, conn_uri: str, **kwargs):
        scheme = conn_uri.split('://', 1)[0]
        AdapterCls = ADAPTERS.get(scheme)
        if not AdapterCls:
            raise ValueError(f"No adapter for scheme '{scheme}'")
        self.adapter = AdapterCls(conn_uri, **kwargs)

    async def run(self, nl_prompt: str) -> list[dict]:
        query = await self.adapter.llm_to_query(nl_prompt)
        return await self.adapter.execute(query)
```

* **Adding new stores**: Implement `ElasticsearchAdapter`, `FirebaseAdapter`, etc., following `DBAdapter`.
* **Minimal changes**: Only update `ADAPTERS` registry.

---

## 7. LLM Tool Integration Example (LangChain)

```python
from langchain.agents import Tool, initialize_agent
from orchestrator import Orchestrator

async def run_agent(conn_uri: str, user_input: str):
    orchestrator = Orchestrator(conn_uri, db_name="mydb")
    tools = [
      Tool(
        name="query_db",
        func=orchestrator.run,
        description="Use this to query your on‑prem database."
      )
    ]
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
    return await agent.run(user_input)
```

* **Single generic tool** (`query_db`) simplifies prompt design.
* **Future extension**: Register multiple tools if you need per‑adapter distinctions.

---

## 8. Adding Future Adapters

1. **Create** `MyNewStoreAdapter(DBAdapter)` in `adapters/mynewstore.py`.
2. **Implement** `llm_to_query` & `execute`.
3. **Register** in `ADAPTERS` with the URI scheme (e.g. `"firestore"`).

You never touch `PostgresAdapter` or core orchestrator logic again.

---

## 9. Summary

* **Adapter pattern** cleanly isolates DB‑specific code.
* **Orchestrator** handles routing based on URI.
* **LLM prompts** target each adapter’s expected query DSL (SQL, Mongo pipelines, etc.).
* **Extensible**: Add new NoSQL or search engines by dropping in new adapter classes.

With this pattern, your on‑prem agent scales to any data store without altering your battle‑tested Postgres code. Happy querying!
