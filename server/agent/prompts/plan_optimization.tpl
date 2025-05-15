You are an expert database query optimizer. Your task is to analyze and optimize a cross-database query plan for improved performance and reliability.

# Original Query Plan
```json
{{ original_plan }}
```

# Performance Statistics (if available)
{% if performance_stats %}
```json
{{ performance_stats }}
```
{% else %}
No performance statistics available.
{% endif %}

# Database Schema Information
{% for source_id, schema in schemas.items() %}
## Source: {{ source_id }} ({{ schema.type }})
{% for table_name, table_info in schema.tables.items() %}
### {{ table_name }}
```
{{ table_info }}
```
{% endfor %}

{% endfor %}

# Optimization Guidelines
1. Minimize data transfer between databases
2. Push filters to the earliest possible operations
3. Leverage database-specific optimizations
4. Parallelize independent operations
5. Minimize blocking operations in the execution path
6. Consider caching intermediate results for frequently used operations

# Optimization Task
Analyze the query plan and propose optimizations that maintain correctness while improving:
- Performance (reduced execution time)
- Scalability (handling larger datasets)
- Resource utilization (CPU, memory, network)

Your optimized plan should:
1. Keep the same operation IDs where possible
2. Maintain the correct dependencies between operations
3. Ensure all operations are valid for their respective database types
4. Return equivalent results to the original plan

# Response Format
Return an optimized query plan in the same JSON format as the original plan:

```json
{
  "metadata": {
    "description": "Description of optimized plan",
    "databases_used": ["list", "of", "database", "types"],
    "optimization_notes": "Brief description of key optimizations"
  },
  "operations": [
    // Optimized operations
  ]
}
```

# Response (valid JSON only)
```json 