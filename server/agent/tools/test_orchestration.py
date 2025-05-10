#!/usr/bin/env python
import asyncio
import os
import sys
import json
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from server.agent.llm.client import get_llm_client
from server.agent.config.settings import Settings
from server.agent.tools.tools import DataTools
from server.agent.tools.state_manager import StateManager
from server.agent.meta.ingest import ensure_index_exists

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_orchestration():
    """Test the orchestrated analysis functionality"""
    try:
        # Set up environment for OpenAI API if not already set
        if not os.environ.get("LLM_API_URL"):
            os.environ["LLM_API_URL"] = "https://api.openai.com/v1"
        
        if not os.environ.get("LLM_API_KEY") and os.environ.get("OPENAI_API_KEY"):
            os.environ["LLM_API_KEY"] = os.environ.get("OPENAI_API_KEY")
        
        # Ensure schema index exists
        logger.info("Ensuring schema index exists")
        if not await ensure_index_exists():
            logger.error("Failed to create schema metadata index")
            return False
        
        # Get LLM client
        logger.info("Initializing LLM client")
        llm = get_llm_client()
        
        # Sample questions for testing
        questions = [
            # Original simple question
            "What are the top 5 customers by total order amount?",
            
            # Large dataset question
            "What are the top 10 customers by total order amount using the large_orders_view and large_users_view?"
        ]
        
        # Select which question to run
        selected_question = questions[1]  # Use the large dataset question
        
        logger.info(f"Running orchestrated analysis for question: {selected_question}")
        
        # Run orchestrated analysis
        result = await llm.orchestrate_analysis(selected_question)
        
        # Print result
        logger.info("Analysis completed")
        logger.info(f"Analysis steps taken: {result.get('steps_taken', 0)}")
        logger.info(f"Final analysis: {result.get('analysis')}")
        
        # Print session ID for reference
        session_id = result.get("session_id")
        logger.info(f"Session ID: {session_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error testing orchestration: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_orchestration())
    sys.exit(0 if success else 1) 