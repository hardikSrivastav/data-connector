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

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from ..config.settings import Settings

# Set up logging
logger = logging.getLogger(__name__)

# Operation-specific configurations for optimal performance
TRIVIAL_OPERATIONS = {
    "fix_grammar": {
        "max_tokens": 200,
        "temperature": 0.1,
        "prompt": "Fix any grammar and spelling errors in the following text. Preserve the original meaning and style. Only return the corrected text:",
    },
    "improve_clarity": {
        "max_tokens": 300,
        "temperature": 0.2,
        "prompt": "Improve the clarity and readability of the following text. Make it more concise and clear while preserving the original meaning:",
    },
    "make_concise": {
        "max_tokens": 150,
        "temperature": 0.1,
        "prompt": "Make the following text more concise while preserving all key information and meaning:",
    },
    "fix_spelling": {
        "max_tokens": 100,
        "temperature": 0.0,
        "prompt": "Fix any spelling errors in the following text. Preserve everything else exactly:",
    },
    "improve_tone": {
        "max_tokens": 300,
        "temperature": 0.3,
        "prompt": "Improve the tone of the following text to be more professional and engaging:",
    },
    "expand_text": {
        "max_tokens": 400,
        "temperature": 0.4,
        "prompt": "Expand the following text with more detail and explanation while maintaining the original meaning:",
    },
    "simplify_language": {
        "max_tokens": 250,
        "temperature": 0.2,
        "prompt": "Simplify the language in the following text to make it easier to understand:",
    },
    "add_examples": {
        "max_tokens": 400,
        "temperature": 0.4,
        "prompt": "Add relevant examples or clarifications to the following text to make it clearer:",
    },
    "summarize_content": {
        "max_tokens": 300,
        "temperature": 0.2,
        "prompt": "Create a concise summary of the following content. Focus on the key points and main ideas:",
    },
    "generate_title": {
        "max_tokens": 50,
        "temperature": 0.3,
        "prompt": "Generate a clear, descriptive title for the following content:",
    },
    "create_outline": {
        "max_tokens": 200,
        "temperature": 0.2,
        "prompt": "Create a structured outline of the key points from the following content:",
    }
}

# Cache for frequently requested operations
@lru_cache(maxsize=1000)
def get_cached_operation_hash(operation: str, text: str) -> str:
    """Generate a hash for caching purposes."""
    return hashlib.md5(f"{operation}:{text}".encode()).hexdigest()


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
                
            else:
                raise ValueError(f"Unsupported trivial LLM provider: {self.provider}")
                
        except Exception as e:
            logger.error(f"Failed to initialize trivial LLM client: {e}")
            self.enabled = False
            raise
    
    def _get_operation_config(self, operation: str) -> Dict[str, Any]:
        """Get configuration for a specific operation."""
        return TRIVIAL_OPERATIONS.get(operation, {
            "max_tokens": self.settings.TRIVIAL_LLM_MAX_TOKENS,
            "temperature": self.settings.TRIVIAL_LLM_TEMPERATURE,
            "prompt": f"Perform the following operation on the text: {operation}. Return only the modified text:",
        })
    
    def _build_prompt(self, operation: str, text: str, context: Optional[Dict] = None) -> str:
        """Build an optimized prompt for the operation."""
        logger.info(f"🔨 TrivialClient: Building prompt for operation '{operation}'")
        logger.info(f"🔨 TrivialClient: Text length: {len(text)}")
        logger.info(f"🔨 TrivialClient: Text content: '{text}'")
        logger.info(f"🔨 TrivialClient: Context: {context}")
        
        config = self._get_operation_config(operation)
        prompt = config["prompt"]
        
        # Add context if provided
        if context:
            block_type = context.get("block_type", "text")
            if block_type != "text":
                prompt += f"\n\nNote: This is a {block_type} block."
        
        final_prompt = f"{prompt}\n\nText: {text}"
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
    
    async def process_operation(
        self, 
        operation: str, 
        text: str, 
        context: Optional[Dict] = None
    ) -> str:
        """
        Process a single trivial operation and return the result.
        
        Args:
            operation: The type of operation (e.g., "fix_grammar", "make_concise")
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
                
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
            
            # Cache the result
            self._set_cache(cache_key, result)
            
            duration = time.time() - start_time
            logger.info(f"Trivial operation '{operation}' completed in {duration:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in trivial operation '{operation}': {e}")
            # Return original text on error
            return text
    
    async def stream_operation(
        self, 
        operation: str, 
        text: str, 
        context: Optional[Dict] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a trivial operation for real-time diff updates.
        
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
            
        except Exception as e:
            logger.error(f"Error in streaming trivial operation '{operation}': {e}")
            yield {
                "type": "error",
                "message": str(e),
                "original_text": text
            }
    
    def get_supported_operations(self) -> List[str]:
        """Get list of supported trivial operations."""
        return list(TRIVIAL_OPERATIONS.keys())
    
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
                "cache_size": len(self._cache)
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