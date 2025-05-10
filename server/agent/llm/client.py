import os
import logging
import jinja2
import json
import uuid
from typing import List, Dict, Any, Optional, Callable
import openai
from openai import OpenAI
import anthropic
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
    
    async def generate_mongodb_query(self, prompt: str) -> str:
        """
        Generate MongoDB aggregation pipeline from a natural language prompt
        
        This method should be overridden by subclasses
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Generated MongoDB query as a JSON string
        """
        raise NotImplementedError("Subclasses must implement generate_mongodb_query")
    
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
    
    async def generate_mongodb_query(self, prompt: str) -> str:
        """
        Generate MongoDB aggregation pipeline from a natural language prompt using OpenAI API
        
        Args:
            prompt: The prompt to send to the OpenAI API
            
        Returns:
            Generated MongoDB query as a JSON string
        """
        logger.info("Generating MongoDB query using OpenAI API")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a MongoDB expert. Generate only JSON representing a valid MongoDB query."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            mongodb_query = response.choices[0].message.content.strip()
            logger.info("Successfully generated MongoDB query")
            
            # Validate that the response is valid JSON
            try:
                json.loads(mongodb_query)
            except json.JSONDecodeError:
                # If it's not valid JSON, try to extract JSON from the response
                # It might be wrapped in ```json and ``` blocks
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', mongodb_query)
                if json_match:
                    mongodb_query = json_match.group(1).strip()
                    # Validate again
                    json.loads(mongodb_query)
                else:
                    raise ValueError("Generated MongoDB query is not valid JSON")
            
            return mongodb_query
            
        except Exception as e:
            logger.error(f"Error generating MongoDB query with OpenAI: {str(e)}")
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
        
        # Pre-load basic schema metadata to provide context to the LLM
        try:
            logger.info("Pre-loading database schema information")
            basic_metadata = await self.data_tools.get_metadata()
            
            # Extract just the table names and basic schema info for efficiency
            table_names = []
            if isinstance(basic_metadata, dict) and 'tables' in basic_metadata:
                for table in basic_metadata.get('tables', []):
                    if 'name' in table:
                        table_names.append(table['name'])
            
            # Create an initial context message with available tables
            context_message = f"""
            Available tables in the database: {', '.join(table_names)}
            
            When analyzing data, first use get_metadata to understand table structures before running queries.
            Always check if a table exists before trying to query it.
            
            Now analyze the following: {question}
            """
        except Exception as e:
            logger.warning(f"Failed to pre-load schema metadata: {str(e)}")
            # Fall back to just the question if we couldn't load metadata
            context_message = f"I need to analyze the following: {question}"
        
        # Initialize conversation with the enhanced context
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context_message}
        ]
        
        # Add basic metadata to state for reference
        if 'table_names' in locals() and table_names:
            state.add_executed_tool(
                "get_metadata", 
                {"preloaded": True}, 
                {"available_tables": table_names}
            )
            await self.state_manager.update_state(state)
        
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
                tool_results = []
                
                # Process each tool call
                for tool_call in tool_calls:
                    # Extract values as dict or object attributes
                    function_name = tool_call.function.name
                    tool_use_id = tool_call.id
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    
                    try:
                        # Execute the function with the parsed arguments
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
                                
                                # Add the tool result for this specific tool use
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps(result)
                                })
                            except Exception as e:
                                logger.error(f"Error executing tool {function_name}: {str(e)}")
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps({"error": f"Error executing {function_name}: {str(e)}"})
                                })
                        else:
                            # Unknown function
                            logger.warning(f"Unknown function: {function_name}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps({"error": f"Unknown function: {function_name}"})
                            })
                    except Exception as e:
                        logger.error(f"Error processing tool call: {str(e)}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps({"error": f"Error processing tool call: {str(e)}"})
                        })
                
                # Add all tool results in a single user message
                if tool_results:
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })
                
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

class AnthropicClient(LLMClient):
    """Client for Anthropic API"""
    
    def __init__(self):
        super().__init__()
        
        # Check if Anthropic settings are configured
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.model_name = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be configured")
            
        try:
            # Initialize Anthropic client with only the required parameters
            # This works better across different versions of the SDK
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info(f"Initialized Anthropic client with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Error initializing Anthropic client: {str(e)}")
            raise
        
        # Define available tools for function calling with Anthropic's custom format
        self.tools = [
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
            },
            {
                "type": "custom",
                "name": "run_summary_query",
                "description": "Generate statistical summaries of specified columns in a table",
                "input_schema": {
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
            },
            {
                "type": "custom",
                "name": "run_targeted_query",
                "description": "Run a specific SQL query with timeout protection",
                "input_schema": {
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
            },
            {
                "type": "custom",
                "name": "sample_data",
                "description": "Get a representative sample of data from a SQL query",
                "input_schema": {
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
            },
            {
                "type": "custom",
                "name": "generate_insights",
                "description": "Generate specific insights from data",
                "input_schema": {
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
        ]
    
    async def generate_sql(self, prompt: str) -> str:
        """
        Generate SQL from a natural language prompt using Anthropic API
        
        Args:
            prompt: The prompt to send to the Anthropic API
            
        Returns:
            Generated SQL as a string
        """
        logger.info("Generating SQL using Anthropic API")
        
        try:
            response = self.client.messages.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system="You are a SQL expert. Generate only SQL code without explanations.",
                temperature=0.1,
                max_tokens=1000
            )
            
            # Extract text content from the response
            if hasattr(response, 'content') and len(response.content) > 0:
                # Handle different response structures
                if hasattr(response.content[0], 'text'):
                    sql = response.content[0].text
                else:
                    sql = response.content[0]
            else:
                logger.warning("Unexpected response format from Anthropic API")
                sql = ""
                
            logger.info("Successfully generated SQL query")
            return sql
            
        except Exception as e:
            logger.error(f"Error generating SQL with Anthropic: {str(e)}")
            raise
    
    async def generate_mongodb_query(self, prompt: str) -> str:
        """
        Generate MongoDB aggregation pipeline from a natural language prompt using Anthropic API
        
        Args:
            prompt: The prompt to send to the Anthropic API
            
        Returns:
            Generated MongoDB query as a JSON string
        """
        logger.info("Generating MongoDB query using Anthropic API")
        
        try:
            response = self.client.messages.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system="You are a MongoDB expert. Generate only JSON representing a valid MongoDB query.",
                temperature=0.1,
                max_tokens=1000
            )
            
            # Extract text content from the response
            if hasattr(response, 'content') and len(response.content) > 0:
                # Handle different response structures
                if hasattr(response.content[0], 'text'):
                    mongodb_query = response.content[0].text
                else:
                    mongodb_query = response.content[0]
            else:
                logger.warning("Unexpected response format from Anthropic API")
                mongodb_query = ""
            
            # Validate that the response is valid JSON
            try:
                json.loads(mongodb_query)
            except json.JSONDecodeError:
                # If it's not valid JSON, try to extract JSON from the response
                # It might be wrapped in ```json and ``` blocks
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', mongodb_query)
                if json_match:
                    mongodb_query = json_match.group(1).strip()
                    # Validate again
                    json.loads(mongodb_query)
                else:
                    raise ValueError("Generated MongoDB query is not valid JSON")
                
            logger.info("Successfully generated MongoDB query")
            return mongodb_query
            
        except Exception as e:
            logger.error(f"Error generating MongoDB query with Anthropic: {str(e)}")
            raise
    
    async def analyze_results(self, rows: List[Dict[str, Any]]) -> str:
        """
        Analyze SQL query results using Anthropic API
        
        Args:
            rows: Query results as a list of dictionaries
            
        Returns:
            Analysis as a string
        """
        logger.info("Analyzing results using Anthropic API")
        
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
            response = self.client.messages.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system="You are a data analyst expert. Provide clear, concise analysis.",
                temperature=0.3,
                max_tokens=1000
            )
            
            # Extract text content from the response
            if hasattr(response, 'content') and len(response.content) > 0:
                # Handle different response structures
                if hasattr(response.content[0], 'text'):
                    analysis = response.content[0].text
                else:
                    analysis = response.content[0]
            else:
                logger.warning("Unexpected response format from Anthropic API")
                analysis = "Unable to generate analysis due to unexpected response format."
                
            logger.info("Successfully generated analysis")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing results with Anthropic: {str(e)}")
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
        
        # Pre-load basic schema metadata to provide context to the LLM
        try:
            logger.info("Pre-loading database schema information")
            basic_metadata = await self.data_tools.get_metadata()
            
            # Extract just the table names and basic schema info for efficiency
            table_names = []
            if isinstance(basic_metadata, dict) and 'tables' in basic_metadata:
                for table in basic_metadata.get('tables', []):
                    if 'name' in table:
                        table_names.append(table['name'])
            
            # Create an initial context message with available tables
            context_message = f"""
            Available tables in the database: {', '.join(table_names)}
            
            When analyzing data, first use get_metadata to understand table structures before running queries.
            Always check if a table exists before trying to query it.
            
            Now analyze the following: {question}
            """
        except Exception as e:
            logger.warning(f"Failed to pre-load schema metadata: {str(e)}")
            # Fall back to just the question if we couldn't load metadata
            context_message = f"I need to analyze the following: {question}"
        
        # Initialize conversation with the enhanced context
        messages = [
            {"role": "user", "content": context_message}
        ]
        
        # Add basic metadata to state for reference
        if 'table_names' in locals() and table_names:
            state.add_executed_tool(
                "get_metadata", 
                {"preloaded": True}, 
                {"available_tables": table_names}
            )
            await self.state_manager.update_state(state)
        
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
                response = self.client.messages.create(
                    model=self.model_name,
                    messages=messages,
                    system=system_prompt,
                    tools=self.tools,
                    temperature=0.2,
                    max_tokens=2000
                )
                
                # Check if we have a text response or a tool use response
                stop_reason = response.stop_reason
                content_blocks = response.content
                
                # Add assistant's message to the conversation history
                assistant_content = []
                
                # Process text content - handle content blocks as plain dictionaries
                for block in content_blocks:
                    if isinstance(block, dict):
                        block_type = block.get('type')
                        if block_type == "text":
                            assistant_content.append({"type": "text", "text": block.get('text', '')})
                    else:
                        # Direct attribute access for model objects
                        try:
                            if getattr(block, 'type', None) == "text":
                                assistant_content.append({"type": "text", "text": getattr(block, 'text', '')})
                        except Exception as e:
                            logger.warning(f"Error processing content block: {str(e)}")
                
                # Check for tool calls - handle both dict and object formats
                tool_calls = []
                for block in content_blocks:
                    if isinstance(block, dict):
                        if block.get('type') == "tool_use":
                            tool_calls.append(block)
                    else:
                        try:
                            if getattr(block, 'type', None) == "tool_use":
                                # Convert to dict for consistent handling
                                tool_calls.append({
                                    'type': 'tool_use',
                                    'id': getattr(block, 'id', ''),
                                    'name': getattr(block, 'name', ''),
                                    'input': getattr(block, 'input', {})
                                })
                        except Exception as e:
                            logger.warning(f"Error processing tool block: {str(e)}")
                
                has_tool_calls = len(tool_calls) > 0
                
                # If it's a final answer (no tool calls) and not explicitly asking for a tool
                if not has_tool_calls:
                    # Process any text response
                    content = ""
                    for block in assistant_content:
                        if block.get('type') == "text":
                            content += block.get('text', '')
                    
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": content}]})
                    
                    # Check if this is the final analysis
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
                
                # If we have tool calls, we need to handle them
                if has_tool_calls:
                    # First add the assistant message with tool calls to our conversation history
                    # Convert to format accepted by API
                    formatted_content = []
                    for block in content_blocks:
                        if isinstance(block, dict):
                            formatted_content.append(block)
                        else:
                            try:
                                if getattr(block, 'type', None) == "text":
                                    formatted_content.append({
                                        "type": "text", 
                                        "text": getattr(block, 'text', '')
                                    })
                                elif getattr(block, 'type', None) == "tool_use":
                                    formatted_content.append({
                                        "type": "tool_use",
                                        "id": getattr(block, 'id', ''),
                                        "name": getattr(block, 'name', ''),
                                        "input": getattr(block, 'input', {})
                                    })
                            except Exception as e:
                                logger.warning(f"Error formatting content block: {str(e)}")
                    
                    messages.append({"role": "assistant", "content": formatted_content})
                    
                    # Process each tool call
                    tool_results = []
                    
                    for tool_call in tool_calls:
                        # Extract values as dict or object attributes
                        function_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                        tool_use_id = tool_call.get('id') if isinstance(tool_call, dict) else getattr(tool_call, 'id', None)
                        function_args = tool_call.get('input') if isinstance(tool_call, dict) else getattr(tool_call, 'input', {})
                        
                        logger.info(f"Executing tool: {function_name} with args: {function_args}")
                        
                        try:
                            # Execute the function with the parsed arguments
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
                                    
                                    # Add the tool result for this specific tool use
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": tool_use_id,
                                        "content": json.dumps(result)
                                    })
                                except Exception as e:
                                    logger.error(f"Error executing tool {function_name}: {str(e)}")
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": tool_use_id,
                                        "content": json.dumps({"error": f"Error executing {function_name}: {str(e)}"})
                                    })
                            else:
                                # Unknown function
                                logger.warning(f"Unknown function: {function_name}")
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps({"error": f"Unknown function: {function_name}"})
                                })
                        except Exception as e:
                            logger.error(f"Error processing tool call: {str(e)}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps({"error": f"Error processing tool call: {str(e)}"})
                            })
                    
                    # Add all tool results in a single user message
                    if tool_results:
                        messages.append({
                            "role": "user",
                            "content": tool_results
                        })
                
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
            
            final_response = self.client.messages.create(
                model=self.model_name,
                messages=messages,
                system=system_prompt,
                temperature=0.2,
                max_tokens=2000
            )
            
            # Extract final content
            final_content = ""
            for block in final_response.content:
                if isinstance(block, dict):
                    if block.get('type') == "text":
                        final_content += block.get('text', '')
                else:
                    try:
                        if getattr(block, 'type', None) == "text":
                            final_content += getattr(block, 'text', '')
                    except Exception as e:
                        logger.warning(f"Error extracting final content: {str(e)}")
            
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
    
    async def generate_mongodb_query(self, prompt: str) -> str:
        """
        Generate MongoDB aggregation pipeline from a natural language prompt using local LLM
        
        Args:
            prompt: The prompt to send to the local LLM
            
        Returns:
            Generated MongoDB query as a JSON string
        """
        logger.info("Generating MongoDB query using local LLM")
        
        # This is a placeholder - in a real implementation, you would:
        # 1. Load the local model
        # 2. Run inference
        # 3. Extract and return the generated MongoDB query
        
        # For demonstration purposes, return a placeholder MongoDB query
        return '''{
          "collection": "users",
          "pipeline": [
            { "$match": { "active": true } },
            { "$limit": 10 }
          ]
        }'''
    
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
    
    # Check for Anthropic configuration
    if os.environ.get("ANTHROPIC_API_KEY"):
        logger.info("Using Anthropic client")
        return AnthropicClient()
    elif settings.LLM_API_URL and settings.LLM_API_KEY:
        logger.info("Using OpenAI client")
        return OpenAIClient()
    elif settings.MODEL_PATH and settings.MODEL_TYPE:
        logger.info("Using local LLM client")
        return LocalLLMClient()
    else:
        raise ValueError("Either OpenAI API, Anthropic API or local model settings must be configured")
