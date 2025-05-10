#!/usr/bin/env python
import os
import json
import anthropic
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_anthropic_tools():
    """Test the Anthropic API with a simple tool"""
    try:
        # Make sure we have an API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set in environment variables")
            return False
        
        # Initialize client
        client = anthropic.Anthropic(api_key=api_key)
        
        # Define a simple tool
        custom_tools = [
            {
                "type": "custom",
                "name": "get_metadata",
                "description": "Get metadata about database tables and columns",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of specific table names to get metadata for. If not provided, gets metadata for all tables."
                        }
                    },
                    "required": []
                }
            }
        ]
        
        # Create a message with the tool
        logger.info("Sending request to Anthropic API with custom tool")
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": "Can you show me the metadata for the orders table?"}
            ],
            tools=custom_tools,
            temperature=0.2,
        )
        
        # Print the response
        logger.info("Response received:")
        logger.info(f"Stop reason: {response.stop_reason}")
        logger.info(json.dumps(response.model_dump(), indent=2))
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing Anthropic API: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_anthropic_tools()
    print(f"Test {'successful' if success else 'failed'}") 