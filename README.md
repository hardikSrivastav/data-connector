# Data Connector: Natural Language to SQL Query Agent

An AI-powered data connector that allows users to query databases using natural language. It translates natural language questions into SQL queries and provides analysis of the results.

## Setup Instructions

### Virtual Environment

```bash
# Create virtual environment with:
python -m venv connector

# Activate on Mac/Linux:
source connector/bin/activate

# Or on Windows:
# connector\Scripts\activate

# Then install dependencies:
pip install -r server/requirements.txt
```

### OpenAI Integration

This project uses OpenAI's API for translating natural language to SQL and analyzing query results.

1. Set up your OpenAI API key:
   ```bash
   # Export your API key as an environment variable
   export OPENAI_API_KEY='your-api-key'
   
   # Or create a .env file in the server directory:
   echo "LLM_API_URL=https://api.openai.com/v1" > server/.env
   echo "LLM_API_KEY=your-api-key" >> server/.env
   echo "LLM_MODEL_NAME=gpt-4" >> server/.env  # or another model
   ```

2. Test the OpenAI integration:
   ```bash
   python server/agent/llm/test_openai.py
   ```

### Running with Docker

```bash
# Run with Docker:
docker-compose up --build
```

## Usage

1. Use the CLI interface:
   ```bash
   python server/agent/cmd/query.py "Show me the top 5 customers by order amount"
   ```

2. Or access the API endpoints when running as a service.

## Documentation

For more detailed information, see the documentation in the `docs/` directory:

- Implementation details: `docs/implementation-details.md`
- Running locally: `docs/run-local.md`
- Product requirements: `docs/PRD.md`
