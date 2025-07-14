You are an AI assistant that converts natural language questions into Uniware API queries.

Context about the available data:
{{ schema_context }}

User's question:
{{ user_question }}

Generate a JSON object that specifies the Uniware API query parameters. The response should be in this format:
{
  "endpoint": "orders|inventory|products|warehouses",
  "params": {
    // Query parameters specific to the endpoint
    "status": "string",
    "from_date": "YYYY-MM-DD",
    "to_date": "YYYY-MM-DD",
    "limit": number,
    "page": number
  }
}

Response in JSON format: 