#!/usr/bin/env python
import asyncio
import os
import sys
import json
import logging

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from server.agent.llm.client import get_llm_client, OpenAIClient
from server.agent.config.settings import Settings

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_sql_generation():
    """Test SQL generation with OpenAI"""
    try:
        # Get LLM client
        llm = get_llm_client()
        
        # Sample schema information and user question
        sample_prompt = """
        You are a database expert tasked with translating natural language questions into SQL queries.
        
        Your task is to:
        1. Analyze the provided database schema information
        2. Generate a SQL query that correctly answers the user's question
        3. Return ONLY the SQL query without explanation or commentary
        
        # Database Schema Information
        Table: users
        Columns:
        - id (integer, primary key)
        - username (varchar)
        - email (varchar)
        - created_at (timestamp)
        - is_active (boolean)
        
        Table: orders
        Columns:
        - id (integer, primary key)
        - user_id (integer, foreign key references users.id)
        - amount (numeric)
        - created_at (timestamp)
        - status (varchar)
        
        # User Question
        Show me the top 5 users with the highest total order amount
        
        # SQL Query
        """
        
        # Generate SQL
        sql = await llm.generate_sql(sample_prompt)
        logger.info(f"Generated SQL:\n{sql}")
        
        # Test result analysis
        sample_data = [
            {"username": "john_doe", "total_amount": 1250.50},
            {"username": "jane_smith", "total_amount": 975.25},
            {"username": "bob_jones", "total_amount": 820.00},
            {"username": "alice_wonder", "total_amount": 750.75},
            {"username": "charlie_brown", "total_amount": 685.30}
        ]
        
        logger.info("Testing result analysis...")
        analysis = await llm.analyze_results(sample_data)
        logger.info(f"Analysis:\n{analysis}")
        
        logger.info("Tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error testing OpenAI integration: {str(e)}")
        return False

def setup_env_vars():
    """Set up environment variables for testing if not already set"""
    if not os.environ.get("LLM_API_URL"):
        os.environ["LLM_API_URL"] = "https://api.openai.com/v1"
    
    # Check if API key is set
    if not os.environ.get("LLM_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        api_key = input("Enter your OpenAI API key: ").strip()
        os.environ["LLM_API_KEY"] = api_key
    elif os.environ.get("OPENAI_API_KEY") and not os.environ.get("LLM_API_KEY"):
        # If OPENAI_API_KEY is set but LLM_API_KEY is not, use OPENAI_API_KEY
        os.environ["LLM_API_KEY"] = os.environ.get("OPENAI_API_KEY")
    
    # Set model name if not set
    if not os.environ.get("LLM_MODEL_NAME"):
        os.environ["LLM_MODEL_NAME"] = "gpt-4" # or whatever model you prefer
    
    logger.info(f"Using LLM API URL: {os.environ.get('LLM_API_URL')}")
    logger.info(f"Using LLM model: {os.environ.get('LLM_MODEL_NAME')}")

if __name__ == "__main__":
    setup_env_vars()
    success = asyncio.run(test_sql_generation())
    sys.exit(0 if success else 1) 