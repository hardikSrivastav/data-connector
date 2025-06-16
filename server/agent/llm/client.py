import os
import logging
import jinja2
import json
import uuid
from typing import List, Dict, Any, Optional, Callable, AsyncIterator
from datetime import datetime
import openai
from openai import OpenAI
import anthropic
from ..config.settings import Settings
from ..tools.tools import DataTools
from ..tools.state_manager import StateManager, AnalysisState
import re

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
        self.data_tools = None  # Will be initialized with db_type when needed
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
    
    async def analyze_results(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> str:
        """
        Analyze query results
        
        This method should be overridden by subclasses
        
        Args:
            rows: Query results as a list of dictionaries
            is_vector_search: Whether the results are from a vector search
            
        Returns:
            Analysis as a string
        """
        raise NotImplementedError("Subclasses must implement analyze_results")
    
    async def orchestrate_analysis(self, question: str, db_type: str = "postgres") -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        This method should be overridden by subclasses
        
        Args:
            question: Natural language question from the user
            db_type: Database type being queried
            
        Returns:
            Final analysis result
        """
        raise NotImplementedError("Subclasses must implement orchestrate_analysis")

    # Streaming Methods
    async def generate_sql_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate SQL from a natural language prompt with streaming
        
        This method should be overridden by subclasses
        
        Args:
            prompt: The prompt to send to the LLM
            
        Yields:
            Streaming events as dictionaries with type, content, and metadata
        """
        raise NotImplementedError("Subclasses must implement generate_sql_stream")
    
    async def generate_mongodb_query_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate MongoDB aggregation pipeline from a natural language prompt with streaming
        
        This method should be overridden by subclasses
        
        Args:
            prompt: The prompt to send to the LLM
            
        Yields:
            Streaming events as dictionaries with type, content, and metadata
        """
        raise NotImplementedError("Subclasses must implement generate_mongodb_query_stream")
    
    async def analyze_results_stream(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """
        Analyze query results with streaming
        
        This method should be overridden by subclasses
        
        Args:
            rows: Query results as a list of dictionaries
            is_vector_search: Whether the results are from a vector search
            
        Yields:
            Streaming events as dictionaries with type, content, and metadata
        """
        raise NotImplementedError("Subclasses must implement analyze_results_stream")
    
    async def orchestrate_analysis_stream(self, question: str, db_type: str = "postgres") -> AsyncIterator[Dict[str, Any]]:
        """
        Orchestrate a multi-step analysis process using available tools with streaming
        
        This method should be overridden by subclasses
        
        Args:
            question: Natural language question from the user
            db_type: Database type being queried
            
        Yields:
            Streaming events as dictionaries with type, content, and metadata
        """
        raise NotImplementedError("Subclasses must implement orchestrate_analysis_stream")

    def _create_stream_event(self, event_type: str, **kwargs) -> Dict[str, Any]:
        """
        Create a standardized streaming event
        
        Args:
            event_type: Type of the event (status, partial_sql, sql_complete, etc.)
            **kwargs: Additional event data
            
        Returns:
            Standardized event dictionary
        """
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": kwargs.pop("session_id", str(uuid.uuid4())),
            **kwargs
        }
        return event

    def _serialize_data_for_llm(self, data: Any) -> str:
        """
        Convert data to JSON-serializable format for LLM APIs.
        Handles Decimal objects and other non-serializable types.
        
        Args:
            data: Data to serialize
            
        Returns:
            JSON string representation of the data
        """
        import decimal
        from datetime import datetime, date
        
        def convert_item(item):
            if isinstance(item, decimal.Decimal):
                return float(item)
            elif isinstance(item, (datetime, date)):
                return item.isoformat()
            elif isinstance(item, dict):
                return {k: convert_item(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [convert_item(i) for i in item]
            elif hasattr(item, '__dict__'):
                # Handle custom objects by converting to dict
                return convert_item(item.__dict__)
            else:
                return item
        
        try:
            converted = convert_item(data)
            # Convert to JSON string
            return json.dumps(converted, indent=2)
        except (TypeError, ValueError) as e:
            logger.warning(f"Data serialization issue: {e}. Using string representation.")
            return str(data)

    async def generate_ga4_query(self, prompt: str) -> str:
        """
        Generate a GA4 query from a prompt.
        
        Args:
            prompt: The prompt for generating the GA4 query
            
        Returns:
            A JSON string with GA4 query parameters
        """
        logger.info(f"Generating GA4 query from prompt: {prompt[:100]}...")
        response = await self.generate(prompt)
        
        # Extract json if needed
        json_match = re.search(r'```(?:json)?\s*(.*?)```', response, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        
        # If no code block markers, assume raw JSON
        return response.strip()

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
        self.model_name = self.settings.LLM_MODEL_NAME or "gpt-4o"
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
    
    async def generate_sql_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate SQL from a natural language prompt using OpenAI API with streaming
        
        Args:
            prompt: The prompt to send to the OpenAI API
            
        Yields:
            Streaming events as dictionaries
        """
        logger.info("Generating SQL using OpenAI API with streaming")
        session_id = str(uuid.uuid4())
        
        try:
            # Yield initial status
            yield self._create_stream_event("status", 
                                           message="Starting SQL generation...", 
                                           session_id=session_id)
            
            # Create streaming request
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a SQL expert. Generate only SQL code without explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                stream=True
            )
            
            yield self._create_stream_event("status", 
                                           message="Receiving SQL generation...", 
                                           session_id=session_id)
            
            # Collect partial content
            partial_content = ""
            chunk_count = 0
            
            # Process streaming response
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    partial_content += content
                    chunk_count += 1
                    
                    # Yield partial SQL content
                    yield self._create_stream_event("partial_sql", 
                                                   content=partial_content, 
                                                   is_complete=False,
                                                   chunk_index=chunk_count,
                                                   session_id=session_id)
            
            # Clean up the final SQL
            sql = partial_content.strip()
            
            # Basic validation
            validation_status = "valid"
            if not sql or not any(keyword in sql.upper() for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE", "WITH"]):
                validation_status = "warning"
            
            # Yield completion event
            yield self._create_stream_event("sql_complete", 
                                           sql=sql, 
                                           validation_status=validation_status,
                                           total_chunks=chunk_count,
                                           session_id=session_id)
            
            logger.info("Successfully completed SQL generation streaming")
            
        except Exception as e:
            logger.error(f"Error generating SQL with OpenAI streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="GENERATION_FAILED",
                                           message=f"Error generating SQL: {str(e)}",
                                           recoverable=True,
                                           session_id=session_id)
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
    
    async def generate_mongodb_query_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate MongoDB aggregation pipeline from a natural language prompt using OpenAI API with streaming
        
        Args:
            prompt: The prompt to send to the OpenAI API
            
        Yields:
            Streaming events as dictionaries
        """
        logger.info("Generating MongoDB query using OpenAI API with streaming")
        session_id = str(uuid.uuid4())
        
        try:
            # Yield initial status
            yield self._create_stream_event("status", 
                                           message="Starting MongoDB query generation...", 
                                           session_id=session_id)
            
            # Create streaming request
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a MongoDB expert. Generate only JSON representing a valid MongoDB query."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                stream=True
            )
            
            yield self._create_stream_event("status", 
                                           message="Receiving MongoDB query generation...", 
                                           session_id=session_id)
            
            # Collect partial content
            partial_content = ""
            chunk_count = 0
            
            # Process streaming response
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    partial_content += content
                    chunk_count += 1
                    
                    # Yield partial MongoDB query content
                    yield self._create_stream_event("partial_mongodb_query", 
                                                   content=partial_content, 
                                                   is_complete=False,
                                                   chunk_index=chunk_count,
                                                   session_id=session_id)
            
            # Clean up the final query
            mongodb_query = partial_content.strip()
            
            # Try to validate JSON
            validation_status = "valid"
            try:
                json.loads(mongodb_query)
            except json.JSONDecodeError:
                # Try to extract JSON from response if wrapped in code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', mongodb_query)
                if json_match:
                    mongodb_query = json_match.group(1).strip()
                    try:
                        json.loads(mongodb_query)
                    except json.JSONDecodeError:
                        validation_status = "invalid"
                else:
                    validation_status = "invalid"
            
            # Yield completion event
            yield self._create_stream_event("mongodb_query_complete", 
                                           query=mongodb_query, 
                                           validation_status=validation_status,
                                           total_chunks=chunk_count,
                                           session_id=session_id)
            
            logger.info("Successfully completed MongoDB query generation streaming")
            
        except Exception as e:
            logger.error(f"Error generating MongoDB query with OpenAI streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="GENERATION_FAILED",
                                           message=f"Error generating MongoDB query: {str(e)}",
                                           recoverable=True,
                                           session_id=session_id)
            raise
    
    async def analyze_results(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> str:
        """
        Analyze query results using OpenAI API
        
        Args:
            rows: Query results as a list of dictionaries
            is_vector_search: Whether the results are from a vector search
            
        Returns:
            Analysis as a string
        """
        logger.info(f"Analyzing {'vector search' if is_vector_search else 'query'} results using OpenAI API")
        
        # Prepare the data for the prompt
        # Convert rows to string to avoid sending too much data
        data_str = self._serialize_data_for_llm(rows[:100])  # Limit to 100 rows
        
        # Choose appropriate prompt based on result type
        if is_vector_search:
            prompt = f"""
            Analyze these vector search results and provide key insights:
            
            {data_str}
            
            Consider:
            1. Similarity patterns in the results
            2. Key information or themes present in the top results
            3. How well the results match the semantic meaning of the query
            4. Any patterns in the metadata of the results
            
            Format your analysis in markdown with clean sections and bullet points.
            """
        else:
            prompt = f"""
            Analyze these SQL query results and provide key insights:
            
            {data_str}
            
            Consider:
            1. Key patterns and trends
            2. Notable outliers
            3. Statistical observations
            4. Business implications
            
            Format your analysis in markdown with clean sections and bullet points.
            """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a data analyst providing clear, concise insights."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            # Extract and return the analysis text
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing results: {str(e)}")
            return f"Error analyzing results: {str(e)}"
    
    async def analyze_results_stream(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """
        Analyze query results using OpenAI API with streaming
        
        Args:
            rows: Query results as a list of dictionaries
            is_vector_search: Whether the results are from a vector search
            
        Yields:
            Streaming events as dictionaries
        """
        logger.info(f"Analyzing {'vector search' if is_vector_search else 'query'} results using OpenAI API with streaming")
        session_id = str(uuid.uuid4())
        
        try:
            # Yield initial status
            yield self._create_stream_event("status", 
                                           message="Starting results analysis...", 
                                           session_id=session_id)
            
            # Prepare the data for the prompt
            data_str = self._serialize_data_for_llm(rows[:100])  # Limit to 100 rows
            
            # Choose appropriate prompt based on result type
            if is_vector_search:
                prompt = f"""
                Analyze these vector search results and provide key insights:
                
                {data_str}
                
                Consider:
                1. Similarity patterns in the results
                2. Key information or themes present in the top results
                3. How well the results match the semantic meaning of the query
                4. Any patterns in the metadata of the results
                
                Format your analysis in markdown with clean sections and bullet points.
                """
            else:
                prompt = f"""
                Analyze these SQL query results and provide key insights:
                
                {data_str}
                
                Consider:
                1. Key patterns and trends
                2. Notable outliers
                3. Statistical observations
                4. Business implications
                
                Format your analysis in markdown with clean sections and bullet points.
                """
            
            yield self._create_stream_event("status", 
                                           message="Generating analysis...", 
                                           session_id=session_id)
            
            # Create streaming request
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a data analyst providing clear, concise insights."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                stream=True
            )
            
            # Collect partial content
            partial_content = ""
            chunk_count = 0
            
            # Process streaming response
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    partial_content += content
                    chunk_count += 1
                    
                    # Yield analysis chunk
                    yield self._create_stream_event("analysis_chunk", 
                                                   text=partial_content, 
                                                   chunk_index=chunk_count,
                                                   is_final=False,
                                                   session_id=session_id)
            
            # Yield final analysis event
            yield self._create_stream_event("analysis_chunk", 
                                           text=partial_content.strip(), 
                                           chunk_index=chunk_count,
                                           is_final=True,
                                           total_chunks=chunk_count,
                                           session_id=session_id)
            
            logger.info("Successfully completed analysis streaming")
            
        except Exception as e:
            logger.error(f"Error analyzing results with OpenAI streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="ANALYSIS_FAILED",
                                           message=f"Error analyzing results: {str(e)}",
                                           recoverable=True,
                                           session_id=session_id)
            raise
    
    async def orchestrate_analysis(self, question: str, db_type: str = "postgres") -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        Args:
            question: Natural language question from the user
            db_type: Database type being queried
            
        Returns:
            Final analysis result with supporting data
        """
        logger.info(f"Starting orchestrated analysis for question: {question} with database type: {db_type}")
        
        # Create a new session and initialize tools
        session_id = await self.state_manager.create_session(question)
        
        # Initialize data tools with the correct database type
        self.data_tools = DataTools(db_type=db_type)
        await self.data_tools.initialize(session_id)
        
        # Get the state for this session
        state = await self.state_manager.get_state(session_id)
        if not state:
            raise ValueError(f"Failed to create session state for question: {question}")
        
        # Load prompt template for orchestration
        system_prompt = self.render_template("orchestration_system.tpl", db_type=db_type)
        
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
    
    async def orchestrate_analysis_stream(self, question: str, db_type: str = "postgres") -> AsyncIterator[Dict[str, Any]]:
        """
        Orchestrate a multi-step analysis process using available tools with streaming
        
        Args:
            question: Natural language question from the user
            db_type: Database type being queried
            
        Yields:
            Streaming events as dictionaries
        """
        logger.info(f"Starting orchestrated analysis streaming for question: {question} with database type: {db_type}")
        session_id = str(uuid.uuid4())
        
        try:
            # Yield initial status
            yield self._create_stream_event("status", 
                                           message="Initializing orchestrated analysis...", 
                                           session_id=session_id)
            
            # Create a new session and initialize tools
            state_session_id = await self.state_manager.create_session(question)
            
            # Initialize data tools with the correct database type
            self.data_tools = DataTools(db_type=db_type)
            await self.data_tools.initialize(state_session_id)
            
            # Get the state for this session
            state = await self.state_manager.get_state(state_session_id)
            if not state:
                raise ValueError(f"Failed to create session state for question: {question}")
            
            yield self._create_stream_event("status", 
                                           message="Loading schema information...", 
                                           session_id=session_id)
            
            # Load prompt template for orchestration
            system_prompt = self.render_template("orchestration_system.tpl", db_type=db_type)
            
            # Pre-load basic schema metadata to provide context to the LLM
            try:
                basic_metadata = await self.data_tools.get_metadata()
                
                # Extract just the table names for efficiency
                table_names = []
                if isinstance(basic_metadata, dict) and 'tables' in basic_metadata:
                    for table in basic_metadata.get('tables', []):
                        if 'name' in table:
                            table_names.append(table['name'])
                
                context_message = f"""
                Available tables in the database: {', '.join(table_names)}
                
                When analyzing data, first use get_metadata to understand table structures before running queries.
                Always check if a table exists before trying to query it.
                
                Now analyze the following: {question}
                """
            except Exception as e:
                logger.warning(f"Failed to pre-load schema metadata: {str(e)}")
                context_message = f"I need to analyze the following: {question}"
            
            # Initialize conversation
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_message}
            ]
            
            yield self._create_stream_event("status", 
                                           message="Starting analysis process...", 
                                           session_id=session_id)
            
            # Progress tracking
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
                
                # Yield progress update
                yield self._create_stream_event("progress", 
                                               step=step_count, 
                                               total=max_steps,
                                               percentage=int((step_count / max_steps) * 100),
                                               current_operation=f"Analysis step {step_count}",
                                               session_id=session_id)
                
                try:
                    # Call LLM with current conversation
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        tools=self.tools,
                        temperature=0.2
                    )
                    
                    response_message = response.choices[0].message
                    message_dict = response_message.model_dump()
                    messages.append(message_dict)
                    
                    tool_calls = response_message.tool_calls
                    
                    # If no tool calls, check if we've reached a conclusion
                    if not tool_calls:
                        content = response_message.content
                        if content and "FINAL ANALYSIS:" in content:
                            # Extract final analysis
                            final_analysis = content.split("FINAL ANALYSIS:")[1].strip()
                            
                            yield self._create_stream_event("analysis_chunk", 
                                                           text=final_analysis, 
                                                           chunk_index=1,
                                                           is_final=True,
                                                           session_id=session_id)
                            
                            yield self._create_stream_event("status", 
                                                           message="Analysis completed successfully", 
                                                           session_id=session_id)
                            return
                        else:
                            # Continue the conversation
                            messages.append({
                                "role": "user", 
                                "content": "Please continue the analysis. Use available tools to gather more information if needed, or provide the final analysis if you have enough information."
                            })
                            continue
                    
                    # Process tool calls
                    tool_results = []
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        tool_use_id = tool_call.id
                        function_args = json.loads(tool_call.function.arguments)
                        
                        yield self._create_stream_event("status", 
                                                       message=f"Executing {function_name}...", 
                                                       session_id=session_id)
                        
                        try:
                            if function_name in tool_executors:
                                result = await tool_executors[function_name](**function_args)
                                
                                # Record in state
                                state.add_executed_tool(function_name, function_args, result)
                                await self.state_manager.update_state(state)
                                
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps(result)
                                })
                            else:
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps({"error": f"Unknown function: {function_name}"})
                                })
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {str(e)}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps({"error": f"Error executing {function_name}: {str(e)}"})
                            })
                    
                    # Add tool results to conversation
                    if tool_results:
                        messages.append({
                            "role": "user",
                            "content": tool_results
                        })
                
                except Exception as e:
                    logger.error(f"Error in orchestration step {step_count}: {str(e)}")
                    yield self._create_stream_event("error", 
                                                   error_code="ORCHESTRATION_ERROR",
                                                   message=f"Error in analysis step {step_count}: {str(e)}",
                                                   recoverable=True,
                                                   session_id=session_id)
                    break
            
            # If we reach here, we've exceeded the maximum number of steps
            yield self._create_stream_event("status", 
                                           message="Generating final analysis from available data...", 
                                           session_id=session_id)
            
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
                
                yield self._create_stream_event("analysis_chunk", 
                                               text=final_analysis, 
                                               chunk_index=1,
                                               is_final=True,
                                               max_steps_reached=True,
                                               session_id=session_id)
                
                yield self._create_stream_event("status", 
                                               message="Analysis completed (max steps reached)", 
                                               session_id=session_id)
                
            except Exception as e:
                logger.error(f"Error generating final analysis: {str(e)}")
                yield self._create_stream_event("error", 
                                               error_code="FINAL_ANALYSIS_FAILED",
                                               message=f"Failed to complete final analysis: {str(e)}",
                                               recoverable=False,
                                               session_id=session_id)
        
        except Exception as e:
            logger.error(f"Error in orchestrated analysis streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="ORCHESTRATION_FAILED",
                                           message=f"Error in orchestrated analysis: {str(e)}",
                                           recoverable=False,
                                           session_id=session_id)
            raise

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
    
    async def analyze_results(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> str:
        """
        Analyze query results using Anthropic API
        
        Args:
            rows: Query results as a list of dictionaries
            is_vector_search: Whether the results are from a vector search
            
        Returns:
            Analysis as a string
        """
        logger.info(f"Analyzing {'vector search' if is_vector_search else 'query'} results using Anthropic API")
        
        # Convert rows to a string representation
        # Limit to first 20 rows for brevity and to avoid token limits
        results_sample = rows[:20]
        results_str = self._serialize_data_for_llm(results_sample)
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
    
    async def orchestrate_analysis(self, question: str, db_type: str = "postgres") -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        Args:
            question: Natural language question from the user
            db_type: Database type being queried
            
        Returns:
            Final analysis result with supporting data
        """
        logger.info(f"Starting orchestrated analysis for question: {question} with database type: {db_type}")
        
        # Create a new session and initialize tools
        session_id = await self.state_manager.create_session(question)
        
        # Initialize data tools with the correct database type
        self.data_tools = DataTools(db_type=db_type)
        await self.data_tools.initialize(session_id)
        
        # Get the state for this session
        state = await self.state_manager.get_state(session_id)
        if not state:
            raise ValueError(f"Failed to create session state for question: {question}")
        
        # Load prompt template for orchestration
        system_prompt = self.render_template("orchestration_system.tpl", db_type=db_type)
        
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

    # Streaming method implementations for AnthropicClient
    async def generate_sql_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate SQL from a natural language prompt using Anthropic API with streaming
        """
        logger.info("Generating SQL using Anthropic API with streaming")
        session_id = str(uuid.uuid4())
        
        try:
            yield self._create_stream_event("status", 
                                           message="Starting SQL generation with Anthropic...", 
                                           session_id=session_id)
            
            # Anthropic streaming
            stream = self.client.messages.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system="You are a SQL expert. Generate only SQL code without explanations.",
                temperature=0.1,
                max_tokens=1000,
                stream=True
            )
            
            partial_content = ""
            chunk_count = 0
            
            for chunk in stream:
                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    content = chunk.delta.text
                    partial_content += content
                    chunk_count += 1
                    
                    yield self._create_stream_event("partial_sql", 
                                                   content=partial_content, 
                                                   is_complete=False,
                                                   chunk_index=chunk_count,
                                                   session_id=session_id)
            
            # Validate SQL
            sql = partial_content.strip()
            validation_status = "valid"
            if not sql or not any(keyword in sql.upper() for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE", "WITH"]):
                validation_status = "warning"
            
            yield self._create_stream_event("sql_complete", 
                                           sql=sql, 
                                           validation_status=validation_status,
                                           total_chunks=chunk_count,
                                           session_id=session_id)
            
        except Exception as e:
            logger.error(f"Error generating SQL with Anthropic streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="GENERATION_FAILED",
                                           message=f"Error generating SQL: {str(e)}",
                                           recoverable=True,
                                           session_id=session_id)
            raise

    async def generate_mongodb_query_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate MongoDB query using Anthropic API with streaming
        """
        logger.info("Generating MongoDB query using Anthropic API with streaming")
        session_id = str(uuid.uuid4())
        
        try:
            yield self._create_stream_event("status", 
                                           message="Starting MongoDB query generation with Anthropic...", 
                                           session_id=session_id)
            
            # Anthropic streaming
            stream = self.client.messages.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system="You are a MongoDB expert. Generate only JSON representing a valid MongoDB query.",
                temperature=0.1,
                max_tokens=1000,
                stream=True
            )
            
            partial_content = ""
            chunk_count = 0
            
            for chunk in stream:
                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    content = chunk.delta.text
                    partial_content += content
                    chunk_count += 1
                    
                    yield self._create_stream_event("partial_mongodb_query", 
                                                   content=partial_content, 
                                                   is_complete=False,
                                                   chunk_index=chunk_count,
                                                   session_id=session_id)
            
            # Validate JSON
            mongodb_query = partial_content.strip()
            validation_status = "valid"
            try:
                json.loads(mongodb_query)
            except json.JSONDecodeError:
                # Try to extract JSON from code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', mongodb_query)
                if json_match:
                    mongodb_query = json_match.group(1).strip()
                    try:
                        json.loads(mongodb_query)
                    except json.JSONDecodeError:
                        validation_status = "invalid"
                else:
                    validation_status = "invalid"
            
            yield self._create_stream_event("mongodb_query_complete", 
                                           query=mongodb_query, 
                                           validation_status=validation_status,
                                           total_chunks=chunk_count,
                                           session_id=session_id)
            
        except Exception as e:
            logger.error(f"Error generating MongoDB query with Anthropic streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="GENERATION_FAILED",
                                           message=f"Error generating MongoDB query: {str(e)}",
                                           recoverable=True,
                                           session_id=session_id)
            raise

    async def analyze_results_stream(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """
        Analyze query results using Anthropic API with streaming
        """
        logger.info(f"Analyzing {'vector search' if is_vector_search else 'query'} results using Anthropic API with streaming")
        session_id = str(uuid.uuid4())
        
        try:
            yield self._create_stream_event("status", 
                                           message="Starting results analysis with Anthropic...", 
                                           session_id=session_id)
            
            # Prepare data
            data_str = self._serialize_data_for_llm(rows[:100])
            
            if is_vector_search:
                prompt = f"""
                Analyze these vector search results and provide key insights:
                
                {data_str}
                
                Consider:
                1. Similarity patterns in the results
                2. Key information or themes present in the top results
                3. How well the results match the semantic meaning of the query
                4. Any patterns in the metadata of the results
                
                Format your analysis in markdown with clean sections and bullet points.
                """
            else:
                prompt = f"""
                Analyze these SQL query results and provide key insights:
                
                {data_str}
                
                Consider:
                1. Key patterns and trends
                2. Notable outliers
                3. Statistical observations
                4. Business implications
                
                Format your analysis in markdown with clean sections and bullet points.
                """
            
            # Anthropic streaming
            stream = self.client.messages.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                system="You are a data analyst providing clear, concise insights.",
                temperature=0.1,
                max_tokens=1500,
                stream=True
            )
            
            partial_content = ""
            chunk_count = 0
            
            for chunk in stream:
                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                    content = chunk.delta.text
                    partial_content += content
                    chunk_count += 1
                    
                    yield self._create_stream_event("analysis_chunk", 
                                                   text=partial_content, 
                                                   chunk_index=chunk_count,
                                                   is_final=False,
                                                   session_id=session_id)
            
            # Final analysis event
            yield self._create_stream_event("analysis_chunk", 
                                           text=partial_content.strip(), 
                                           chunk_index=chunk_count,
                                           is_final=True,
                                           total_chunks=chunk_count,
                                           session_id=session_id)
            
        except Exception as e:
            logger.error(f"Error analyzing results with Anthropic streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="ANALYSIS_FAILED",
                                           message=f"Error analyzing results: {str(e)}",
                                           recoverable=True,
                                           session_id=session_id)
            raise

    async def orchestrate_analysis_stream(self, question: str, db_type: str = "postgres") -> AsyncIterator[Dict[str, Any]]:
        """
        Orchestrate a multi-step analysis process using available tools with streaming (Anthropic)
        """
        logger.info(f"Starting orchestrated analysis streaming with Anthropic for question: {question}")
        session_id = str(uuid.uuid4())
        
        try:
            yield self._create_stream_event("status", 
                                           message="Initializing orchestrated analysis with Anthropic...", 
                                           session_id=session_id)
            
            # Note: For brevity, this is a simplified implementation
            # A full implementation would mirror the OpenAI orchestration but adapted for Anthropic's API
            yield self._create_stream_event("status", 
                                           message="Anthropic orchestration streaming is simplified for now", 
                                           session_id=session_id)
            
            yield self._create_stream_event("analysis_chunk", 
                                           text=f"Anthropic-based analysis for '{question}' using {db_type} database would be implemented here.", 
                                           chunk_index=1,
                                           is_final=True,
                                           session_id=session_id)
            
        except Exception as e:
            logger.error(f"Error in Anthropic orchestration streaming: {str(e)}")
            yield self._create_stream_event("error", 
                                           error_code="ORCHESTRATION_FAILED",
                                           message=f"Error in Anthropic orchestration: {str(e)}",
                                           recoverable=False,
                                           session_id=session_id)
            raise

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
    
    async def analyze_results(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> str:
        """
        Analyze query results using local LLM
        
        Args:
            rows: Query results as a list of dictionaries
            is_vector_search: Whether the results are from a vector search
            
        Returns:
            Analysis as a string
        """
        logger.info(f"Analyzing {'vector search' if is_vector_search else 'query'} results using local LLM")
        
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
    
    async def orchestrate_analysis(self, question: str, db_type: str = "postgres") -> Dict[str, Any]:
        """
        Orchestrate a multi-step analysis process using available tools
        
        Args:
            question: Natural language question from the user
            db_type: Database type being queried
            
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

    # Streaming method implementations for LocalLLMClient
    async def generate_sql_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate SQL with streaming (placeholder implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Local LLM SQL generation not implemented", session_id=session_id)
        yield self._create_stream_event("sql_complete", sql="SELECT * FROM users LIMIT 10", validation_status="warning", session_id=session_id)
    
    async def generate_mongodb_query_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate MongoDB query with streaming (placeholder implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Local LLM MongoDB generation not implemented", session_id=session_id)
        yield self._create_stream_event("mongodb_query_complete", query='{"collection": "users", "pipeline": [{"$limit": 10}]}', validation_status="warning", session_id=session_id)
    
    async def analyze_results_stream(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """Analyze results with streaming (placeholder implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Local LLM analysis not implemented", session_id=session_id)
        yield self._create_stream_event("analysis_chunk", text="Local LLM analysis not implemented", chunk_index=1, is_final=True, session_id=session_id)
    
    async def orchestrate_analysis_stream(self, question: str, db_type: str = "postgres") -> AsyncIterator[Dict[str, Any]]:
        """Orchestrate analysis with streaming (placeholder implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Local LLM orchestration not implemented", session_id=session_id)
        yield self._create_stream_event("analysis_chunk", text="Local LLM orchestration not implemented", chunk_index=1, is_final=True, session_id=session_id)

class DummyLLMClient(LLMClient):
    """
    Dummy client for simulating API calls without using real LLM APIs.
    
    This client returns predefined responses for different templates
    to enable testing the cross-database orchestration system.
    """
    
    def __init__(self, response_mode: str = "success"):
        """
        Initialize the dummy client.
        
        Args:
            response_mode: Mode that determines response behavior
                         "success": All operations succeed
                         "validation_fail": Plan validation fails
                         "error": Simulates errors in LLM responses
        """
        super().__init__()
        self.model_name = "dummy-model"
        self.response_mode = response_mode
        self.client = self  # Use self as the client for chat.completions.create
        
        # Set up dummy response templates
        self._setup_dummy_responses()
    
    def _setup_dummy_responses(self):
        """Set up predefined responses for different templates"""
        # Map template names to response generators
        self.template_responses = {
            "schema_classifier.tpl": self._generate_classifier_response,
            "orchestration_plan.tpl": self._generate_plan_response,
            "validation_check.tpl": self._generate_validation_response,
            "plan_optimization.tpl": self._generate_optimization_response,
            "result_aggregator.tpl": self._generate_aggregation_response,
            "dry_run_analysis.tpl": self._generate_dry_run_response
        }
    
    def _generate_classifier_response(self, **kwargs):
        """Generate response for database classification"""
        if self.response_mode == "error":
            return {"content": "Error generating classification"}
        
        # Extract user question to make response somewhat relevant
        question = kwargs.get("user_question", "")
        
        # Determine databases to include based on question keywords
        databases = []
        if "user" in question.lower() or "customer" in question.lower():
            databases.append("postgres")
        if "document" in question.lower() or "content" in question.lower():
            databases.append("mongodb")
        if "similar" in question.lower() or "like" in question.lower():
            databases.append("qdrant")
        if "message" in question.lower() or "chat" in question.lower():
            databases.append("slack")
            
        # Default to postgres if nothing matched
        if not databases:
            databases = ["postgres"]
        
        response = {
            "selected_databases": databases,
            "rationale": {
                database: f"Selected based on relevance to query: '{question}'"
                for database in databases
            }
        }
        
        return {"content": json.dumps(response, indent=2)}
    
    def _generate_plan_response(self, **kwargs):
        """Generate a dummy query plan"""
        if self.response_mode == "error":
            return {"content": "Error generating plan"}
        
        # Extract parameters to make response somewhat relevant
        question = kwargs.get("user_question", "")
        db_candidates = kwargs.get("db_candidates", ["postgres"])
        
        # Create a simple plan with one operation per database type
        operations = []
        for i, db_type in enumerate(db_candidates):
            op_id = f"op{i+1}"
            
            if db_type == "postgres":
                operations.append({
                    "id": op_id,
                    "db_type": "postgres",
                    "source_id": "postgres_main",
                    "params": {
                        "query": f"SELECT * FROM users WHERE active = true LIMIT 10 /* {question} */",
                        "params": []
                    },
                    "depends_on": []
                })
            elif db_type == "mongodb":
                operations.append({
                    "id": op_id,
                    "db_type": "mongodb",
                    "source_id": "mongodb_main",
                    "params": {
                        "collection": "users",
                        "pipeline": [
                            {"$match": {"active": True}},
                            {"$limit": 10}
                        ]
                    },
                    "depends_on": []
                })
            elif db_type == "qdrant":
                operations.append({
                    "id": op_id,
                    "db_type": "qdrant",
                    "source_id": "qdrant_products",
                    "params": {
                        "collection": "products",
                        "vector": [0.1, 0.2, 0.3],
                        "filter": {"category": "electronics"},
                        "limit": 10
                    },
                    "depends_on": []
                })
            elif db_type == "slack":
                operations.append({
                    "id": op_id,
                    "db_type": "slack",
                    "source_id": "slack_main",
                    "params": {
                        "channels": ["general"],
                        "query": question,
                        "date_from": "2023-01-01",
                        "date_to": "2023-12-31"
                    },
                    "depends_on": []
                })
        
        # If we have multiple databases, add a join operation
        if len(operations) > 1:
            join_op = {
                "id": "join_op",
                "db_type": "postgres",
                "source_id": "postgres_main",
                "params": {
                    "query": "SELECT * FROM joined_data",
                    "params": []
                },
                "depends_on": [op["id"] for op in operations]
            }
            operations.append(join_op)
        
        plan = {
            "metadata": {
                "description": f"Plan for: {question}",
                "databases_used": db_candidates
            },
            "operations": operations
        }
        
        return {"content": json.dumps(plan, indent=2)}
    
    def _generate_validation_response(self, **kwargs):
        """Generate a validation response"""
        if self.response_mode == "error":
            return {"content": "Error validating plan"}
        
        if self.response_mode == "validation_fail":
            validation = {
                "valid": False,
                "errors": [
                    {
                        "operation_id": "op1",
                        "error_type": "invalid_table",
                        "description": "Table 'users' does not exist in schema registry"
                    }
                ],
                "warnings": [],
                "suggestions": [
                    {
                        "operation_id": "op1",
                        "suggestion_type": "alternative",
                        "description": "Consider using 'customers' table instead"
                    }
                ]
            }
        else:
            validation = {
                "valid": True,
                "errors": [],
                "warnings": [
                    {
                        "operation_id": "op1",
                        "warning_type": "performance",
                        "description": "Consider adding a limit to the query for better performance"
                    }
                ],
                "suggestions": [
                    {
                        "operation_id": "op1",
                        "suggestion_type": "optimization",
                        "description": "Add an index on the column being filtered"
                    }
                ]
            }
        
        return {"content": json.dumps(validation, indent=2)}
    
    def _generate_optimization_response(self, **kwargs):
        """Generate an optimization response"""
        if self.response_mode == "error":
            return {"content": "Error optimizing plan"}
        
        # Get the original plan to optimize
        original_plan = kwargs.get("original_plan", "{}")
        try:
            plan_dict = json.loads(original_plan)
            
            # Add optimization metadata
            plan_dict["metadata"]["optimization_notes"] = "Optimized by pushing filters earlier in the pipeline"
            
            # Make a small change to each operation to simulate optimization
            for op in plan_dict.get("operations", []):
                if op["db_type"] == "postgres" and "params" in op and "query" in op["params"]:
                    # Add a comment to indicate optimization
                    op["params"]["query"] += " /* optimized */"
                elif op["db_type"] == "mongodb" and "params" in op and "pipeline" in op["params"]:
                    # Add a comment field to indicate optimization
                    op["params"]["pipeline"].append({"$comment": "optimized"})
            
            return {"content": json.dumps(plan_dict, indent=2)}
        except Exception:
            # If parsing fails, return a generic optimized plan
            return {"content": original_plan}
    
    def _generate_aggregation_response(self, **kwargs):
        """Generate an aggregation response"""
        if self.response_mode == "error":
            return {"content": "Error aggregating results"}
        
        # Create a simple aggregation result
        aggregation = {
            "aggregated_results": [
                {"id": 1, "name": "User 1", "email": "user1@example.com"},
                {"id": 2, "name": "User 2", "email": "user2@example.com"}
            ],
            "summary_statistics": {
                "total_count": 2,
                "sources_used": 2
            },
            "key_insights": [
                "Found 2 matching records across databases"
            ],
            "aggregation_notes": {
                "join_strategy": "inner join on id field"
            }
        }
        
        return {"content": json.dumps(aggregation, indent=2)}
    
    def _generate_dry_run_response(self, **kwargs):
        """Generate a dry run analysis response"""
        if self.response_mode == "error":
            return {"content": "Error analyzing dry run"}
        
        # Create a simple dry run analysis
        analysis = {
            "overall_assessment": "PROCEED",
            "confidence": 0.9,
            "analysis": {
                "correctness": {
                    "score": 9,
                    "notes": "Plan appears correct based on schema validation"
                },
                "completeness": {
                    "score": 8,
                    "notes": "Plan covers all aspects of the user query"
                },
                "efficiency": {
                    "score": 7,
                    "notes": "Query plan could be optimized but is generally efficient"
                },
                "robustness": {
                    "score": 8,
                    "notes": "Plan handles expected edge cases"
                },
                "security": {
                    "score": 9,
                    "notes": "No security concerns detected"
                }
            },
            "critical_issues": [],
            "recommendations": {
                "proceed_conditions": "Plan can proceed as is",
                "modifications": []
            }
        }
        
        return {"content": json.dumps(analysis, indent=2)}
    
    async def chat_completions_create(self, model=None, messages=None, **kwargs):
        """
        Simulate the chat.completions.create method of OpenAI/Anthropic.
        
        Args:
            model: Model name (ignored)
            messages: List of message objects
            **kwargs: Additional parameters
            
        Returns:
            Simulated response object
        """
        # Extract the user message
        user_message = None
        for message in messages:
            if message.get("role") == "user":
                user_message = message.get("content")
                break
        
        # Determine which template is being used by looking for key phrases
        template_type = None
        for template_name in self.template_responses:
            template_content = self.render_template(template_name)
            if user_message and any(phrase in user_message for phrase in template_content.split('\n')[:3]):
                template_type = template_name
                break
        
        # Get template variables from the user message
        template_vars = {}
        if template_type:
            # Extract variables from user message - this is a simplified approach
            for line in user_message.split('\n'):
                if "# User Question" in line and ":" in line:
                    template_vars["user_question"] = line.split(":", 1)[1].strip()
                    break
        
        # Generate response based on template type
        if template_type and template_type in self.template_responses:
            response_content = self.template_responses[template_type](**template_vars)
        else:
            # Fallback response
            response_content = {"content": "I'm a dummy LLM response"}
        
        # Create a response object similar to what the API would return
        response = type('DummyResponse', (), {
            'choices': [
                type('Choice', (), {
                    'message': type('Message', (), response_content)
                })
            ]
        })
        
        return response
    
    async def generate_sql(self, prompt: str) -> str:
        """Generate SQL from a natural language prompt"""
        return "SELECT * FROM users LIMIT 10"
    
    async def generate_mongodb_query(self, prompt: str) -> str:
        """Generate MongoDB query from a natural language prompt"""
        return '{"collection": "users", "pipeline": [{"$match": {}}, {"$limit": 10}]}'
    
    async def analyze_results(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> str:
        """Analyze query results"""
        return f"Analysis of {len(rows)} rows: Sample data looks good."
    
    async def orchestrate_analysis(self, question: str, db_type: str = "postgres") -> Dict[str, Any]:
        """Orchestrate a multi-step analysis"""
        return {
            "session_id": "dummy-session",
            "question": question,
            "analysis": f"Analysis for '{question}' using {db_type} database: Found relevant data.",
            "steps_taken": 3,
            "state": {"status": "completed"}
        }

    # Streaming method implementations for DummyLLMClient
    async def generate_sql_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate SQL with streaming (dummy implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Starting dummy SQL generation...", session_id=session_id)
        yield self._create_stream_event("partial_sql", content="SELECT * FROM", is_complete=False, chunk_index=1, session_id=session_id)
        yield self._create_stream_event("partial_sql", content="SELECT * FROM users", is_complete=False, chunk_index=2, session_id=session_id)
        yield self._create_stream_event("sql_complete", sql="SELECT * FROM users LIMIT 10", validation_status="valid", session_id=session_id)
    
    async def generate_mongodb_query_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate MongoDB query with streaming (dummy implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Starting dummy MongoDB generation...", session_id=session_id)
        yield self._create_stream_event("partial_mongodb_query", content='{"collection":', is_complete=False, chunk_index=1, session_id=session_id)
        yield self._create_stream_event("mongodb_query_complete", query='{"collection": "users", "pipeline": [{"$match": {}}, {"$limit": 10}]}', validation_status="valid", session_id=session_id)
    
    async def analyze_results_stream(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """Analyze results with streaming (dummy implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Starting dummy analysis...", session_id=session_id)
        yield self._create_stream_event("analysis_chunk", text=f"Analyzing {len(rows)} rows of data...", chunk_index=1, is_final=False, session_id=session_id)
        yield self._create_stream_event("analysis_chunk", text=f"Analysis complete: Found {len(rows)} records with sample data.", chunk_index=2, is_final=True, session_id=session_id)
    
    async def orchestrate_analysis_stream(self, question: str, db_type: str = "postgres") -> AsyncIterator[Dict[str, Any]]:
        """Orchestrate analysis with streaming (dummy implementation)"""
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("status", message="Starting dummy orchestration...", session_id=session_id)
        yield self._create_stream_event("progress", step=1, total=3, percentage=33, current_operation="Loading metadata", session_id=session_id)
        yield self._create_stream_event("progress", step=2, total=3, percentage=66, current_operation="Executing query", session_id=session_id)
        yield self._create_stream_event("progress", step=3, total=3, percentage=100, current_operation="Generating analysis", session_id=session_id)
        yield self._create_stream_event("analysis_chunk", text=f"Dummy analysis for '{question}' using {db_type} database: Found relevant data.", chunk_index=1, is_final=True, session_id=session_id)

class FallbackLLMClient(LLMClient):
    """
    Client that implements automatic fallbacks between different LLM providers.
    If the primary client fails, it will try alternative clients in sequence.
    """
    
    def __init__(self, clients: List[LLMClient] = None):
        """
        Initialize with a list of LLM clients to try in order
        
        Args:
            clients: List of LLM clients in priority order (first is primary)
        """
        super().__init__()
        self.clients = clients or []
        
        # Set model name to the primary client's model name, if available
        if self.clients and hasattr(self.clients[0], 'model_name'):
            self.model_name = self.clients[0].model_name
        else:
            self.model_name = "fallback-model"
            
        # For client access, forward to primary client
        if self.clients:
            self.client = self.clients[0].client
        
        logger.info(f"Initialized FallbackLLMClient with {len(self.clients)} clients")
        for i, client in enumerate(self.clients):
            logger.info(f"  Client {i+1}: {client.__class__.__name__} ({getattr(client, 'model_name', 'unknown')})")
    
    async def _try_clients(self, method_name: str, *args, **kwargs) -> Any:
        """
        Try calling a method on each client in order until one succeeds
        
        Args:
            method_name: The name of the method to call
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Result from the first successful client
            
        Raises:
            Exception: If all clients fail
        """
        errors = []
        
        for i, client in enumerate(self.clients):
            try:
                method = getattr(client, method_name)
                result = await method(*args, **kwargs)
                
                # If this is not the primary client, log that we used a fallback
                if i > 0:
                    logger.info(f"Successfully used fallback client {i+1} ({client.__class__.__name__}) for {method_name}")
                
                return result
            except Exception as e:
                # Log the error and try the next client
                error_msg = str(e)
                # Only log the first 100 chars of error to avoid massive logs
                logger.warning(f"Client {i+1} ({client.__class__.__name__}) failed for {method_name}: {error_msg[:100]}...")
                errors.append(f"Client {i+1} ({client.__class__.__name__}): {error_msg}")
                continue
        
        # If we get here, all clients failed
        raise Exception(f"All LLM clients failed for {method_name}: {'; '.join(errors)}")
    
    async def generate_sql(self, prompt: str) -> str:
        """Generate SQL from a natural language prompt"""
        return await self._try_clients("generate_sql", prompt)
    
    async def generate_mongodb_query(self, prompt: str) -> str:
        """Generate MongoDB query from a natural language prompt"""
        return await self._try_clients("generate_mongodb_query", prompt)
    
    async def analyze_results(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> str:
        """Analyze query results"""
        return await self._try_clients("analyze_results", rows, is_vector_search)
    
    async def orchestrate_analysis(self, question: str, db_type: str = "postgres") -> Dict[str, Any]:
        """Orchestrate a multi-step analysis"""
        return await self._try_clients("orchestrate_analysis", question, db_type)

    # Streaming method implementations for FallbackLLMClient
    async def generate_sql_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate SQL with streaming using fallback clients"""
        async for event in await self._try_clients_stream("generate_sql_stream", prompt):
            yield event
    
    async def generate_mongodb_query_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Generate MongoDB query with streaming using fallback clients"""
        async for event in await self._try_clients_stream("generate_mongodb_query_stream", prompt):
            yield event
    
    async def analyze_results_stream(self, rows: List[Dict[str, Any]], is_vector_search: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """Analyze results with streaming using fallback clients"""
        async for event in await self._try_clients_stream("analyze_results_stream", rows, is_vector_search):
            yield event
    
    async def orchestrate_analysis_stream(self, question: str, db_type: str = "postgres") -> AsyncIterator[Dict[str, Any]]:
        """Orchestrate analysis with streaming using fallback clients"""
        async for event in await self._try_clients_stream("orchestrate_analysis_stream", question, db_type):
            yield event

    async def _try_clients_stream(self, method_name: str, *args, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        Try calling a streaming method on each client in order until one succeeds
        
        Args:
            method_name: The name of the streaming method to call
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Yields:
            Events from the first successful client
        """
        errors = []
        
        for i, client in enumerate(self.clients):
            try:
                method = getattr(client, method_name)
                
                # If this is not the primary client, yield a status event about using fallback
                if i > 0:
                    yield self._create_stream_event("status", 
                                                   message=f"Using fallback client {i+1} ({client.__class__.__name__})",
                                                   session_id=str(uuid.uuid4()))
                
                async for event in method(*args, **kwargs):
                    yield event
                return  # Success, no need to try more clients
                
            except Exception as e:
                # Log the error and try the next client
                error_msg = str(e)
                logger.warning(f"Client {i+1} ({client.__class__.__name__}) failed for {method_name}: {error_msg[:100]}...")
                errors.append(f"Client {i+1} ({client.__class__.__name__}): {error_msg}")
                continue
        
        # If we get here, all clients failed
        session_id = str(uuid.uuid4())
        yield self._create_stream_event("error", 
                                       error_code="ALL_CLIENTS_FAILED",
                                       message=f"All LLM clients failed for {method_name}: {'; '.join(errors)}",
                                       recoverable=False,
                                       session_id=session_id)
        raise Exception(f"All LLM clients failed for {method_name}: {'; '.join(errors)}")

def get_llm_client() -> LLMClient:
    """
    Factory function to get the appropriate LLM client based on configuration
    
    Returns:
        An instance of LLMClient
    """
    settings = Settings()
    
    # Create a list to hold available clients
    clients = []
    
    # Check if we want to use the dummy client
    if os.environ.get("USE_DUMMY_LLM") == "true":
        response_mode = os.environ.get("DUMMY_RESPONSE_MODE", "success")
        logger.info(f"Using dummy LLM client with mode: {response_mode}")
        return DummyLLMClient(response_mode=response_mode)
    
    # Try to initialize Anthropic client if API key is available
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            logger.info("Initializing Anthropic client")
            clients.append(AnthropicClient())
        except Exception as e:
            logger.warning(f"Failed to initialize Anthropic client: {str(e)}")
    
    # Try to initialize OpenAI client if API key and URL are available
    if settings.LLM_API_URL and settings.LLM_API_KEY:
        try:
            logger.info("Initializing OpenAI client")
            clients.append(OpenAIClient())
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {str(e)}")
    
    # Try to initialize local model if path and type are available
    if settings.MODEL_PATH and settings.MODEL_TYPE:
        try:
            logger.info("Initializing local LLM client")
            clients.append(LocalLLMClient())
        except Exception as e:
            logger.warning(f"Failed to initialize local LLM client: {str(e)}")
    
    # Create and return fallback client if we have at least one client
    if clients:
        return FallbackLLMClient(clients)
    else:
        raise ValueError("No valid LLM clients could be initialized. Check your configuration.")

class OrchestrationClassificationClient:
    """
    Lightweight LLM client for fast orchestration classification operations.
    Uses AWS Bedrock with Claude Haiku for 1-token classification.
    """
    
    def __init__(self):
        self.settings = Settings()
        self.client = None
        self.enabled = True
        self.model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
        
        self._initialize_client()
        logger.info(f"Initialized OrchestrationClassificationClient with Bedrock")
    
    def _initialize_client(self):
        """Initialize AWS Bedrock client with proper credential handling."""
        try:
            import boto3
            import os
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # Use same credential pattern as trivial client
            region = os.getenv("AWS_REGION", "us-east-1")
            
            try:
                self.client = boto3.client(
                    "bedrock-runtime",
                    region_name=region
                )
                
                # Test credentials by making a simple call to bedrock (not bedrock-runtime)
                # Use a separate client just for testing credentials
                test_client = boto3.client("bedrock", region_name=region)
                test_client.list_foundation_models()
                logger.info(f"Successfully initialized Bedrock classification client in region: {region}")
                
            except NoCredentialsError:
                logger.error("AWS credentials not found for classification client")
                self.enabled = False
                raise ValueError("AWS credentials not found. Please configure AWS credentials via environment variables, AWS profile, or IAM role.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'UnauthorizedOperation':
                    logger.error("AWS credentials don't have permission to access Bedrock")
                    self.enabled = False
                    raise ValueError("AWS credentials don't have permission to access Bedrock. Please check IAM permissions.")
                else:
                    logger.error(f"AWS Bedrock initialization failed: {e}")
                    self.enabled = False
                    raise ValueError(f"AWS Bedrock initialization failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error calling Bedrock: {e}")
                self.enabled = False
                raise ValueError(f"Unexpected error calling Bedrock: {e}")
                
        except Exception as e:
            logger.error(f"Failed to initialize classification client: {e}")
            self.enabled = False
            raise
    
    def is_enabled(self) -> bool:
        """Check if the classification client is properly enabled."""
        return self.enabled
    
    async def classify_operation(self, request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify an operation using ultra-fast LLM routing with 1-token response.
        
        Args:
            request: The user's request text
            context: Context dictionary with block information
            
        Returns:
            Dict with classification results
        """
        if not self.enabled:
            raise ValueError("Classification client is not available")
        
        try:
            import json
            import time
            
            logger.info(f"🧠 CLASSIFICATION: Classifying request: '{request}'")
            logger.info(f"🧠 CLASSIFICATION: Context type: {context.get('type', 'unknown')}")
            
            # Build the prompt for 1-token classification (same as TypeScript version)
            prompt = f"""Classify this user request as either TRIVIAL or DATA_ANALYSIS.

TRIVIAL operations (use fast client):
- Grammar/spelling fixes
- Tone adjustments  
- Text formatting
- Simple rewrites
- Content generation
- Basic text improvements

DATA_ANALYSIS operations (use powerful client):
- Data analysis queries
- Statistical calculations
- Database operations
- Chart/graph generation
- Complex data insights
- Cross-database queries

Request: "{request}"
Context: {context.get('type', 'text')} block, {len(context.get('content', ''))} characters

Respond with exactly one token: TRIVIAL or DATA_ANALYSIS"""

            start_time = time.time()
            
            # Call Bedrock with 1-token limit (same model as TypeScript version)
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ]
                })
            )
            
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Parse response
            response_body = json.loads(response['body'].read())
            output = response_body['content'][0]['text'].strip().upper()
            
            logger.info(f"🧠 CLASSIFICATION: Bedrock response: '{output}' in {int(processing_time)}ms")
            
            # Determine if trivial - look for TRIVIAL token in response
            is_trivial = 'TRIVIAL' in output
            
            # Calculate confidence based on response clarity and processing time
            confidence = 0.9 if output in ['TRIVIAL', 'DATA_ANALYSIS'] else 0.7
            if processing_time < 300:
                confidence += 0.05
            
            # Determine operation type (same logic as TypeScript version)
            def infer_operation_type(request_text: str, is_trivial: bool) -> str:
                req = request_text.lower()
                if is_trivial:
                    if 'grammar' in req or 'spell' in req or 'fix' in req:
                        return 'grammar_fix'
                    if 'tone' in req or 'formal' in req or 'casual' in req:
                        return 'tone_adjustment'
                    if 'format' in req or 'indent' in req:
                        return 'formatting'
                    if 'rephrase' in req or 'rewrite' in req:
                        return 'text_transformation'
                    return 'simple_edit'
                else:
                    if 'analyze' in req or 'data' in req:
                        return 'data_analysis'
                    if 'generate' in req or 'create' in req:
                        return 'content_generation'
                    if 'research' in req or 'find' in req:
                        return 'research_operation'
                    return 'complex_operation'
            
            operation_type = infer_operation_type(request, is_trivial)
            estimated_time = 500 if is_trivial else 3000
            tier = 'trivial' if is_trivial else 'overpowered'
            
            logger.info(f"🧠 CLASSIFICATION: Final classification: {tier.upper()} ({operation_type}, {int(confidence * 100)}% confidence)")
            
            return {
                "tier": tier,
                "confidence": confidence,
                "reasoning": f"Bedrock LLM classification: {'TRIVIAL (fast client)' if is_trivial else 'DATA ANALYSIS (overpowered)'} in {int(processing_time)}ms with {int(confidence * 100)}% confidence",
                "estimated_time": estimated_time,
                "operation_type": operation_type
            }
            
        except Exception as e:
            logger.error(f"🧠 CLASSIFICATION: LLM classification failed: {e}")
            # Fallback to regex classification (same as TypeScript version)
            import re
            data_analysis_patterns = r'\b(analyze|analysis|statistical|metrics|calculate|chart|graph|data\s+insight|database\s+quer|sql\s+quer)\b'
            is_data_analysis = bool(re.search(data_analysis_patterns, request, re.IGNORECASE))
            
            tier = 'overpowered' if is_data_analysis else 'trivial'
            operation_type = 'data_analysis' if is_data_analysis else 'text_editing'
            
            logger.info(f"🧠 CLASSIFICATION: Fallback classification: {tier.upper()} ({operation_type})")
            
            return {
                "tier": tier,
                "confidence": 0.7,
                "reasoning": f"Fallback regex classification: {'DATA ANALYSIS detected' if is_data_analysis else 'TEXT EDITING (default)'} due to LLM error: {str(e)}",
                "estimated_time": 3000 if is_data_analysis else 500,
                "operation_type": operation_type
            }

# Global instance for the classification client
_classification_client = None

def get_classification_client() -> OrchestrationClassificationClient:
    """Get the global classification client instance."""
    global _classification_client
    if _classification_client is None:
        _classification_client = OrchestrationClassificationClient()
    return _classification_client
