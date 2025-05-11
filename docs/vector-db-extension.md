# Vector Database Adapter Pattern for On-Prem Data Analysis Agent

This document focuses on integrating vector stores—such as Qdrant, Pinecone, Milvus, and Chroma—into your existing adapter–orchestrator framework.

---

## 1. Overview

* **Goal:** Plug vector search capabilities into your on-prem agent the same way you did for relational and NoSQL stores.
* **Benefits:**

  * Reuse orchestration logic.
  * Encapsulate embedding + search in adapters.
  * Easily add new vector stores by implementing the same interface.

---

## 2. Common Adapter Interface (`DBAdapter`)

All vector adapters implement this interface:

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
        Convert natural-language prompt into a query:
        - Embedding vector + filter for vector stores.
        """
    
    @abstractmethod
    async def execute(self, query: Any) -> List[Dict]:
        """
        Run the vector search and return hits as list of dicts.
        """
```

---

## 3. QdrantAdapter Example

```python
# adapters/qdrant.py
from qdrant_client import QdrantClient
from adapters.base import DBAdapter
from typing import Any, Dict, List
import openai

class QdrantAdapter(DBAdapter):
    def __init__(self, conn_uri: str, collection_name: str, api_key: str = None):
        super().__init__(conn_uri)
        self.client = QdrantClient(url=conn_uri, api_key=api_key)
        self.collection = collection_name

    async def llm_to_query(self, nl_prompt: str) -> Dict[str, Any]:
        # 1. Embed the prompt
        resp = openai.Embedding.create(
            input=nl_prompt,
            model="text-embedding-ada-002"
        )
        vector = resp["data"][0]["embedding"]

        # 2. (Optional) Generate JSON filter via LLM
        filter_json = await call_openai_to_generate_json_filter(nl_prompt)

        return {"vector": vector, "top_k": 10, "filter": filter_json}

    async def execute(self, query: Dict[str, Any]) -> List[Dict]:
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=query["vector"],
            limit=query["top_k"],
            query_filter=query.get("filter")
        )
        return [{"id": h.id, "score": h.score, **h.payload} for h in hits]
```

---

## 4. PineconeAdapter Stub

```python
# adapters/pinecone.py
import pinecone
from adapters.base import DBAdapter
from typing import Any, Dict, List
import openai

class PineconeAdapter(DBAdapter):
    def __init__(self, conn_uri: str, index_name: str, api_key: str):
        super().__init__(conn_uri)
        pinecone.init(api_key=api_key, environment=conn_uri)
        self.index = pinecone.Index(index_name)

    async def llm_to_query(self, nl_prompt: str) -> Dict[str, Any]:
        embed = openai.Embedding.create(input=nl_prompt, model="text-embedding-ada-002")
        vector = embed["data"][0]["embedding"]
        filter_json = await call_openai_to_generate_json_filter(nl_prompt)
        return {"vector": vector, "top_k": 10, "filter": filter_json}

    async def execute(self, query: Dict[str, Any]) -> List[Dict]:
        resp = self.index.query(
            vector=query["vector"],
            top_k=query["top_k"],
            filter=query.get("filter")
        )
        return [{"id": m.id, "score": m.score, **m.metadata} for m in resp.matches]
```

---

## 5. MilvusAdapter Stub

```python
# adapters/milvus.py
from pymilvus import Collection
from adapters.base import DBAdapter
from typing import Any, Dict, List
import openai

class MilvusAdapter(DBAdapter):
    def __init__(self, conn_uri: str, collection_name: str):
        super().__init__(conn_uri)
        self.collection = Collection(collection_name, using="default")

    async def llm_to_query(self, nl_prompt: str) -> Dict[str, Any]:
        resp = openai.Embedding.create(input=nl_prompt, model="text-embedding-ada-002")
        vector = resp["data"][0]["embedding"]
        filter_json = await call_openai_to_generate_json_filter(nl_prompt)
        return {"vector": vector, "top_k": 10, "filter": filter_json}

    async def execute(self, query: Dict[str, Any]) -> List[Dict]:
        results = self.collection.search(
            data=[query["vector"]],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=query["top_k"],
            expr=query.get("filter")
        )
        return [{"id": r.id, "score": r.distance, **r.entity.get("payload")} for r in results[0]]
```

---

## 6. ChromaAdapter Stub

```python
# adapters/chroma.py
from chromadb import Client
from adapters.base import DBAdapter
from typing import Any, Dict, List
import openai

class ChromaAdapter(DBAdapter):
    def __init__(self, conn_uri: str, collection_name: str):
        super().__init__(conn_uri)
        self.client = Client(path=conn_uri)
        self.coll = self.client.get_collection(collection_name)

    async def llm_to_query(self, nl_prompt: str) -> Dict[str, Any]:
        resp = openai.Embedding.create(input=nl_prompt, model="text-embedding-ada-002")
        vector = resp["data"][0]["embedding"]
        return {"vector": vector, "top_k": 10}

    async def execute(self, query: Dict[str, Any]) -> List[Dict]:
        results = self.coll.query(query_embeddings=[query["vector"]], n_results=query["top_k"])
        hits = results["documents"][0]
        metas = results["metadatas"][0]
        return [{"id": metas[i].get("id"), "score": results["distances"][0][i], **metas[i]} for i in range(len(hits))]
```

---

## 7. Orchestrator Registration

```python
# orchestrator.py
from adapters.qdrant import QdrantAdapter
from adapters.pinecone import PineconeAdapter
from adapters.milvus import MilvusAdapter
from adapters.chroma import ChromaAdapter

ADAPTERS = {
    "qdrant": QdrantAdapter,
    "pinecone": PineconeAdapter,
    "milvus": MilvusAdapter,
    "chroma": ChromaAdapter,
}
```

---

## 8. Vector Search Workflow

1. **Normalize Query**: clean and preprocess input text.
2. **Embed**: use embedding model to generate `vector`.
3. **Generate Filter** (optional): LLM → JSON for metadata filter.
4. **Search**: call adapter’s `execute()`.
5. **Enrich**: fetch full records if needed.
6. **Format**: create human-readable snippets.
7. **Summarize** (optional): send to LLM for final narrative.
8. **Return**: present to user.

---

**With these vector adapters, your orchestrator supports semantic search across any vector store by simply implementing and registering new subclasses.**
