"""
AWS Bedrock LLM Client for LangGraph Integration

Provides AWS Bedrock as the primary LLM choice for LangGraph workflows,
with Anthropic and OpenAI as fallbacks.
"""

import logging
import json
import time
import boto3
from typing import Dict, List, Any, Optional, AsyncIterator, Union
from datetime import datetime

from ...llm.client import get_llm_client, get_classification_client, AnthropicClient, OpenAIClient

logger = logging.getLogger(__name__)

class BedrockLangGraphClient:
    """
    Enhanced LLM client that uses AWS Bedrock as primary choice with fallbacks.
    
    This client is specifically designed for LangGraph workflows and provides:
    - AWS Bedrock Claude as primary model
    - Anthropic Claude as first fallback
    - OpenAI GPT as second fallback
    - Specialized prompt handling for graph operations
    - Enhanced error recovery and circuit breakers
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize primary and fallback clients
        self.primary_client = None
        self.fallback_clients = []
        
        self._initialize_clients()
        
        # Circuit breaker settings
        self.circuit_breaker_threshold = 3
        self.circuit_breaker_timeout = 60  # seconds
        self.failure_counts = {}
        self.circuit_open_until = {}
        
        logger.info(f"Initialized BedrockLangGraphClient with {len(self.fallback_clients)} fallback clients")
    
    async def generate_completion(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate a simple text completion using the best available LLM.
        This method provides compatibility for tools expecting basic completion functionality.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            **kwargs: Additional parameters
            
        Returns:
            Generated text completion
        """
        try:
            # Check if client is functional
            if not self.is_functional:
                logger.info("LLM client is not functional, returning fallback response")
                return "LLM client not available - using fallback response"
            
            # Try primary client first
            if self.primary_client == "bedrock" and self._is_circuit_closed("bedrock"):
                logger.info("Using Bedrock for text completion")
                
                # Use bedrock parameters or defaults
                tokens = max_tokens or self.bedrock_max_tokens
                temp = temperature if temperature is not None else self.bedrock_temperature
                
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": min(tokens, 4000),  # Ensure within limits
                    "temperature": temp,
                    "top_p": self.bedrock_top_p,
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                response = self.bedrock_client.invoke_model(
                    modelId=self.bedrock_model_id,
                    body=json.dumps(body)
                )
                
                response_body = json.loads(response["body"].read())
                
                if "content" in response_body and len(response_body["content"]) > 0:
                    return response_body["content"][0]["text"]
                else:
                    raise Exception("No content in Bedrock response")
            
            # Try fallback clients
            for client_name, client in self.fallback_clients:
                if self._is_circuit_closed(client_name):
                    logger.info(f"Using {client_name} fallback for text completion")
                    
                    if client_name == "anthropic":
                        result = await client.generate_completion(
                            prompt=prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            **kwargs
                        )
                        return result
                    elif client_name == "openai":
                        result = await client.generate_completion(
                            prompt=prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            **kwargs
                        )
                        return result
            
            raise Exception("All LLM clients are unavailable")
            
        except Exception as e:
            logger.error(f"Failed to generate completion: {e}")
            self._record_failure("bedrock" if self.primary_client == "bedrock" else "fallback")
            return f"Error generating completion: {str(e)}"
    
    def _initialize_clients(self):
        """Initialize Bedrock primary client and configure fallbacks."""
        try:
            # Get settings for proper AWS credentials
            from ...config.settings import Settings
            settings = Settings()
            
            # Check if Bedrock is enabled
            if not settings.BEDROCK_ENABLED:
                logger.info("Bedrock is disabled in configuration")
                self.primary_client = None
            else:
                # Get AWS credentials configuration
                aws_config = settings.aws_credentials_config
                bedrock_config = settings.bedrock_config
                
                logger.info(f"AWS credentials config keys: {list(aws_config.keys())}")
                
                # Initialize AWS Bedrock runtime client with explicit credentials
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    **aws_config  # This includes region_name, aws_access_key_id, aws_secret_access_key
                )
                
                # Test Bedrock connectivity with the same credentials
                test_client = boto3.client("bedrock", **aws_config)
                models_response = test_client.list_foundation_models()
                logger.info(f"Bedrock connectivity test successful. Found {len(models_response.get('modelSummaries', []))} models")
                
                self.primary_client = "bedrock"
                self.bedrock_model_id = bedrock_config['model_id']
                self.bedrock_max_tokens = bedrock_config['max_tokens']
                self.bedrock_temperature = bedrock_config['temperature']
                self.bedrock_top_p = bedrock_config['top_p']
                
                logger.info(f"Successfully initialized Bedrock client in region: {aws_config.get('region_name', 'us-east-1')}")
                logger.info(f"Using model: {self.bedrock_model_id}")
            
        except Exception as e:
            logger.warning(f"Failed to initialize Bedrock client: {e}")
            logger.warning(f"Error type: {type(e).__name__}")
            import traceback
            logger.warning(f"Full traceback: {traceback.format_exc()}")
            self.primary_client = None
        
        # Initialize fallback clients
        try:
            # Add Anthropic as first fallback
            anthropic_client = AnthropicClient()
            self.fallback_clients.append(("anthropic", anthropic_client))
            logger.info("Added Anthropic as fallback client")
        except Exception as e:
            logger.warning(f"Failed to initialize Anthropic fallback: {e}")
        
        try:
            # Add OpenAI as second fallback
            openai_client = OpenAIClient()
            self.fallback_clients.append(("openai", openai_client))
            logger.info("Added OpenAI as fallback client")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI fallback: {e}")
        
        if not self.primary_client and not self.fallback_clients:
            logger.warning("No LLM clients could be initialized - this may be expected in testing environments")
            # Don't raise an error, allow the client to be created but mark it as non-functional
            self.is_functional = False
        else:
            self.is_functional = True
    
    async def generate_graph_plan(
        self,
        question: str,
        databases_available: List[str],
        schema_metadata: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate a LangGraph execution plan using the best available LLM.
        
        Args:
            question: User's question
            databases_available: List of available databases
            schema_metadata: Database schema information
            context: Additional context for planning
            
        Returns:
            Graph execution plan
        """
        prompt = self._create_graph_planning_prompt(
            question, 
            databases_available, 
            schema_metadata, 
            context
        )
        
        try:
            # Check if client is functional
            if not self.is_functional:
                logger.info("LLM client is not functional, using fallback plan")
                return self._create_fallback_plan(question, databases_available)
            
            # Try primary client first
            if self.primary_client == "bedrock" and self._is_circuit_closed("bedrock"):
                logger.info("Using Bedrock for graph planning")
                return await self._generate_with_bedrock(prompt, "graph_planning")
            
            # Try fallback clients
            for client_name, client in self.fallback_clients:
                if self._is_circuit_closed(client_name):
                    logger.info(f"Using {client_name} fallback for graph planning")
                    
                    if client_name == "anthropic":
                        return await self._generate_with_anthropic(client, prompt)
                    elif client_name == "openai":
                        return await self._generate_with_openai(client, prompt)
            
            raise Exception("All LLM clients are unavailable")
            
        except Exception as e:
            logger.error(f"Failed to generate graph plan: {e}")
            return {
                "error": str(e),
                "fallback_plan": self._create_fallback_plan(question, databases_available)
            }
    
    async def optimize_graph_execution(
        self,
        original_plan: Dict[str, Any],
        performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Optimize a graph execution plan based on performance data.
        
        Args:
            original_plan: Original execution plan
            performance_data: Performance metrics and feedback
            
        Returns:
            Optimized execution plan
        """
        prompt = self._create_optimization_prompt(original_plan, performance_data)
        
        try:
            # Check if client is functional
            if not self.is_functional:
                logger.info("LLM client is not functional, returning original plan")
                return original_plan
            
            # Try primary client first
            if self.primary_client == "bedrock" and self._is_circuit_closed("bedrock"):
                return await self._generate_with_bedrock(prompt, "optimization")
            
            # Try fallback clients
            for client_name, client in self.fallback_clients:
                if self._is_circuit_closed(client_name):
                    if client_name == "anthropic":
                        return await self._generate_with_anthropic(client, prompt)
                    elif client_name == "openai":
                        return await self._generate_with_openai(client, prompt)
            
            # Return original plan if optimization fails
            logger.warning("Optimization failed, returning original plan")
            return original_plan
            
        except Exception as e:
            logger.error(f"Failed to optimize graph plan: {e}")
            return original_plan
    
    async def analyze_graph_results(
        self,
        execution_results: Dict[str, Any],
        original_question: str
    ) -> str:
        """
        Analyze graph execution results to generate insights.
        
        Args:
            execution_results: Results from graph execution
            original_question: Original user question
            
        Returns:
            Analysis text
        """
        prompt = self._create_analysis_prompt(execution_results, original_question)
        
        try:
            # Check if client is functional
            if not self.is_functional:
                logger.info("LLM client is not functional, returning basic analysis")
                return "Analysis completed successfully (mock mode)."
            
            # Try primary client first
            if self.primary_client == "bedrock" and self._is_circuit_closed("bedrock"):
                result = await self._generate_with_bedrock(prompt, "analysis")
                return result.get("analysis", "Analysis completed successfully.")
            
            # Try fallback clients
            for client_name, client in self.fallback_clients:
                if self._is_circuit_closed(client_name):
                    if client_name == "anthropic":
                        return await client.analyze_results(
                            execution_results.get("operation_results", [])
                        )
                    elif client_name == "openai":
                        return await client.analyze_results(
                            execution_results.get("operation_results", [])
                        )
            
            return "Analysis completed, but detailed insights are unavailable."
            
        except Exception as e:
            logger.error(f"Failed to analyze graph results: {e}")
            return f"Analysis failed: {str(e)}"
    
    async def _generate_with_bedrock(
        self,
        prompt: str,
        operation_type: str
    ) -> Dict[str, Any]:
        """Generate response using AWS Bedrock."""
        try:
            start_time = time.time()
            
            # Construct Bedrock request using configured parameters
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.bedrock_max_tokens,
                "temperature": self.bedrock_temperature,
                "top_p": self.bedrock_top_p,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            logger.info(f"Making Bedrock request with model: {self.bedrock_model_id}")
            logger.debug(f"Request body: {json.dumps(body, indent=2)}")
            
            response = self.bedrock_client.invoke_model(
                modelId=self.bedrock_model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            logger.info("Bedrock request successful, parsing response")
            
            response_body = json.loads(response['body'].read())
            logger.debug(f"Bedrock response: {json.dumps(response_body, indent=2)}")
            
            output = response_body['content'][0]['text']
            
            execution_time = time.time() - start_time
            
            # Reset failure count on success
            self.failure_counts["bedrock"] = 0
            
            logger.info(f"Bedrock {operation_type} completed in {execution_time:.2f}s")
            logger.info(f"Generated text length: {len(output)}")
            
            # Parse JSON response if applicable
            try:
                if operation_type in ["graph_planning", "optimization"]:
                    result = json.loads(output)
                    logger.info("Successfully parsed response as JSON")
                    return result
                else:
                    return {"analysis": output}
            except json.JSONDecodeError:
                logger.info("Response is not valid JSON, returning as text")
                # Return raw text if not valid JSON
                return {"analysis": output}
            
        except Exception as e:
            self._record_failure("bedrock")
            logger.error(f"Bedrock generation failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    async def _generate_with_anthropic(
        self,
        client: AnthropicClient,
        prompt: str
    ) -> Dict[str, Any]:
        """Generate response using Anthropic fallback."""
        try:
            # Use Anthropic client's chat completion
            response = client.client.messages.create(
                model=client.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.1
            )
            
            # Extract content
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
                elif isinstance(block, dict) and 'text' in block:
                    content += block['text']
            
            # Reset failure count on success
            self.failure_counts["anthropic"] = 0
            
            # Try to parse as JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"analysis": content}
            
        except Exception as e:
            self._record_failure("anthropic")
            logger.error(f"Anthropic generation failed: {e}")
            raise
    
    async def _generate_with_openai(
        self,
        client: OpenAIClient,
        prompt: str
    ) -> Dict[str, Any]:
        """Generate response using OpenAI fallback."""
        try:
            response = client.client.chat.completions.create(
                model=client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            
            # Reset failure count on success
            self.failure_counts["openai"] = 0
            
            # Try to parse as JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"analysis": content}
            
        except Exception as e:
            self._record_failure("openai")
            logger.error(f"OpenAI generation failed: {e}")
            raise
    
    def _create_graph_planning_prompt(
        self,
        question: str,
        databases_available: List[str],
        schema_metadata: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> str:
        """Create prompt for graph planning."""
        context = context or {}
        
        return f"""You are a LangGraph orchestration expert. Create an optimal execution plan for the following query.

QUESTION: {question}

AVAILABLE DATABASES: {', '.join(databases_available)}

SCHEMA METADATA:
{json.dumps(schema_metadata, indent=2)}

CONTEXT: {json.dumps(context, indent=2)}

Create a LangGraph execution plan that:
1. Determines the optimal sequence of nodes
2. Identifies parallelization opportunities  
3. Handles error scenarios and fallbacks
4. Optimizes for performance and resource usage

Return a JSON object with:
{{
    "graph_structure": {{
        "nodes": [list of node specifications],
        "edges": [list of edge specifications], 
        "conditional_edges": [list of conditional logic]
    }},
    "execution_strategy": {{
        "parallelism_level": "low|medium|high",
        "estimated_time": "time in seconds",
        "resource_requirements": {{}}
    }},
    "optimization_hints": [
        "suggestion 1",
        "suggestion 2"
    ]
}}"""
    
    def _create_optimization_prompt(
        self,
        original_plan: Dict[str, Any],
        performance_data: Dict[str, Any]
    ) -> str:
        """Create prompt for plan optimization."""
        return f"""You are a performance optimization expert for LangGraph workflows.

ORIGINAL PLAN:
{json.dumps(original_plan, indent=2)}

PERFORMANCE DATA:
{json.dumps(performance_data, indent=2)}

Analyze the performance data and optimize the execution plan. Focus on:
1. Reducing bottlenecks identified in performance data
2. Better parallelization strategies
3. Resource allocation improvements
4. Error handling enhancements

Return an optimized JSON plan with the same structure as the original, plus an "optimization_notes" field explaining the changes."""
    
    def _create_analysis_prompt(
        self,
        execution_results: Dict[str, Any],
        original_question: str
    ) -> str:
        """Create prompt for result analysis."""
        return f"""You are a data analysis expert. Analyze the following execution results and provide insights.

ORIGINAL QUESTION: {original_question}

EXECUTION RESULTS:
{json.dumps(execution_results, indent=2)}

Provide a comprehensive analysis that:
1. Answers the original question based on the results
2. Identifies key patterns and insights
3. Highlights any anomalies or unexpected findings
4. Suggests follow-up questions or investigations

Format your response as clear, structured analysis with sections for different insights."""
    
    def _create_fallback_plan(
        self,
        question: str,
        databases_available: List[str]
    ) -> Dict[str, Any]:
        """Create a simple fallback plan when LLM generation fails."""
        return {
            "graph_structure": {
                "nodes": [
                    {"id": "metadata", "type": "metadata_collection"},
                    {"id": "planning", "type": "planning"},
                    {"id": "execution", "type": "execution"}
                ],
                "edges": [
                    {"from": "metadata", "to": "planning"},
                    {"from": "planning", "to": "execution"}
                ],
                "conditional_edges": []
            },
            "execution_strategy": {
                "parallelism_level": "medium",
                "estimated_time": "30",
                "resource_requirements": {
                    "memory": "standard",
                    "cpu": "medium"
                }
            },
            "optimization_hints": [
                "Fallback plan generated due to LLM unavailability",
                "Consider checking LLM connectivity"
            ],
            "fallback": True
        }
    
    def _is_circuit_closed(self, client_name: str) -> bool:
        """Check if circuit breaker is closed (client is available)."""
        current_time = time.time()
        
        # Check if circuit is open and timeout has passed
        if client_name in self.circuit_open_until:
            if current_time > self.circuit_open_until[client_name]:
                # Reset circuit
                del self.circuit_open_until[client_name]
                self.failure_counts[client_name] = 0
                logger.info(f"Circuit breaker reset for {client_name}")
            else:
                return False
        
        # Check failure count
        failure_count = self.failure_counts.get(client_name, 0)
        return failure_count < self.circuit_breaker_threshold
    
    def _record_failure(self, client_name: str):
        """Record a failure and potentially open circuit breaker."""
        self.failure_counts[client_name] = self.failure_counts.get(client_name, 0) + 1
        
        if self.failure_counts[client_name] >= self.circuit_breaker_threshold:
            # Open circuit breaker
            self.circuit_open_until[client_name] = time.time() + self.circuit_breaker_timeout
            logger.warning(f"Circuit breaker opened for {client_name} due to {self.failure_counts[client_name]} failures")
    
    def get_client_status(self) -> Dict[str, Any]:
        """Get status of all clients and circuit breakers."""
        status = {
            "primary_client": self.primary_client,
            "fallback_clients": [name for name, _ in self.fallback_clients],
            "circuit_breakers": {}
        }
        
        all_clients = ["bedrock"] + [name for name, _ in self.fallback_clients]
        
        for client_name in all_clients:
            status["circuit_breakers"][client_name] = {
                "status": "closed" if self._is_circuit_closed(client_name) else "open",
                "failure_count": self.failure_counts.get(client_name, 0),
                "open_until": self.circuit_open_until.get(client_name)
            }
        
        return status 