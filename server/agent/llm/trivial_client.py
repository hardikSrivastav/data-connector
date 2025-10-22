"""
Trivial LLM Client for fast text editing operations.

This client is optimized for speed and cost-efficiency using lightweight models
like Grok for simple text editing tasks (grammar fixes, tone adjustments, etc.).
Completely separate from the heavyweight LLM system.
"""

import json
import asyncio
from typing import Dict, Any, Optional, AsyncIterator, List
from functools import lru_cache
import hashlib
import time
import logging
import os

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..config.settings import Settings

# Set up logging
logger = logging.getLogger(__name__)

# Single universal prompt configuration for all trivial operations
TRIVIAL_CONFIG = {
    "max_tokens": 500,
    "temperature": 0.3,
    "prompt": """You are an intelligent text assistant. Respond to the user's request directly and helpfully. You can:

- Fix grammar, spelling, and punctuation errors
- Improve clarity, readability, and flow
- Adjust tone (professional, casual, formal, etc.)
- Make text more concise or expand with details
- Simplify complex language or add technical depth
- Create summaries, outlines, or titles
- Add examples and clarifications
- Generate new content based on the request

Always format your response with proper markdown for optimal readability:

**Text Formatting:**
- Use **bold** for emphasis and key points
- Use *italic* for subtle emphasis or technical terms
- Use `code` for technical terms, commands, or specific references

**Structure and Organization:**
- Use ## headings for major sections when covering multiple topics
- Use ### subheadings for subsections within a topic
- Use - bullet points for lists, examples, and key items
- Use 1. numbered lists for steps or ordered information
- Use > blockquotes for important notes, quotes, or callouts

**Special Content:**
- Use ```code blocks``` for code examples or formatted text
- Use --- horizontal dividers to separate distinct sections

**Examples of Good Formatting:**

For a request like "explain machine learning":
## Machine Learning Overview
Machine learning is a **subset of artificial intelligence** that enables systems to learn from data.

### Key Types
- **Supervised Learning**: Uses labeled data
- **Unsupervised Learning**: Finds patterns in unlabeled data  
- **Reinforcement Learning**: Learns through rewards

### Common Applications
1. Image recognition
2. Natural language processing
3. Recommendation systems

For content generation, structure your response logically with proper headings and sections. For text editing, maintain the original structure while improving clarity and formatting.

Be direct and concise while providing exactly what the user asks for."""
}

# Cache for frequently requested operations
@lru_cache(maxsize=1000)
def get_cached_operation_hash(request: str, text: str) -> str:
    """Generate a hash for caching purposes."""
    return hashlib.md5(f"{request}:{text}".encode()).hexdigest()


class TrivialLLMClient:
    """
    Lightweight LLM client optimized for fast text editing operations.
    
    Features:
    - Ultra-fast response times (200-500ms)
    - Cost-optimized for simple operations  
    - Streaming support for real-time diff updates
    - Operation-specific optimizations
    - Caching for common requests
    """
    
    def __init__(self):
        self.settings = Settings()
        self.client = None
        self.provider = self.settings.TRIVIAL_LLM_PROVIDER
        self.model = self.settings.TRIVIAL_LLM_MODEL
        self.enabled = self.settings.TRIVIAL_LLM_ENABLED
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        if not self.enabled:
            logger.warning("Trivial LLM client is disabled")
            return
            
        self._initialize_client()
        logger.info(f"Initialized TrivialLLMClient with provider: {self.provider}, model: {self.model}")
    
    def _initialize_client(self):
        """Initialize the appropriate client based on provider."""
        try:
            if self.provider == "grok":
                if not self.settings.TRIVIAL_LLM_API_KEY:
                    raise ValueError("TRIVIAL_LLM_API_KEY or XAI_API_KEY required for Grok")
                
                self.client = AsyncOpenAI(
                    api_key=self.settings.TRIVIAL_LLM_API_KEY,
                    base_url=self.settings.TRIVIAL_LLM_BASE_URL,
                    timeout=self.settings.TRIVIAL_LLM_TIMEOUT,
                    max_retries=self.settings.TRIVIAL_LLM_MAX_RETRIES
                )
                
            elif self.provider == "openai-mini":
                if not self.settings.TRIVIAL_LLM_API_KEY:
                    raise ValueError("TRIVIAL_LLM_API_KEY required for OpenAI")
                
                self.client = AsyncOpenAI(
                    api_key=self.settings.TRIVIAL_LLM_API_KEY,
                    timeout=self.settings.TRIVIAL_LLM_TIMEOUT,
                    max_retries=self.settings.TRIVIAL_LLM_MAX_RETRIES
                )
                self.model = "gpt-4o-mini"
                
            elif self.provider == "claude-haiku":
                if not self.settings.TRIVIAL_LLM_API_KEY:
                    raise ValueError("TRIVIAL_LLM_API_KEY required for Claude")
                
                self.client = AsyncAnthropic(
                    api_key=self.settings.TRIVIAL_LLM_API_KEY,
                    timeout=self.settings.TRIVIAL_LLM_TIMEOUT,
                    max_retries=self.settings.TRIVIAL_LLM_MAX_RETRIES
                )
                self.model = "claude-3-haiku-20240307"
                
            elif self.provider == "bedrock":
                # Initialize AWS Bedrock client
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
                    logger.info(f"Successfully initialized Bedrock client in region: {region}")
                    
                except NoCredentialsError:
                    raise ValueError("AWS credentials not found. Please configure AWS credentials via environment variables, AWS profile, or IAM role.")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'UnauthorizedOperation':
                        raise ValueError("AWS credentials don't have permission to access Bedrock. Please check IAM permissions.")
                    else:
                        raise ValueError(f"AWS Bedrock initialization failed: {e}")
                except Exception as e:
                    raise ValueError(f"Unexpected error calling Bedrock: {e}")
                
            else:
                raise ValueError(f"Unsupported trivial LLM provider: {self.provider}")
                
        except Exception as e:
            logger.error(f"Failed to initialize trivial LLM client: {e}")
            self.enabled = False
            raise
    
    def _get_operation_config(self, operation: str) -> Dict[str, Any]:
        """Get configuration for trivial operations."""
        return TRIVIAL_CONFIG
    
    def _build_prompt(self, operation: str, text: str, context: Optional[Dict] = None) -> str:
        """Build an optimized prompt for the operation."""
        logger.info(f"🔨 TrivialClient: Building prompt for request '{operation}'")
        logger.info(f"🔨 TrivialClient: Text length: {len(text)}")
        logger.info(f"🔨 TrivialClient: Text content: '{text}'")
        logger.info(f"🔨 TrivialClient: Context: {context}")
        
        config = self._get_operation_config(operation)
        base_prompt = config["prompt"]
        
        # Add context if provided
        context_note = ""
        if context:
            block_type = context.get("block_type", "text")
            if block_type != "text":
                context_note = f"\n\nNote: This is a {block_type} block."
        
        # Determine if this is content generation vs text editing
        is_content_generation = not text.strip()
        
        if is_content_generation:
            # For content generation, just respond to the user's request directly
            final_prompt = f"{base_prompt}{context_note}\n\nUser Request: {operation}\n\nProvide a direct response to the user's request using proper markdown formatting. Do not include meta-commentary or structure analysis."
        else:
            # For text editing, frame it as improvement
            final_prompt = f"{base_prompt}{context_note}\n\nUser Request: {operation}\n\nText to improve: {text}"
        
        logger.info(f"🔨 TrivialClient: Final prompt: '{final_prompt}'")
        return final_prompt
    
    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check if result is cached and still valid."""
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for key: {cache_key[:10]}...")
                return result
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, result: str):
        """Cache the result."""
        self._cache[cache_key] = (result, time.time())
        
        # Simple cache cleanup - remove oldest if too large
        if len(self._cache) > 1000:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
    
    def _prepare_bedrock_request(self, prompt: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare request body for Bedrock based on model type."""
        if self.model.startswith("anthropic.claude"):
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"],
                "messages": [{"role": "user", "content": prompt}]
            }
        elif self.model.startswith("amazon.titan"):
            return {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": config["max_tokens"],
                    "temperature": config["temperature"],
                    "topP": 0.9
                }
            }
        elif self.model.startswith("cohere.command"):
            return {
                "prompt": prompt,
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"],
                "p": 0.9
            }
        elif self.model.startswith("ai21.j2"):
            return {
                "prompt": prompt,
                "maxTokens": config["max_tokens"],
                "temperature": config["temperature"]
            }
        elif self.model.startswith("amazon.nova"):
            return {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "maxTokens": config["max_tokens"],
                    "temperature": config["temperature"]
                }
            }
        else:
            # Default format (works for most models)
            return {
                "prompt": prompt,
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"]
            }
    
    def _extract_bedrock_response(self, response_body: Dict[str, Any]) -> str:
        """Extract text from Bedrock response based on model type."""
        if self.model.startswith("anthropic.claude"):
            return response_body.get("content", [{}])[0].get("text", "")
        elif self.model.startswith("amazon.titan"):
            return response_body.get("results", [{}])[0].get("outputText", "")
        elif self.model.startswith("cohere.command"):
            return response_body.get("generations", [{}])[0].get("text", "")
        elif self.model.startswith("ai21.j2"):
            return response_body.get("completions", [{}])[0].get("data", {}).get("text", "")
        elif self.model.startswith("amazon.nova"):
            return response_body.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
        else:
            # Try common response formats
            return (response_body.get("completion") or 
                   response_body.get("text") or 
                   response_body.get("output") or 
                   str(response_body))
    
    def _invoke_bedrock_model(self, prompt: str, config: Dict[str, Any], stream: bool = False) -> Any:
        """Invoke Bedrock model with proper error handling."""
        request_body = self._prepare_bedrock_request(prompt, config)
        
        try:
            if stream:
                response = self.client.invoke_model_with_response_stream(
                    modelId=self.model,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json"
                )
                return response
            else:
                response = self.client.invoke_model(
                    modelId=self.model,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json"
                )
                
                response_body = json.loads(response['body'].read())
                return self._extract_bedrock_response(response_body)
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ValidationException':
                raise ValueError(f"Invalid request to Bedrock model {self.model}: {e}")
            elif error_code == 'AccessDeniedException':
                raise ValueError(f"Access denied to Bedrock model {self.model}. Check IAM permissions and model access.")
            elif error_code == 'ThrottlingException':
                raise ValueError(f"Bedrock API rate limit exceeded. Please retry later.")
            else:
                raise ValueError(f"Bedrock API error: {e}")
        except Exception as e:
            raise ValueError(f"Unexpected error calling Bedrock: {e}")
    
    async def process_operation(
        self, 
        operation: str, 
        text: str, 
        context: Optional[Dict] = None
    ) -> str:
        """
        Process a trivial text improvement request and return the result.
        
        Args:
            operation: The user's request (e.g., "fix grammar", "make this more professional", "give me a short paragraph on India's independence")
            text: The text to process
            context: Optional context about the block/document
            
        Returns:
            The processed text
        """
        if not self.enabled or not self.client:
            logger.warning("Trivial LLM client not available, returning original text")
            return text
        
        # Check cache first
        cache_key = get_cached_operation_hash(operation, text)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            return cached_result
        
        start_time = time.time()
        config = self._get_operation_config(operation)
        prompt = self._build_prompt(operation, text, context)
        
        try:
            if self.provider in ["grok", "openai-mini"]:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"],
                    stream=False
                )
                result = response.choices[0].message.content.strip()
                
            elif self.provider == "claude-haiku":
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"],
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text.strip()
                
            elif self.provider == "bedrock":
                # Use asyncio to run the synchronous Bedrock call
                result = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self._invoke_bedrock_model(prompt, config, stream=False)
                )
                result = result.strip() if result else text
                
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
            
            # Cache the result
            self._set_cache(cache_key, result)
            
            duration = time.time() - start_time
            logger.info(f"Trivial request '{operation}' completed in {duration:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in trivial request '{operation}': {e}")
            # Return original text on error
            return text
    
    async def stream_operation(
        self, 
        operation: str, 
        text: str, 
        context: Optional[Dict] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a trivial text improvement request for real-time updates.
        
        Args:
            operation: The user's request (e.g., "fix grammar", "make this more professional", "give me a short paragraph on India's independence")
            text: The text to process
            context: Optional context about the block/document
        
        Yields:
            Dictionary with streaming updates
        """
        if not self.enabled or not self.client:
            yield {
                "type": "error",
                "message": "Trivial LLM client not available",
                "original_text": text
            }
            return
        
        # Check cache first
        cache_key = get_cached_operation_hash(operation, text)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            yield {
                "type": "complete",
                "result": cached_result,
                "cached": True,
                "duration": 0.0
            }
            return
        
        start_time = time.time()
        config = self._get_operation_config(operation)
        prompt = self._build_prompt(operation, text, context)
        
        yield {
            "type": "start",
            "operation": operation,
            "provider": self.provider,
            "model": self.model
        }
        
        try:
            if self.provider in ["grok", "openai-mini"]:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"],
                    stream=True
                )
                
                result_buffer = ""
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        result_buffer += content
                        
                        yield {
                            "type": "chunk",
                            "content": content,
                            "partial_result": result_buffer
                        }
                
                # Cache the final result
                self._set_cache(cache_key, result_buffer)
                
                yield {
                    "type": "complete",
                    "result": result_buffer,
                    "cached": False,
                    "duration": time.time() - start_time
                }
                
            elif self.provider == "claude-haiku":
                # Claude doesn't support streaming in the same way, so we'll do a single request
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"],
                    messages=[{"role": "user", "content": prompt}]
                )
                
                result = response.content[0].text.strip()
                self._set_cache(cache_key, result)
                
                yield {
                    "type": "complete",
                    "result": result,
                    "cached": False,
                    "duration": time.time() - start_time
                }
                
            elif self.provider == "bedrock":
                # Handle Bedrock streaming
                try:
                    stream_response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self._invoke_bedrock_model(prompt, config, stream=True)
                    )
                    
                    result_buffer = ""
                    
                    # Process streaming response
                    for event in stream_response['body']:
                        chunk_data = json.loads(event['chunk']['bytes'])
                        
                        # Extract content based on model type
                        content = ""
                        if self.model.startswith("anthropic.claude"):
                            if chunk_data.get('type') == 'content_block_delta':
                                content = chunk_data.get('delta', {}).get('text', '')
                        elif self.model.startswith("amazon.titan"):
                            content = chunk_data.get('outputText', '')
                        elif self.model.startswith("amazon.nova"):
                            if chunk_data.get('contentBlockDelta'):
                                content = chunk_data['contentBlockDelta'].get('text', '')
                        else:
                            # Try to extract content from common formats
                            content = (chunk_data.get('text') or 
                                     chunk_data.get('completion') or 
                                     chunk_data.get('output', ''))
                        
                        if content:
                            result_buffer += content
                            yield {
                                "type": "chunk",
                                "content": content,
                                "partial_result": result_buffer
                            }
                    
                    # Cache the final result
                    self._set_cache(cache_key, result_buffer)
                    
                    yield {
                        "type": "complete",
                        "result": result_buffer,
                        "cached": False,
                        "duration": time.time() - start_time
                    }
                    
                except Exception as bedrock_error:
                    logger.warning(f"Bedrock streaming failed, falling back to non-streaming: {bedrock_error}")
                    # Fallback to non-streaming for Bedrock
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self._invoke_bedrock_model(prompt, config, stream=False)
                    )
                    result = result.strip() if result else text
                    self._set_cache(cache_key, result)
                    
                    yield {
                        "type": "complete",
                        "result": result,
                        "cached": False,
                        "duration": time.time() - start_time
                    }
            
        except Exception as e:
            logger.error(f"Error in streaming trivial request '{operation}': {e}")
            yield {
                "type": "error",
                "message": str(e),
                "original_text": text
            }
    
    def get_supported_operations(self) -> List[str]:
        """Get list of supported trivial operations."""
        # Return indicator that all natural language requests are supported
        # This allows the frontend to pass through any user request without categorization
        return ["natural_language_request"]
    
    def is_enabled(self) -> bool:
        """Check if the trivial client is enabled and ready."""
        return self.enabled and self.client is not None
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the trivial LLM client."""
        if not self.enabled:
            return {
                "status": "disabled",
                "provider": self.provider,
                "message": "Trivial LLM client is disabled"
            }
        
        try:
            # Quick test operation
            test_result = await self.process_operation(
                "fix_spelling", 
                "Thsi is a test sentnce.",
                context={"block_type": "text"}
            )
            
            return {
                "status": "healthy",
                "provider": self.provider,
                "model": self.model,
                "test_successful": True,
                "cache_size": len(self._cache),
                "supports_natural_language": True,
                "supported_operations": self.get_supported_operations()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider,
                "message": str(e),
                "test_successful": False
            }


# Global instance
_trivial_client = None

def get_trivial_llm_client() -> TrivialLLMClient:
    """Get the global trivial LLM client instance."""
    global _trivial_client
    if _trivial_client is None:
        _trivial_client = TrivialLLMClient()
    return _trivial_client 