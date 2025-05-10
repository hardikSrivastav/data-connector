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

### Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env-example .env
   ```

2. Update the `.env` file with your specific configuration:
   - Database credentials
   - OpenAI API key
   - Redis settings (if using)

### OpenAI Integration

This project uses OpenAI's API for translating natural language to SQL and analyzing query results.

1. Set up your OpenAI API key:
   ```bash
   # Export your API key as an environment variable
   export OPENAI_API_KEY='your-api-key'
   
   # Or add it to your .env file:
   echo "LLM_API_KEY=your-api-key" >> .env
   ```

2. Test the OpenAI integration:
   ```bash
   python server/agent/llm/test_openai.py
   ```

### Git Setup

The project includes a comprehensive `.gitignore` file to prevent sensitive information and large files from being committed to the repository. If you've already committed sensitive files, use the cleanup script:

```bash
# Run the cleanup script to remove sensitive files from git tracking
./cleanup_git.sh

# Then commit the changes
git commit -m "Remove sensitive and large files from git tracking"
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

### Using Large Views

For testing with large datasets, the project includes virtual views that simulate large amounts of data:

```bash
# Check schema for large views:
python -m server.agent.cmd.query check-schema

# Run a query explicitly specifying large views:
python -m server.agent.cmd.query "What are the top 10 customers by total order amount using the large_orders_view and large_users_view?" --orchestrate
```

## Documentation

For more detailed information, see the documentation in the `docs/` directory:

- Implementation details: `docs/implementation-details.md`
- Running locally: `docs/run-local.md`
- Product requirements: `docs/PRD.md`
