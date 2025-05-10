import os
import logging
import jinja2
import json
import uuid
from typing import List, Dict, Any, Optional, Callable
import openai
from openai import OpenAI
from ..config.settings import Settings
from ..tools.tools import DataTools
from ..tools.state_manager import StateManager, AnalysisState

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMClient:
    """Base class for LLM client implementations"""
    
    def __init__(self):
        self.settings = Settings()
        self.templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Initialize tools and state manager
        self.data_tools = DataTools()
        self.state_manager = StateManager()
    
    def render_template(self, template_name: str, **kwargs) -> str:
        """
        Render a Jinja2 template with the provided variables
        
        Args:
            template_name: Name of the template file
            **kwargs: Variables to pass to the template
            
        Returns:
            Rendered template as a string
        """
        template = self.template_env.get_template(template_name)
        return template.render(**kwargs)
    
    async def generate_sql(self, prompt: str) -> str:
        """
        Generate SQL from a natural language prompt
        
        This method should be overridden by subclasses
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Generated SQL as a string
        """
        raise NotImplementedError("Subclasses must implement generate_sql")
    
    async def analyze_results(self, rows: List[Dict[str, Any]]) -> str:
        """
        Analyze SQL query results
        
        This method should be overridden by subclasses
        
        Args:
            rows: Query results as a list of dictionaries
            
        Returns:
            Analysis as a string
        """
        raise NotImplementedError("Subclasses must implement analyze_results")
    
    async def orchestrate_analysis(self, question: str) -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        This method should be overridden by subclasses
        
        Args:
            question: Natural language question from the user
            
        Returns:
            Final analysis result
        """
        raise NotImplementedError("Subclasses must implement orchestrate_analysis")

class OpenAIClient(LLMClient):
    """Client for OpenAI API"""
    
    def __init__(self):
        super().__init__()
        
        # Check if OpenAI settings are configured
        if not self.settings.LLM_API_URL or not self.settings.LLM_API_KEY:
            raise ValueError("OpenAI API URL and API key must be configured")
            
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.settings.LLM_API_KEY,
            base_url=self.settings.LLM_API_URL
        )
        
        # Default model name if not specified
        self.model_name = self.settings.LLM_MODEL_NAME or "gpt-4"
        logger.info(f"Initialized OpenAI client with model: {self.model_name}")
        
        # Define available tools for function calling
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_metadata",
                    "description": "Get metadata about database tables and columns",
                    "parameters": {
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
            },
            {
                "type": "function",
                "function": {
                    "name": "run_summary_query",
                    "description": "Generate statistical summaries of specified columns in a table",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Name of the table to analyze"
                            },
                            "columns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of column names to generate statistics for. If not provided, will use all numeric columns."
                            }
                        },
                        "required": ["table_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_targeted_query",
                    "description": "Run a specific SQL query with timeout protection",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Query timeout in seconds (default: 30)"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sample_data",
                    "description": "Get a representative sample of data from a SQL query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL query to sample from"
                            },
                            "sample_size": {
                                "type": "integer",
                                "description": "Number of rows to sample (default: 100)"
                            },
                            "sampling_method": {
                                "type": "string",
                                "enum": ["random", "first", "stratified"],
                                "description": "Method to use for sampling (default: random)"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_insights",
                    "description": "Generate specific insights from data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "object",
                                "description": "Data to analyze"
                            },
                            "insight_type": {
                                "type": "string",
                                "enum": ["outliers", "trends", "clusters", "correlations"],
                                "description": "Type of insight to generate"
                            }
                        },
                        "required": ["data", "insight_type"]
                    }
                }
            }
        ]
    
    async def generate_sql(self, prompt: str) -> str:
        """
        Generate SQL from a natural language prompt using OpenAI API
        
        Args:
            prompt: The prompt to send to the OpenAI API
            
        Returns:
            Generated SQL as a string
        """
        logger.info("Generating SQL using OpenAI API")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a SQL expert. Generate only SQL code without explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            sql = response.choices[0].message.content.strip()
            logger.info("Successfully generated SQL query")
            return sql
            
        except Exception as e:
            logger.error(f"Error generating SQL with OpenAI: {str(e)}")
            raise
    
    async def analyze_results(self, rows: List[Dict[str, Any]]) -> str:
        """
        Analyze SQL query results using OpenAI API
        
        Args:
            rows: Query results as a list of dictionaries
            
        Returns:
            Analysis as a string
        """
        logger.info("Analyzing results using OpenAI API")
        
        # Convert rows to a string representation
        # Limit to first 20 rows for brevity and to avoid token limits
        results_sample = rows[:20]
        results_str = json.dumps(results_sample, indent=2)
        total_rows = len(rows)
        
        # Create a prompt for the analysis
        prompt = f"""
        Analyze the following SQL query results and provide a brief summary:
        
        Total rows returned: {total_rows}
        Sample data ({min(20, total_rows)} rows):
        {results_str}
        
        Please describe any patterns, insights, or notable points about this data.
        Keep your analysis concise and focused on the most important observations.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a data analyst expert. Provide clear, concise analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            analysis = response.choices[0].message.content.strip()
            logger.info("Successfully generated analysis")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing results with OpenAI: {str(e)}")
            raise
    
    async def orchestrate_analysis(self, question: str) -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        Args:
            question: Natural language question from the user
            
        Returns:
            Final analysis result with supporting data
        """
        logger.info(f"Starting orchestrated analysis for question: {question}")
        
        # Create a new session and initialize tools
        session_id = await self.state_manager.create_session(question)
        await self.data_tools.initialize(session_id)
        
        # Get the state for this session
        state = await self.state_manager.get_state(session_id)
        if not state:
            raise ValueError(f"Failed to create session state for question: {question}")
        
        # Load prompt template for orchestration
        system_prompt = self.render_template("orchestration_system.tpl")
        
        # Initialize conversation
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"I need to analyze the following: {question}"}
        ]
        
        # Define a maximum number of steps to prevent infinite loops
        max_steps = 10
        step_count = 0
        
        # Tool execution mapping
        tool_executors = {
            "get_metadata": self.data_tools.get_metadata,
            "run_summary_query": self.data_tools.run_summary_query,
            "run_targeted_query": self.data_tools.run_targeted_query,
            "sample_data": self.data_tools.sample_data,
            "generate_insights": self.data_tools.generate_insights
        }
        
        while step_count < max_steps:
            step_count += 1
            logger.info(f"Orchestration step {step_count} for session {session_id}")
            
            try:
                # Call LLM with current conversation
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.tools,
                    temperature=0.2
                )
                
                # Get the response message
                response_message = response.choices[0].message
                
                # Before appending, make a deep copy to avoid reference issues with tool_calls
                # Convert to dict, then create a clean message entry
                message_dict = response_message.model_dump()
                
                # Add the message to the conversation
                messages.append(message_dict)
                
                # Check if LLM wants to call a function
                tool_calls = response_message.tool_calls
                
                # If no tool calls, check if we've reached a conclusion
                if not tool_calls:
                    # Check if this is the final analysis
                    content = response_message.content
                    if content and "FINAL ANALYSIS:" in content:
                        # Extract final analysis
                        final_analysis = content.split("FINAL ANALYSIS:")[1].strip()
                        
                        # Update state with final analysis
                        state.set_final_result(
                            {"session_id": session_id, "question": question},
                            final_analysis
                        )
                        await self.state_manager.update_state(state)
                        
                        # Return final result
                        return {
                            "session_id": session_id,
                            "question": question,
                            "analysis": final_analysis,
                            "steps_taken": step_count,
                            "state": state.to_dict()
                        }
                    else:
                        # Need more information, continue the conversation
                        messages.append({
                            "role": "user", 
                            "content": "Please continue the analysis. Use available tools to gather more information if needed, or provide the final analysis if you have enough information."
                        })
                        continue
                
                # Keep track of tools we need to respond to in this iteration
                tool_responses = []
                
                # Process each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    
                    # Safely parse arguments
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in tool arguments: {tool_call.function.arguments}")
                        function_args = {}
                    
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    
                    # Execute the function
                    if function_name in tool_executors:
                        try:
                            # Execute the tool and get result
                            result = await tool_executors[function_name](**function_args)
                            
                            # Record in state
                            state.add_executed_tool(function_name, function_args, result)
                            await self.state_manager.update_state(state)
                            
                            # If it's a SQL query, also record it
                            if function_name == "run_targeted_query" and "query" in function_args:
                                state.add_generated_query(
                                    function_args["query"],
                                    f"Query executed in step {step_count}",
                                    False  # Not final yet
                                )
                                await self.state_manager.update_state(state)
                            
                            # Prepare the tool response
                            tool_responses.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": json.dumps(result)
                            })
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {str(e)}")
                            tool_responses.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": json.dumps({"error": f"Error executing {function_name}: {str(e)}"})
                            })
                    else:
                        # Unknown function
                        tool_responses.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"error": f"Unknown function: {function_name}"})
                        })
                
                # Add all tool responses to the conversation
                messages.extend(tool_responses)
                
            except Exception as e:
                logger.error(f"Error in orchestration step {step_count}: {str(e)}")
                
                # Add error to conversation
                messages.append({
                    "role": "user",
                    "content": f"An error occurred: {str(e)}. Please continue with available information or try a different approach."
                })
        
        # If we reach here, we've exceeded the maximum number of steps
        logger.warning(f"Exceeded maximum steps ({max_steps}) for session {session_id}")
        
        # Generate a final response based on what we have
        try:
            final_prompt = "We've reached the maximum number of analysis steps. Please provide your best analysis based on the information gathered so far. Begin with 'FINAL ANALYSIS:'"
            messages.append({"role": "user", "content": final_prompt})
            
            final_response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.2
            )
            
            final_content = final_response.choices[0].message.content
            if "FINAL ANALYSIS:" in final_content:
                final_analysis = final_content.split("FINAL ANALYSIS:")[1].strip()
            else:
                final_analysis = final_content
            
            # Update state
            state.set_final_result(
                {"session_id": session_id, "question": question, "max_steps_reached": True},
                final_analysis
            )
            await self.state_manager.update_state(state)
            
            return {
                "session_id": session_id,
                "question": question,
                "analysis": final_analysis,
                "steps_taken": step_count,
                "max_steps_reached": True,
                "state": state.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error generating final analysis: {str(e)}")
            return {
                "session_id": session_id,
                "question": question,
                "error": f"Failed to complete analysis: {str(e)}",
                "steps_taken": step_count,
                "state": state.to_dict()
            }

class LocalLLMClient(LLMClient):
    """Client for local LLM inference"""
    
    def __init__(self):
        super().__init__()
        
        # Check if local model settings are configured
        if not self.settings.MODEL_PATH or not self.settings.MODEL_TYPE:
            raise ValueError("Model path and type must be configured for local inference")
    
    async def generate_sql(self, prompt: str) -> str:
        """
        Generate SQL from a natural language prompt using local LLM
        
        Args:
            prompt: The prompt to send to the local LLM
            
        Returns:
            Generated SQL as a string
        """
        logger.info("Generating SQL using local LLM")
        
        # This is a placeholder - in a real implementation, you would:
        # 1. Load the local model
        # 2. Run inference
        # 3. Extract and return the generated SQL
        
        # For demonstration purposes, return a placeholder SQL query
        return "SELECT * FROM users LIMIT 10"
    
    async def analyze_results(self, rows: List[Dict[str, Any]]) -> str:
        """
        Analyze SQL query results using local LLM
        
        Args:
            rows: Query results as a list of dictionaries
            
        Returns:
            Analysis as a string
        """
        logger.info("Analyzing results using local LLM")
        
        # Convert rows to a string representation
        results_str = str(rows[:10])  # Limit to first 10 rows for brevity
        
        # Create a prompt for the analysis
        prompt = f"""
        Analyze the following query results and provide a brief summary:
        
        {results_str}
        
        Please describe any patterns, insights, or notable points about this data.
        """
        
        # This is a placeholder - in a real implementation, you would:
        # 1. Load the local model
        # 2. Run inference
        # 3. Extract and return the analysis
        
        # For demonstration purposes, return a placeholder analysis
        return "Analysis would be provided by the local LLM in a real implementation."
    
    async def orchestrate_analysis(self, question: str) -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        Args:
            question: Natural language question from the user
            
        Returns:
            Final analysis result
        """
        # Placeholder implementation - in a real implementation, you would:
        # 1. Implement function calling for local LLM
        # 2. Use similar orchestration logic as OpenAIClient
        
        logger.info(f"Orchestration not fully implemented for local LLM")
        
        return {
            "question": question,
            "analysis": "Orchestrated analysis not implemented for local LLM",
            "error": "Not implemented"
        }

def get_llm_client() -> LLMClient:
    """
    Factory function to get the appropriate LLM client based on configuration
    
    Returns:
        An instance of LLMClient
    """
    settings = Settings()
    
    if settings.LLM_API_URL and settings.LLM_API_KEY:
        logger.info("Using OpenAI client")
        return OpenAIClient()
    elif settings.MODEL_PATH and settings.MODEL_TYPE:
        logger.info("Using local LLM client")
        return LocalLLMClient()
    else:
        raise ValueError("Either OpenAI API or local model settings must be configured")
