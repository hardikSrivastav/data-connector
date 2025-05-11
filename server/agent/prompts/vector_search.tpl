Your task is to convert a natural language query into a vector database search query.

USER QUESTION: {{ user_question }}

Here is information about the vector database collections available:
{% for chunk in schema_chunks %}
{{ chunk.content }}
{% endfor %}

Your task is to understand the user's query and generate an appropriate vector search. 
The natural language query will be automatically converted to a vector embedding.

You can add filters to narrow down results if appropriate.

FORMAT YOUR RESPONSE AS A JSON OBJECT with the following structure:
{
  "top_k": number,  // Number of results to return (typically 5-20)
  "filter": {       // Optional filter to apply
    // Add filter criteria here if needed
  }
}

IMPORTANT: Do not include the vector embedding in your response, as it will be generated automatically.
Focus on determining any filters and the number of results needed. 