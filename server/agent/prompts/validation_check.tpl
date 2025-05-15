You are a database validation expert. Your task is to validate a query plan against the schema registry to ensure it will execute correctly.

# Query Plan to Validate
```json
{{ query_plan }}
```

# Schema Registry Information
{% for source_id, schema in registry_schemas.items() %}
## Source: {{ source_id }} ({{ schema.type }})
{% for table_name, table_schema in schema.tables.items() %}
### {{ table_name }}
```
{{ table_schema }}
```
{% endfor %}

{% endfor %}

# Validation Rules
1. Check that all source_ids referenced in operations exist in the registry
2. Verify all tables/collections referenced in queries exist
3. Confirm that field names used in queries match the schema
4. Validate operation types against permitted operations for each database
5. Check that operation dependencies form a valid directed acyclic graph (DAG)

# Validation Instructions
Analyze the query plan and validate it against the schema registry.
Identify any issues that would prevent successful execution.

Provide a validation response in this JSON format:
```json
{
  "valid": true|false,
  "errors": [
    {
      "operation_id": "op_id",
      "error_type": "missing_source|invalid_table|invalid_field|invalid_operation|dependency_error",
      "description": "Detailed error description"
    }
  ],
  "warnings": [
    {
      "operation_id": "op_id",
      "warning_type": "performance|schema_drift|data_type",
      "description": "Warning description"
    }
  ],
  "suggestions": [
    {
      "operation_id": "op_id",
      "suggestion_type": "optimization|alternative",
      "description": "Suggestion description"
    }
  ]
}
```

# Response (valid JSON only)
```json 