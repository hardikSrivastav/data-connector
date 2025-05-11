# Qdrant Vector Database Initialization

This directory contains scripts to initialize a Qdrant vector database with sample corporate data for demonstration and testing purposes.

## Collections

The initialization creates three collections that model common enterprise use cases for vector search:

1. **corporate_knowledge**: A document repository containing corporate knowledge base articles, policies, and documents from various departments
2. **product_catalog**: A product catalog with vector search capabilities for semantic product discovery
3. **customer_support**: A collection of customer support tickets and queries for semantic search

## Data Structure

### Corporate Knowledge Collection

Documents have the following metadata:
- `title`: Document title
- `content`: Document content
- `department`: Department that owns the document (Engineering, Finance, HR, etc.)
- `document_type`: Type of document (Policy, Procedure, Handbook, Report, etc.)
- `created_at`: Creation timestamp

### Product Catalog Collection

Products have the following metadata:
- `name`: Product name
- `sku`: Stock keeping unit identifier
- `category`: Product category
- `manufacturer`: Manufacturer name
- `price`: Price as a float
- `in_stock`: Boolean indicating stock status
- `description`: Product description

### Customer Support Collection

Support queries have the following metadata:
- `query_text`: The actual support query
- `category`: Query category (Technical, Billing, Account, etc.)
- `product`: Related product
- `resolved`: Boolean indicating resolution status
- `created_at`: Creation timestamp
- `resolved_at`: Resolution timestamp (if resolved)
- `customer`: Customer information
- `full_text`: Complete ticket text

## Usage with Vector Search

These collections are ideal for testing vector search capabilities, including:

1. **Semantic search**: Finding documents/products/queries by meaning instead of keywords
2. **Filtered vector search**: Combining vector similarity with metadata filtering
3. **Recommendations**: Finding similar products or documents

## Example Queries

Using the Python client:

```python
from qdrant_client import QdrantClient
import openai

# Connect to Qdrant
client = QdrantClient(host="localhost", port=7000)

# Get embedding for query
response = openai.Embedding.create(
    input="How to configure security settings",
    model="text-embedding-ada-002"
)
vector = response.data[0].embedding

# Search with filter
results = client.search(
    collection_name="corporate_knowledge",
    query_vector=vector,
    limit=5,
    query_filter={
        "must": [
            {"key": "department", "match": {"value": "Engineering"}}
        ]
    }
)
```

## Technical Implementation

The initialization script:
1. Creates the collections with appropriate schema
2. Generates sample data with random embedding vectors
3. Creates indexes for efficient filtering
4. Populates all collections with batch uploading

The data volumes are:
- Corporate Knowledge: 500 documents
- Product Catalog: 200 products
- Customer Support: 300 tickets 