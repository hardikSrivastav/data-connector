"""
LangGraph Tool Execution Node

This node is responsible for executing tools from the tool registry system
based on LLM decision-making. It integrates with the Bedrock client for
tool selection and execution coordination.
"""

import logging
import json
import time
import asyncio
from typing import Any, Dict, List, Optional, TypedDict
try:
    from typing import Annotated
except ImportError:
    # Python 3.8 compatibility
    from typing_extensions import Annotated
from datetime import datetime
import traceback

from ...tools.registry import ToolRegistry, ToolCall, ExecutionResult
from ...config.settings import Settings
from ..graphs.bedrock_client import BedrockLangGraphClient as BedrockLLMClient
from ..output_aggregator import get_output_integrator

# Configure logging
logger = logging.getLogger(__name__)

class ToolExecutionState(TypedDict):
    """State for tool execution workflow."""
    user_query: str
    tool_calls: List[ToolCall]
    execution_results: List[ExecutionResult]
    selected_tools: List[str]
    execution_plan: Optional[Dict[str, Any]]
    errors: List[str]
    metadata: Dict[str, Any]

class ToolExecutionNode:
    """
    LangGraph node for executing tools from the registry.
    
    This node handles:
    1. Tool selection based on user query analysis
    2. Tool execution coordination
    3. Result aggregation and formatting
    4. Error handling and recovery
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the tool execution node.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.tool_registry = ToolRegistry(settings)
        self.llm_client = BedrockLLMClient(settings)
        
        # Initialize output aggregator integration
        self.output_integrator = get_output_integrator()
        
        logger.info("ToolExecutionNode initialized with real Bedrock client and output aggregator")
    
    async def _ensure_tools_registered(self):
        """Ensure tools are registered in the registry."""
        try:
            # Check if tools are already registered
            available_tools = await self.tool_registry.get_available_tools()
            if len(available_tools) > 0:
                logger.info(f"Tools already registered: {len(available_tools)} tools found")
                return
            
            logger.info("Registering tools in ToolExecutionNode...")
            
            # Register general tools
            await self.tool_registry.register_general_tools()
            logger.info("General tools registered")
            
            # Register database-specific tools for all configured databases
            # Use proper database-specific URIs instead of relying on connection_uri
            db_configs = [
                ('postgres', self._get_postgres_uri()),
                ('mongo', self.tool_registry.settings.MONGODB_URI),
                ('shopify', self.tool_registry.settings.SHOPIFY_URI),
                ('qdrant', self.tool_registry.settings.QDRANT_URI),
                ('slack', self.tool_registry.settings.SLACK_URI),
                ('ga4', self._get_ga4_uri())
            ]
            
            for db_type, connection_uri in db_configs:
                if connection_uri:
                    try:
                        await self.tool_registry.register_database_tools(db_type, connection_uri)
                        logger.info(f"Registered {db_type} tools")
                    except Exception as e:
                        logger.warning(f"Failed to register {db_type} tools: {e}")
            
            # Log final tool count
            final_tools = await self.tool_registry.get_available_tools()
            logger.info(f"ToolExecutionNode tool registration complete: {len(final_tools)} tools available")
            
        except Exception as e:
            logger.error(f"Failed to register tools: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_postgres_uri(self) -> str:
        """Get PostgreSQL-specific URI without affecting other database types."""
        settings = self.tool_registry.settings
        return settings.db_dsn  # Use direct PostgreSQL DSN instead of connection_uri
    
    def _get_ga4_uri(self) -> str:
        """Get GA4-specific URI."""
        settings = self.tool_registry.settings
        if settings.GA4_KEY_FILE and settings.GA4_PROPERTY_ID:
            return f"ga4://{settings.GA4_PROPERTY_ID}"
        return None
    
    def _resolve_step_dependencies(
        self, 
        parameters: Dict[str, Any], 
        step_outputs: Dict[str, Any], 
        execution_results: List[Any]
    ) -> Dict[str, Any]:
        """
        Resolve step dependencies in tool parameters.
        
        Replaces placeholders like 'output_from_step_2' with actual results.
        
        Args:
            parameters: Original tool parameters
            step_outputs: Dictionary of step outputs
            execution_results: List of execution results
            
        Returns:
            Parameters with resolved dependencies
        """
        if not parameters:
            return parameters
            
        resolved_params = {}
        
        for key, value in parameters.items():
            if isinstance(value, str):
                # Check for step output placeholders
                if value.startswith('output_from_step_'):
                    try:
                        # Extract step number
                        step_num = int(value.split('_')[-1])
                        step_key = f"step_{step_num}"
                        
                        if step_key in step_outputs:
                            resolved_value = step_outputs[step_key]
                            logger.info(f"Resolved {value} to actual result: {str(resolved_value)[:100]}...")
                            resolved_params[key] = resolved_value
                        elif step_num <= len(execution_results):
                            # Try to get from execution results
                            result = execution_results[step_num - 1]
                            if result.success and result.result:
                                resolved_value = result.result
                                logger.info(f"Resolved {value} from execution results: {str(resolved_value)[:100]}...")
                                resolved_params[key] = resolved_value
                            else:
                                logger.warning(f"Could not resolve {value}: step failed or no result")
                                resolved_params[key] = value
                        else:
                            logger.warning(f"Could not resolve {value}: step not found")
                            resolved_params[key] = value
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse step reference {value}: {e}")
                        resolved_params[key] = value
                else:
                    resolved_params[key] = value
            else:
                resolved_params[key] = value
                
        return resolved_params
    
    def _validate_tool_parameters(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance tool parameters before execution."""
        validated_params = parameters.copy()
        
        # Get tool information from registry
        tool_info = None
        for tool in self.tool_registry.tools.values():
            if tool["tool_id"] == tool_id:
                tool_info = tool
                break
        
        if not tool_info:
            logger.warning(f"Could not find tool info for {tool_id}")
            return validated_params
        
        required_params = tool_info.get("parameters", {})
        
        # Add missing parameters with intelligent defaults
        for param_name, param_type in required_params.items():
            if param_name not in validated_params:
                logger.warning(f"Missing required parameter '{param_name}' for {tool_id}, adding default")
                
                if param_name == "query":
                    if "shopify" in tool_id:
                        validated_params[param_name] = "SELECT id, title, status FROM products WHERE status = 'active' LIMIT 10"
                    elif "postgres" in tool_id:
                        validated_params[param_name] = "SELECT * FROM sample_orders WHERE created_at >= NOW() - INTERVAL '7 days' LIMIT 10"
                    elif "mongo" in tool_id:
                        validated_params[param_name] = {
                            "collection": "sample_orders", 
                            "pipeline": [{"$match": {"status": "active"}}, {"$limit": 10}]
                        }
                elif param_name == "nl_prompt":
                    validated_params[param_name] = "Analyze performance and provide optimization recommendations"
                elif param_name == "data":
                    validated_params[param_name] = []  # Empty list as safe default
                elif param_name == "filepath":
                    validated_params[param_name] = f"/tmp/tool_output_{tool_id.replace('.', '_')}.csv"
                elif param_name == "table_name":
                    validated_params[param_name] = "sample_orders"
                elif param_name == "collection_name":
                    validated_params[param_name] = "sample_orders"
                else:
                    # Generic defaults
                    if param_type == "str":
                        validated_params[param_name] = "default_value"
                    elif param_type == "int":
                        validated_params[param_name] = 10
                    elif param_type == "bool":
                        validated_params[param_name] = True
                    elif param_type == "dict":
                        validated_params[param_name] = {}
                    elif param_type == "list":
                        validated_params[param_name] = []
        
        return validated_params

    async def execute_node(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method for the tool node.
        
        Args:
            input_data: Input containing user_query, session_id and other parameters
            
        Returns:
            Dictionary containing execution results and metadata
        """
        logger.info(f"ToolExecutionNode.execute_node called with query: {input_data.get('user_query', 'N/A')[:100]}...")
        
        # Extract session_id for output aggregation
        session_id = input_data.get("session_id")
        if not session_id:
            logger.warning("No session_id provided to ToolExecutionNode, output aggregation will be limited")
        
        # Ensure tools are registered before proceeding
        await self._ensure_tools_registered()
        
        # Initialize state
        state: ToolExecutionState = {
            "user_query": input_data.get("user_query", ""),
            "tool_calls": [],
            "execution_results": [],
            "selected_tools": [],
            "execution_plan": None,
            "errors": [],
            "metadata": {
                "start_time": time.time(),
                "input_data": input_data,
                "session_id": session_id
            }
        }
        
        try:
            # Step 1: Analyze query and select tools
            state = await self.analyze_and_select_tools(state)
            
            # Step 2: Create execution plan
            state = await self.create_execution_plan(state)
            
            # Step 3: Execute tools
            state = await self.execute_tools(state)
            
            # Step 4: Synthesize results
            state = await self.synthesize_results(state)
            
            # Calculate total execution time
            state["metadata"]["total_execution_time"] = time.time() - state["metadata"]["start_time"]
            
            # Format final response
            if state["execution_results"]:
                final_response = self._format_final_response(
                    state["metadata"].get("synthesis_response", "No synthesis available"),
                    state["execution_results"],
                    state["metadata"]
                )
            else:
                final_response = f"No tools were executed successfully. Errors: {', '.join(state['errors'])}"
            
            logger.info(f"ToolExecutionNode completed successfully with {len(state['execution_results'])} results")
            
            # Calculate actual success rate
            successful_tools = sum(1 for r in state["execution_results"] if r.success)
            total_tools = len(state["execution_results"])
            success_rate = successful_tools / total_tools if total_tools > 0 else 0
            
            # Require at least 50% success rate and at least one successful tool
            is_successful = success_rate >= 0.5 and successful_tools > 0
            
            logger.info(f"Tool execution summary: {successful_tools}/{total_tools} tools successful ({success_rate:.1%})")
            
            # Capture outputs for output aggregator if session_id is available
            if session_id:
                try:
                    await self._capture_tool_execution_outputs(session_id, state)
                    logger.info(f"🔄 [OUTPUT_AGGREGATOR] Captured tool execution outputs for session {session_id}")
                except Exception as e:
                    logger.warning(f"🔄 [OUTPUT_AGGREGATOR] Failed to capture outputs: {e}")
            
            return {
                "response": final_response,
                "execution_results": state["execution_results"],
                "selected_tools": state["selected_tools"],
                "execution_plan": state["execution_plan"],
                "errors": state["errors"],
                "metadata": {
                    **state["metadata"],
                    "success_rate": success_rate,
                    "successful_tools": successful_tools,
                    "total_tools": total_tools
                },
                "success": is_successful
            }
            
        except Exception as e:
            logger.error(f"ToolExecutionNode execution failed: {e}")
            logger.error(traceback.format_exc())
            
            return {
                "response": f"Tool execution failed: {str(e)}",
                "execution_results": [],
                "selected_tools": [],
                "execution_plan": None,
                "errors": [str(e)],
                "metadata": state["metadata"],
                "success": False
            }
    
    async def analyze_and_select_tools(self, state: ToolExecutionState) -> ToolExecutionState:
        """
        Analyze user query and select appropriate tools.
        
        Args:
            state: Current execution state
            
        Returns:
            Updated state with selected tools
        """
        logger.info(f"Analyzing query for tool selection: {state['user_query'][:100]}...")
        
        try:
            # Store current query for fallback logic
            self._current_query = state['user_query']
            
            # Get available tools from registry
            available_tools = await self.tool_registry.get_available_tools()
            logger.info(f"Found {len(available_tools)} available tools")
            
            if not available_tools:
                logger.warning("No tools available in registry")
                state["errors"].append("No tools available for execution")
                return state
            
            # Create tool selection prompt
            tools_description = self._format_tools_for_llm(available_tools)
            selection_prompt = self._create_tool_selection_prompt(
                state["user_query"], 
                tools_description
            )
            
            # Use LLM to select tools
            logger.debug("Sending tool selection prompt to Bedrock")
            selection_response = await self.llm_client.generate_completion(
                prompt=selection_prompt,
                max_tokens=1000,
                temperature=0.1
            )
            
            # Parse tool selection response
            selected_tools = self._parse_tool_selection(selection_response, available_tools)
            logger.info(f"LLM selected {len(selected_tools)} tools: {[t['tool_id'] for t in selected_tools]}")
            
            # Update state
            state["selected_tools"] = [tool["tool_id"] for tool in selected_tools]
            state["metadata"]["tool_selection_response"] = selection_response
            state["metadata"]["available_tools_count"] = len(available_tools)
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to analyze and select tools: {e}")
            logger.error(traceback.format_exc())
            state["errors"].append(f"Tool selection failed: {str(e)}")
            return state
    
    async def create_execution_plan(self, state: ToolExecutionState) -> ToolExecutionState:
        """
        Create execution plan for selected tools.
        
        Args:
            state: Current execution state
            
        Returns:
            Updated state with execution plan
        """
        logger.info("Creating execution plan for selected tools")
        
        selected_tools = state.get("selected_tools", [])
        if not selected_tools:
            logger.warning("No tools selected for execution plan")
            state["errors"].append("No tools selected for execution plan")
            return state
        
        try:
            # Get detailed information about selected tools
            tool_details = []
            for tool_id in selected_tools:
                tool_info = await self.tool_registry.get_tool_info(tool_id)
                if tool_info:
                    tool_details.append(tool_info)
                    logger.info(f"🔧 DEBUG: Tool {tool_id} info: {tool_info}")
                else:
                    logger.warning(f"Tool {tool_id} not found in registry")
            
            if not tool_details:
                logger.error("No valid tool details found for execution plan")
                state["errors"].append("No valid tool details found")
                return state
            
            # Create execution plan prompt
            execution_plan_prompt = self._create_execution_plan_prompt(
                state["user_query"], 
                tool_details
            )
            
            logger.info(f"🔧 DEBUG: Execution plan prompt length: {len(execution_plan_prompt)}")
            logger.info(f"🔧 DEBUG: Execution plan prompt preview: {execution_plan_prompt[:500]}...")
            
            # Generate execution plan using LLM
            response = await self.llm_client.generate_completion(
                prompt=execution_plan_prompt,
                max_tokens=2000,
                temperature=0.1
            )
            
            logger.info(f"🔧 DEBUG: Raw LLM execution plan response: {response[:1000]}...")
            
            # Parse execution plan
            execution_plan = self._parse_execution_plan(response, tool_details)
            
            logger.info(f"🔧 DEBUG: Parsed execution plan: {json.dumps(execution_plan, indent=2)}")
            
            state["execution_plan"] = execution_plan
            logger.info(f"Execution plan created with {len(execution_plan.get('steps', []))} steps")
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to create execution plan: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            state["errors"].append(f"Execution plan creation failed: {str(e)}")
            return state
    
    async def execute_tools(self, state: ToolExecutionState) -> ToolExecutionState:
        """
        Execute tools based on the execution plan.
        
        Args:
            state: Current execution state
            
        Returns:
            Updated state with execution results
        """
        logger.info("Executing tools based on execution plan")
        
        execution_plan = state.get("execution_plan", {})
        if not execution_plan or "steps" not in execution_plan:
            logger.error("No execution plan found or plan has no steps")
            state["errors"].append("No execution plan available")
            return state
        
        try:
            # Create tool calls from execution plan
            tool_calls = self._create_tool_calls_from_plan(execution_plan, state["user_query"])
            
            logger.info(f"🔧 DEBUG: Created {len(tool_calls)} tool calls from execution plan")
            for i, tool_call in enumerate(tool_calls):
                logger.info(f"🔧 DEBUG: Tool call {i+1}: {tool_call.tool_id}")
                logger.info(f"🔧 DEBUG: Tool call {i+1} parameters: {tool_call.parameters}")
                logger.info(f"🔧 DEBUG: Tool call {i+1} context: {tool_call.context}")
            
            # Execute each tool call
            execution_results = []
            step_outputs = {}
            
            for i, tool_call in enumerate(tool_calls):
                logger.info(f"Executing tool call {i+1}/{len(tool_calls)}: {tool_call.tool_id}")
                
                try:
                    start_time = time.time()
                    
                    # Resolve any step dependencies in parameters
                    resolved_parameters = self._resolve_step_dependencies(
                        tool_call.parameters, 
                        step_outputs, 
                        execution_results
                    )
                    
                    logger.info(f"🔧 DEBUG: Resolved parameters for {tool_call.tool_id}: {resolved_parameters}")
                    
                    # Validate and enhance parameters
                    validated_parameters = self._validate_tool_parameters(
                        tool_call.tool_id, 
                        resolved_parameters
                    )
                    
                    logger.info(f"🔧 DEBUG: Validated parameters for {tool_call.tool_id}: {validated_parameters}")
                    
                    # Create updated tool call with validated parameters
                    updated_tool_call = ToolCall(
                        call_id=tool_call.call_id,
                        tool_id=tool_call.tool_id,
                        parameters=validated_parameters,
                        context=tool_call.context
                    )
                    
                    logger.info(f"🔧 DEBUG: About to execute tool {tool_call.tool_id} with final parameters: {validated_parameters}")
                    
                    # Execute the tool
                    result = await self.tool_registry.execute_tool(updated_tool_call)
                    
                    execution_time = time.time() - start_time
                    result.metadata["execution_time"] = execution_time
                    
                    logger.info(f"Tool {tool_call.tool_id} completed in {execution_time:.2f}s, success: {result.success}")
                    
                    if not result.success:
                        logger.error(f"Tool execution failed: {result.error}")
                        logger.info(f"🔧 DEBUG: Failed tool call details:")
                        logger.info(f"🔧 DEBUG: - Tool ID: {tool_call.tool_id}")
                        logger.info(f"🔧 DEBUG: - Parameters: {validated_parameters}")
                        logger.info(f"🔧 DEBUG: - Error: {result.error}")
                    
                    execution_results.append(result)
                    
                    # Store output for dependency resolution
                    if result.success and result.result:
                        step_outputs[f"step_{i+1}"] = result.result
                    
                except Exception as e:
                    logger.error(f"Tool execution exception for {tool_call.tool_id}: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                    # Create error result
                    error_result = ExecutionResult(
                        tool_id=tool_call.tool_id,
                        call_id=tool_call.call_id,
                        success=False,
                        error=str(e),
                        metadata={"execution_time": 0}
                    )
                    execution_results.append(error_result)
            
            # Update state with results
            state["execution_results"] = execution_results
            state["tool_calls"] = tool_calls
            
            # Calculate success metrics
            successful_count = sum(1 for result in execution_results if result.success)
            total_count = len(execution_results)
            
            logger.info(f"Tool execution completed: {successful_count}/{total_count} tools successful ({successful_count/total_count*100:.1f}%)")
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to execute tools: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            state["errors"].append(f"Tool execution failed: {str(e)}")
            return state
    
    async def synthesize_results(self, state: ToolExecutionState) -> ToolExecutionState:
        """
        Synthesize tool execution results into a coherent response.
        
        Args:
            state: Current execution state
            
        Returns:
            Updated state with synthesized results
        """
        logger.info("Synthesizing tool execution results")
        
        try:
            if not state["execution_results"]:
                logger.warning("No execution results to synthesize")
                state["metadata"]["final_response"] = "No tools were executed successfully."
                return state
            
            # Prepare results for synthesis
            results_summary = self._prepare_results_for_synthesis(state["execution_results"])
            
            # Create synthesis prompt
            synthesis_prompt = self._create_synthesis_prompt(
                state["user_query"],
                results_summary,
                state.get("execution_plan", {})
            )
            
            logger.debug("Generating response synthesis with Bedrock")
            synthesis_response = await self.llm_client.generate_completion(
                prompt=synthesis_prompt,
                max_tokens=2000,
                temperature=0.2
            )
            
            # Process and format final response
            final_response = self._format_final_response(
                synthesis_response, 
                state["execution_results"],
                state["metadata"]
            )
            
            # Update state
            state["metadata"]["final_response"] = final_response
            state["metadata"]["synthesis_response"] = synthesis_response
            
            logger.info("Result synthesis completed")
            return state
            
        except Exception as e:
            logger.error(f"Failed to synthesize results: {e}")
            logger.error(traceback.format_exc())
            state["errors"].append(f"Result synthesis failed: {str(e)}")
            return state
    
    def _format_tools_for_llm(self, tools: List[Dict[str, Any]]) -> str:
        """Format available tools for LLM understanding."""
        tools_text = "Available Tools:\n\n"
        
        for tool in tools:
            tools_text += f"Tool ID: {tool['tool_id']}\n"
            tools_text += f"Name: {tool['name']}\n"
            tools_text += f"Description: {tool['description']}\n"
            tools_text += f"Category: {tool['category']}\n"
            
            if tool.get('parameters'):
                tools_text += f"Parameters: {json.dumps(tool['parameters'], indent=2)}\n"
            
            tools_text += f"Performance Score: {tool.get('performance_metrics', {}).get('avg_score', 'N/A')}\n"
            tools_text += "\n---\n\n"
        
        return tools_text
    
    def _create_tool_selection_prompt(self, user_query: str, tools_description: str) -> str:
        """Create prompt for tool selection with database context awareness."""
        # Detect database context from query
        query_lower = user_query.lower()
        database_hints = ""
        
        if "shopify" in query_lower or "product" in query_lower or "inventory" in query_lower or "order" in query_lower:
            database_hints = "\n🛍️ SHOPIFY CONTEXT DETECTED: Prioritize shopify.* tools for e-commerce data analysis"
        elif "mongodb" in query_lower or "mongo" in query_lower or "collection" in query_lower:
            database_hints = "\n📊 MONGODB CONTEXT DETECTED: Prioritize mongo.* tools for document database operations"
        elif "postgresql" in query_lower or "postgres" in query_lower or "sql" in query_lower or "table" in query_lower:
            database_hints = "\n🐘 POSTGRESQL CONTEXT DETECTED: Prioritize postgres.* tools for relational database operations"
        elif "qdrant" in query_lower or "vector" in query_lower or "semantic" in query_lower:
            database_hints = "\n🔍 QDRANT CONTEXT DETECTED: Prioritize qdrant.* tools for vector search operations"
        elif "slack" in query_lower or "message" in query_lower or "channel" in query_lower:
            database_hints = "\n💬 SLACK CONTEXT DETECTED: Prioritize slack.* tools for workspace communication analysis"
        elif "ga4" in query_lower or "google analytics" in query_lower or "audience" in query_lower:
            database_hints = "\n📈 GA4 CONTEXT DETECTED: Prioritize ga4.* tools for web analytics"
        
        return f"""You are an expert tool selector for a data analysis system. Your task is to analyze the user's query and select the most appropriate tools to accomplish their request.

User Query: {user_query}{database_hints}

{tools_description}

CRITICAL TOOL SELECTION RULES:
1. **Database Context Priority**: If the query mentions specific platforms (Shopify, MongoDB, PostgreSQL, etc.), STRONGLY prioritize tools from that platform
2. **Domain-Specific Analysis**: For e-commerce queries, use Shopify tools; for document analysis, use MongoDB tools; for relational data, use PostgreSQL tools
3. **Tool Relevance**: Select tools that directly address the user's specific request (performance analysis, inventory optimization, etc.)
4. **Workflow Completeness**: Include supporting tools for data validation, export, or visualization if the query implies these needs

Instructions:
1. Analyze the user's query to identify the primary database/platform context
2. Select the most relevant tools that can help answer their query
3. Prioritize platform-specific tools when context is clear
4. Consider the tool categories and descriptions carefully
5. Select between 2-5 tools maximum - focus on what's necessary for a complete analysis

Response Format:
Provide your selection as a JSON object with this structure:
{{
    "analysis": "Brief analysis of the user's request and detected database context",
    "selected_tools": [
        {{
            "tool_id": "tool_identifier",
            "reason": "Why this tool is needed for the specific context"
        }}
    ],
    "execution_strategy": "Brief description of how these tools should work together"
}}

Focus on practical utility and database-appropriate tool selection."""
    
    def _create_execution_plan_prompt(self, user_query: str, tool_details: List[Dict]) -> str:
        """Create prompt for execution plan generation."""
        tools_info = ""
        for tool in tool_details:
            tools_info += f"Tool: {tool['tool_id']}\n"
            tools_info += f"Description: {tool['description']}\n"
            
            # Show expected parameter types and provide examples
            params = tool.get('parameters', {})
            if params:
                tools_info += f"Required Parameters:\n"
                for param_name, param_type in params.items():
                    if param_name == "query" and "postgres" in tool['tool_id']:
                        tools_info += f"  - {param_name} ({param_type}): SQL query string (e.g., 'SELECT * FROM table_name LIMIT 10')\n"
                    elif param_name == "query" and "mongo" in tool['tool_id']:
                        tools_info += f"  - {param_name} ({param_type}): MongoDB query object with 'collection' and 'pipeline' fields\n"
                    elif param_name == "nl_prompt":
                        tools_info += f"  - {param_name} ({param_type}): Natural language description of what you want to query\n"
                    elif param_name == "data":
                        tools_info += f"  - {param_name} ({param_type}): Data to process (use 'output_from_step_X' to reference previous step outputs)\n"
                    elif param_name == "filepath":
                        tools_info += f"  - {param_name} ({param_type}): File path for output (e.g., '/tmp/results.csv')\n"
                    else:
                        tools_info += f"  - {param_name} ({param_type}): Value for this parameter\n"
            else:
                tools_info += f"Parameters: None required\n"
            tools_info += "\n"
        
        return f"""You are creating an execution plan for data analysis tools. Your task is to define the specific steps and parameters for executing the selected tools.

User Query: {user_query}

Selected Tools:
{tools_info}

CRITICAL INSTRUCTIONS:
1. For each tool, provide ALL required parameters with ACTUAL VALUES, not placeholders
2. If a tool needs data from a previous step, use exactly this format: "output_from_step_X" where X is the step number
3. For SQL queries, write actual SQL statements based on the user query
4. For MongoDB queries, provide proper JSON objects with collection and pipeline fields
5. For file operations, use realistic file paths like "/tmp/analysis_results.csv"
6. NO PLACEHOLDERS - every parameter must have a concrete value

Examples of GOOD parameters:
- For postgres.execute_query: {{"query": "SELECT * FROM sample_orders WHERE status = 'active' LIMIT 10"}}
- For mongo.execute_query: {{"query": {{"collection": "sample_orders", "pipeline": [{{"$match": {{"status": "active"}}}}, {{"$limit": 10}}]}}}}
- For file export: {{"data": "output_from_step_1", "filepath": "/tmp/shopify_analysis.csv"}}

Response Format (JSON only):
{{
    "steps": [
        {{
            "step_number": 1,
            "tool_id": "tool_identifier",
            "parameters": {{"param_name": "actual_value_not_placeholder"}},
            "description": "What this step accomplishes",
            "depends_on": []
        }}
    ],
    "expected_outcome": "What the overall execution should achieve",
    "execution_notes": "Any special considerations"
}}"""
    
    def _create_synthesis_prompt(self, user_query: str, results_summary: str, execution_plan: Dict) -> str:
        """Create prompt for result synthesis."""
        return f"""You are synthesizing the results of multiple data analysis tools to provide a comprehensive answer to the user's query.

Original User Query: {user_query}

Tool Execution Results:
{results_summary}

Instructions:
1. Analyze all the tool results in context of the user's original query
2. Identify key insights and findings
3. Present the information in a clear, structured manner
4. Highlight any important patterns, anomalies, or recommendations
5. If there were any errors, acknowledge them but focus on successful results

Response Format:
Provide a comprehensive response that includes:
- Executive summary of findings
- Detailed analysis of results
- Key insights and recommendations
- Any limitations or caveats

Write in a professional but accessible tone, as if explaining to a business stakeholder."""
    
    def _parse_tool_selection(self, response: str, available_tools: List[Dict]) -> List[Dict]:
        """Parse LLM tool selection response with intelligent fallbacks."""
        try:
            logger.info(f"Raw LLM tool selection response: {response[:500]}...")
            
            # Try to extract JSON from response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "{" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                response = response[json_start:json_end]
            
            logger.info(f"Cleaned JSON for parsing: {response[:300]}...")
            selection_data = json.loads(response)
            logger.info(f"Parsed selection data: {selection_data}")
            
            selected_tools = []
            
            # Extract selected tool IDs
            for tool_selection in selection_data.get("selected_tools", []):
                tool_id = tool_selection.get("tool_id")
                logger.info(f"Processing tool selection: {tool_id}")
                
                # Find tool in available tools
                for tool in available_tools:
                    if tool["tool_id"] == tool_id:
                        selected_tools.append(tool)
                        logger.info(f"Found and selected tool: {tool_id}")
                        break
                else:
                    logger.warning(f"Tool {tool_id} not found in available tools")
            
            logger.info(f"Final selected tools: {[t['tool_id'] for t in selected_tools]}")
            return selected_tools
            
        except Exception as e:
            logger.error(f"Failed to parse tool selection: {e}")
            logger.error(f"Raw response that failed: {response[:200]}...")
            # Intelligent fallback when LLM is not functional
            fallback_tools = self._intelligent_tool_fallback(available_tools)
            logger.info(f"Using fallback tools: {[t['tool_id'] for t in fallback_tools]}")
            return fallback_tools
    
    def _intelligent_tool_fallback(self, available_tools: List[Dict]) -> List[Dict]:
        """Intelligent tool selection fallback when LLM is not functional."""
        if not hasattr(self, '_current_query'):
            # If no query context, return first available tool
            return available_tools[:1] if available_tools else []
        
        query = self._current_query.lower()
        selected_tools = []
        
        # Context-aware tool selection based on keywords
        if "shopify" in query or "product" in query or "inventory" in query or "order" in query:
            logger.info("Fallback: Detected Shopify context, selecting Shopify tools")
            shopify_tools = [tool for tool in available_tools if "shopify" in tool["tool_id"]]
            selected_tools.extend(shopify_tools[:3])  # Select up to 3 Shopify tools
            
        elif "mongodb" in query or "mongo" in query or "collection" in query:
            logger.info("Fallback: Detected MongoDB context, selecting MongoDB tools")
            mongo_tools = [tool for tool in available_tools if "mongo" in tool["tool_id"]]
            selected_tools.extend(mongo_tools[:3])
            
        elif "postgresql" in query or "postgres" in query or "sql" in query or "table" in query:
            logger.info("Fallback: Detected PostgreSQL context, selecting PostgreSQL tools")
            postgres_tools = [tool for tool in available_tools if "postgres" in tool["tool_id"]]
            selected_tools.extend(postgres_tools[:3])
            
        elif "qdrant" in query or "vector" in query or "semantic" in query:
            logger.info("Fallback: Detected Qdrant context, selecting Qdrant tools")
            qdrant_tools = [tool for tool in available_tools if "qdrant" in tool["tool_id"]]
            selected_tools.extend(qdrant_tools[:3])
            
        elif "slack" in query or "message" in query or "channel" in query:
            logger.info("Fallback: Detected Slack context, selecting Slack tools")
            slack_tools = [tool for tool in available_tools if "slack" in tool["tool_id"]]
            selected_tools.extend(slack_tools[:3])
            
        elif "ga4" in query or "google analytics" in query or "audience" in query:
            logger.info("Fallback: Detected GA4 context, selecting GA4 tools")
            ga4_tools = [tool for tool in available_tools if "ga4" in tool["tool_id"]]
            selected_tools.extend(ga4_tools[:3])
        
        # For general data analysis queries (like "count of available data")
        elif any(keyword in query for keyword in ["count", "data", "available", "analyze", "show", "statistics"]):
            logger.info("Fallback: Detected general data analysis query, selecting diverse database tools")
            # Select one tool from each major database type for comprehensive analysis
            postgres_tools = [tool for tool in available_tools if "postgres" in tool["tool_id"] and "execute_query" in tool["tool_id"]]
            mongo_tools = [tool for tool in available_tools if "mongo" in tool["tool_id"] and "execute_query" in tool["tool_id"]]
            shopify_tools = [tool for tool in available_tools if "shopify" in tool["tool_id"] and "execute_query" in tool["tool_id"]]
            
            if postgres_tools:
                selected_tools.extend(postgres_tools[:1])
            if mongo_tools:
                selected_tools.extend(mongo_tools[:1])
            if shopify_tools:
                selected_tools.extend(shopify_tools[:1])
        
        # If no specific context detected or no relevant tools found, add some general tools
        if not selected_tools:
            logger.info("Fallback: No specific context detected, selecting general analysis tools")
            # Look for general analysis tools
            analysis_tools = [tool for tool in available_tools if any(keyword in tool["tool_id"] 
                             for keyword in ["analyze", "performance", "statistics", "introspect", "execute_query"])]
            selected_tools.extend(analysis_tools[:3])
        
        # Always add data validation and export tools for completeness
        support_tools = [tool for tool in available_tools if any(keyword in tool["tool_id"]
                        for keyword in ["data_validation", "export", "csv"])]
        selected_tools.extend(support_tools[:1])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tools = []
        for tool in selected_tools:
            if tool["tool_id"] not in seen:
                seen.add(tool["tool_id"])
                unique_tools.append(tool)
        
        # Ensure we have at least one tool
        if not unique_tools and available_tools:
            unique_tools = available_tools[:1]
        
        logger.info(f"Fallback tool selection: {[tool['tool_id'] for tool in unique_tools]}")
        return unique_tools

    def _parse_execution_plan(self, response: str, tool_details: List[Dict]) -> Dict[str, Any]:
        """Parse LLM execution plan response with robust JSON handling."""
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "{" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                response = response[json_start:json_end]
            
            # Clean up common JSON issues
            response = response.replace('\n', ' ')  # Remove newlines
            response = response.replace('\t', ' ')  # Remove tabs
            response = response.replace('\\', '')   # Remove escape characters that cause issues
            
            # Try parsing with json.loads
            execution_plan = json.loads(response)
            
            # Validate and enhance the execution plan
            execution_plan = self._validate_and_enhance_execution_plan(execution_plan, tool_details)
            
            return execution_plan
            
        except Exception as e:
            logger.error(f"Failed to parse execution plan: {e}")
            logger.debug(f"Raw response that failed to parse: {response[:500]}...")
            
            # Fallback: create intelligent plan with proper parameters
            return self._create_intelligent_fallback_plan(tool_details)
    
    def _validate_and_enhance_execution_plan(self, plan: Dict[str, Any], tool_details: List[Dict]) -> Dict[str, Any]:
        """Validate and enhance execution plan with missing parameters."""
        if "steps" not in plan:
            return self._create_intelligent_fallback_plan(tool_details)
        
        # Enhance each step with missing parameters
        for step in plan["steps"]:
            tool_id = step.get("tool_id")
            tool_info = next((tool for tool in tool_details if tool["tool_id"] == tool_id), None)
            
            if tool_info:
                # Add missing required parameters with intelligent defaults
                step["parameters"] = self._add_missing_parameters(
                    step.get("parameters", {}), 
                    tool_info, 
                    step.get("step_number", 1)
                )
        
        return plan
    
    def _add_missing_parameters(self, params: Dict[str, Any], tool_info: Dict[str, Any], step_number: int) -> Dict[str, Any]:
        """Add missing required parameters with intelligent defaults."""
        tool_id = tool_info["tool_id"]
        required_params = tool_info.get("parameters", {})
        
        logger.info(f"🔧 DEBUG: _add_missing_parameters called for {tool_id}")
        logger.info(f"🔧 DEBUG: - Input params: {params}")
        logger.info(f"🔧 DEBUG: - Required params: {required_params}")
        logger.info(f"🔧 DEBUG: - Step number: {step_number}")
        
        enhanced_params = params.copy()
        
        for param_name, param_type in required_params.items():
            if param_name not in enhanced_params:
                logger.info(f"🔧 DEBUG: Missing parameter '{param_name}' for {tool_id}, generating default")
                
                # Generate intelligent default based on tool and parameter
                if param_name == "query":
                    if "shopify" in tool_id:
                        default_query = "SELECT COUNT(*) FROM products"
                        logger.info(f"🔧 DEBUG: Generated Shopify query: {default_query}")
                        enhanced_params[param_name] = default_query
                    elif "postgres" in tool_id:
                        # Try to get actual table names from schema
                        try:
                            # Get schema information from the current state or metadata
                            if hasattr(self, '_current_schema_metadata'):
                                postgres_schema = self._current_schema_metadata.get('postgres', {})
                                tables = postgres_schema.get('tables', [])
                                if tables:
                                    # Use the first available table
                                    table_name = tables[0]
                                    default_query = f"SELECT COUNT(*) FROM {table_name}"
                                    logger.info(f"🔧 DEBUG: Generated PostgreSQL query with real table: {default_query}")
                                else:
                                    default_query = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                                    logger.info(f"🔧 DEBUG: Generated PostgreSQL schema query: {default_query}")
                            else:
                                default_query = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                                logger.info(f"🔧 DEBUG: Generated PostgreSQL fallback query: {default_query}")
                        except Exception as e:
                            logger.warning(f"🔧 DEBUG: Failed to get schema info for PostgreSQL: {e}")
                            default_query = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                            logger.info(f"🔧 DEBUG: Generated PostgreSQL error fallback query: {default_query}")
                        
                        enhanced_params[param_name] = default_query
                    elif "mongo" in tool_id:
                        default_query = "db.collection.countDocuments({})"
                        logger.info(f"🔧 DEBUG: Generated MongoDB query: {default_query}")
                        enhanced_params[param_name] = default_query
                    else:
                        default_query = f"SELECT COUNT(*) FROM data_table"
                        logger.info(f"🔧 DEBUG: Generated generic fallback query (THIS IS THE PROBLEM): {default_query}")
                        enhanced_params[param_name] = default_query
                elif param_name == "collection_name" and "mongo" in tool_id:
                    default_collection = "products"
                    logger.info(f"🔧 DEBUG: Generated MongoDB collection: {default_collection}")
                    enhanced_params[param_name] = default_collection
                elif param_name == "database_name":
                    default_db = "ceneca_db"
                    logger.info(f"🔧 DEBUG: Generated database name: {default_db}")
                    enhanced_params[param_name] = default_db
                elif param_name == "limit":
                    default_limit = 100
                    logger.info(f"🔧 DEBUG: Generated limit: {default_limit}")
                    enhanced_params[param_name] = default_limit
                else:
                    logger.warning(f"🔧 DEBUG: No default generator for parameter '{param_name}' in {tool_id}")
        
        logger.info(f"🔧 DEBUG: Enhanced params for {tool_id}: {enhanced_params}")
        return enhanced_params
    
    def _create_intelligent_fallback_plan(self, tool_details: List[Dict]) -> Dict[str, Any]:
        """Create an intelligent fallback execution plan."""
        steps = []
        
        for i, tool in enumerate(tool_details):
            step_number = i + 1
            tool_id = tool["tool_id"]
            
            # Create intelligent parameters based on tool type
            parameters = self._add_missing_parameters({}, tool, step_number)
            
            step = {
                "step_number": step_number,
                "tool_id": tool_id,
                "parameters": parameters,
                "description": f"Execute {tool.get('name', tool_id)}",
                "depends_on": [step_number - 1] if step_number > 1 else []
            }
            steps.append(step)
        
        return {
            "steps": steps,
            "expected_outcome": "Execute selected tools with intelligent parameter defaults",
            "execution_notes": "Intelligent fallback execution plan with proper parameters"
        }
    
    def _create_tool_calls_from_plan(self, execution_plan: Dict, user_query: str) -> List[ToolCall]:
        """Create tool calls from execution plan."""
        tool_calls = []
        
        logger.info(f"🔧 DEBUG: Creating tool calls from execution plan with {len(execution_plan.get('steps', []))} steps")
        
        for step in execution_plan.get("steps", []):
            logger.info(f"🔧 DEBUG: Processing step: {step}")
            
            tool_call = ToolCall(
                call_id=f"call_{int(time.time())}_{step['step_number']}",
                tool_id=step["tool_id"],
                parameters=step.get("parameters", {}),
                context={
                    "user_query": user_query,
                    "step_description": step.get("description", ""),
                    "step_number": step["step_number"],
                    "depends_on": step.get("depends_on", [])
                }
            )
            
            logger.info(f"🔧 DEBUG: Created tool call for {step['tool_id']}:")
            logger.info(f"🔧 DEBUG: - Call ID: {tool_call.call_id}")
            logger.info(f"🔧 DEBUG: - Parameters: {tool_call.parameters}")
            logger.info(f"🔧 DEBUG: - Context: {tool_call.context}")
            
            tool_calls.append(tool_call)
        
        logger.info(f"🔧 DEBUG: Created {len(tool_calls)} tool calls total")
        return tool_calls
    
    def _prepare_results_for_synthesis(self, execution_results: List[ExecutionResult]) -> str:
        """Prepare execution results for synthesis prompt."""
        results_text = ""
        
        for i, result in enumerate(execution_results):
            results_text += f"Result {i+1} - Tool: {result.tool_id}\n"
            results_text += f"Success: {result.success}\n"
            
            if result.success and result.result:
                if isinstance(result.result, dict):
                    results_text += f"Output: {json.dumps(result.result, indent=2, default=str)}\n"
                else:
                    results_text += f"Output: {str(result.result)}\n"
            
            if result.error:
                results_text += f"Error: {result.error}\n"
            
            if result.metadata:
                execution_time = result.metadata.get("execution_time", "N/A")
                results_text += f"Execution Time: {execution_time}s\n"
            
            results_text += "\n---\n\n"
        
        return results_text
    
    def _format_final_response(self, synthesis_response: str, execution_results: List[ExecutionResult], metadata: Dict) -> str:
        """Format the final response with additional metadata."""
        # Extract clean response from synthesis
        final_response = synthesis_response.strip()
        
        # Add execution metadata
        successful_tools = sum(1 for r in execution_results if r.success)
        total_time = metadata.get("total_execution_time", 0)
        
        response_footer = f"\n\n---\nExecution Summary: {successful_tools}/{len(execution_results)} tools executed successfully in {total_time:.2f}s"
        
        return final_response + response_footer

    def set_schema_metadata(self, schema_metadata: Dict[str, Any]):
        """Store schema metadata for use in parameter generation."""
        self._current_schema_metadata = schema_metadata
        logger.info(f"🔧 DEBUG: Stored schema metadata: {schema_metadata}")
    
    async def _capture_tool_execution_outputs(self, session_id: str, state: ToolExecutionState):
        """
        Capture all tool execution outputs for the output aggregator.
        
        Args:
            session_id: Session ID for output aggregation
            state: Current execution state containing results
        """
        try:
            aggregator = self.output_integrator.get_aggregator(session_id)
            
            # Capture execution plan with actual operations
            if state.get("execution_plan"):
                plan = state["execution_plan"]
                
                # Enhance the plan with actual operations from steps
                operations = []
                for step in plan.get("steps", []):
                    operations.append({
                        "operation_id": step.get("step_number", 0),
                        "tool_id": step.get("tool_id", "unknown"),
                        "parameters": step.get("parameters", {}),
                        "description": step.get("description", ""),
                        "depends_on": step.get("depends_on", [])
                    })
                
                enhanced_plan = {
                    **plan,
                    "operations": operations,
                    "strategy": plan.get("strategy", "llm_generated"),
                    "success_rate": state["metadata"].get("success_rate", 0)
                }
                
                aggregator.capture_execution_plan(
                    plan=enhanced_plan,
                    node_id="tool_execution_node",
                    plan_source="llm_generated"
                )
                logger.debug(f"🔄 [OUTPUT_AGGREGATOR] Captured execution plan with {len(operations)} operations")
            
            # Create a mapping of tool call IDs to parameters
            tool_call_params = {}
            for tool_call in state.get("tool_calls", []):
                tool_call_params[tool_call.call_id] = {
                    "tool_id": tool_call.tool_id,
                    "parameters": tool_call.parameters,
                    "context": tool_call.context
                }
            
            # Capture individual tool executions with proper parameter mapping
            for result in state.get("execution_results", []):
                # Get tool execution details
                tool_id = result.tool_id if hasattr(result, 'tool_id') else "unknown"
                call_id = result.call_id if hasattr(result, 'call_id') else f"call_{tool_id}_{int(time.time())}"
                
                # Get parameters from the original tool call
                parameters = {}
                if call_id in tool_call_params:
                    parameters = tool_call_params[call_id]["parameters"]
                
                # Extract raw data if available
                raw_data = []
                if result.success and result.result:
                    if isinstance(result.result, list):
                        raw_data = result.result
                    elif isinstance(result.result, dict):
                        raw_data = [result.result] 
                
                # Capture tool execution
                aggregator.capture_tool_execution(
                    tool_id=tool_id,
                    call_id=call_id,
                    parameters=parameters,
                    result=result.result,
                    success=result.success,
                    execution_time_ms=result.metadata.get("execution_time", 0) * 1000 if result.metadata else 0,
                    error_message=result.error if hasattr(result, 'error') else None,
                    node_id="tool_execution_node"
                )
                
                # Capture raw data if available
                if raw_data:
                    # Determine source based on tool_id
                    source = "unknown"
                    if "mongo" in tool_id.lower():
                        source = "mongodb"
                    elif "postgres" in tool_id.lower():
                        source = "postgresql"
                    elif "shopify" in tool_id.lower():
                        source = "shopify"
                    elif "ga4" in tool_id.lower():
                        source = "ga4"
                    elif "qdrant" in tool_id.lower():
                        source = "qdrant"
                    elif "slack" in tool_id.lower():
                        source = "slack"
                    
                    aggregator.capture_raw_data(
                        source=source,
                        rows=raw_data,
                        query=parameters.get("query"),
                        node_id="tool_execution_node",
                        tool_id=tool_id
                    )
                    logger.debug(f"🔄 [OUTPUT_AGGREGATOR] Captured raw data from {source}: {len(raw_data)} rows")
                
                logger.debug(f"🔄 [OUTPUT_AGGREGATOR] Captured tool execution: {tool_id}, success={result.success}")
            
            # Capture final synthesis
            synthesis_response = state["metadata"].get("synthesis_response")
            if synthesis_response:
                aggregator.capture_final_synthesis(
                    response_text=synthesis_response,
                    sources_used=state.get("selected_tools", []),
                    node_id="tool_execution_node",
                    synthesis_method="llm_based"
                )
                logger.debug(f"🔄 [OUTPUT_AGGREGATOR] Captured final synthesis")
            
            # Capture performance metrics
            metrics = {
                "total_duration_ms": state["metadata"].get("total_execution_time", 0) * 1000,
                "operations_executed": len(state.get("execution_results", [])),
                "operations_successful": sum(1 for r in state.get("execution_results", []) if r.success),
                "tool_success_rate": state["metadata"].get("success_rate", 0)
            }
            
            aggregator.capture_performance_metrics(
                metrics=metrics,
                node_id="tool_execution_node"
            )
            logger.debug(f"🔄 [OUTPUT_AGGREGATOR] Captured performance metrics")
            
        except Exception as e:
            logger.error(f"🔄 [OUTPUT_AGGREGATOR] Failed to capture tool execution outputs: {e}")
            import traceback
            logger.error(traceback.format_exc()) 