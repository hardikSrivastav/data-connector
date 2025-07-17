"""
LangGraph Classification Node

Integrates the existing DatabaseClassifier into the LangGraph workflow for 
iterative query processing and database selection.
"""

import logging
import time
from typing import Dict, List, Any, Optional, AsyncIterator

from ..streaming import StreamingNodeBase
from ..state import LangGraphState
from ...db.classifier import DatabaseClassifier
from ...db.registry.integrations import registry_client

logger = logging.getLogger(__name__)

class ClassificationNode(StreamingNodeBase):
    """
    Classification node that determines relevant databases for a query.
    
    This node integrates the existing DatabaseClassifier into the LangGraph
    workflow, providing database selection with streaming progress updates.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Initialize the database classifier
        self.classifier = DatabaseClassifier()
        
        # Cache for preventing re-initialization
        self._classification_cache = {}
        
        logger.info("🔍 ClassificationNode initialized with database classifier")
    
    async def __call__(self, state: LangGraphState, **kwargs) -> Dict[str, Any]:
        """Non-streaming execution of classification node."""
        logger.info("🔍 [CLASSIFICATION] Starting non-streaming classification")
        
        # Get the user query from state
        user_query = state.get("user_query", state.get("question", ""))
        session_id = state.get("session_id", "unknown")
        
        if not user_query:
            logger.error("🔍 [CLASSIFICATION] No user query found in state")
            return {"classification_error": "No user query provided"}
        
        logger.info(f"🔍 [CLASSIFICATION] Processing query: '{user_query}' (session: {session_id})")
        
        # Check cache to prevent re-initialization
        cache_key = f"{session_id}_{hash(user_query)}"
        if cache_key in self._classification_cache:
            logger.info("🔍 [CLASSIFICATION] Using cached classification result")
            cached_result = self._classification_cache[cache_key]
            
            # Update state with cached results
            state.update({
                "databases_identified": cached_result["database_types"],
                "classification_sources": cached_result["sources"],
                "classification_reasoning": cached_result["reasoning"],
                "is_cross_database": cached_result["is_cross_database"],
                "classification_metadata": cached_result["raw_metadata"]
            })
            
            return state
        
        try:
            # Step 1: Perform database classification
            logger.info("🔍 [CLASSIFICATION] Step 1: Performing database classification")
            start_time = time.time()
            
            classification_result = await self.classifier.classify(user_query)
            
            classification_time = time.time() - start_time
            logger.info(f"🔍 [CLASSIFICATION] Classification completed in {classification_time:.2f}s")
            
            # Step 2: Process classification results
            logger.info("🔍 [CLASSIFICATION] Step 2: Processing classification results")
            
            sources = classification_result.get("sources", [])
            reasoning = classification_result.get("reasoning", "")
            schema_metadata = classification_result.get("schema_metadata", {})
            
            # Extract database types from sources
            database_types = []
            enhanced_sources = []
            
            # Get all sources for type mapping
            all_sources = registry_client.get_all_sources()
            sources_by_id = {s["id"]: s for s in all_sources}
            
            for source_id in sources:
                if source_id in sources_by_id:
                    source = sources_by_id[source_id]
                    db_type = source.get("type", "unknown")
                    database_types.append(db_type)
                    
                    enhanced_sources.append({
                        "id": source_id,
                        "type": db_type,
                        "name": source.get("name", source_id),
                        "relevance": "high"  # Could implement scoring here
                    })
                    
                    logger.info(f"🔍 [CLASSIFICATION] Identified relevant database: {db_type} ({source_id})")
            
            # Remove duplicates while preserving order
            unique_database_types = list(dict.fromkeys(database_types))
            is_cross_database = len(unique_database_types) > 1
            
            logger.info(f"🔍 [CLASSIFICATION] Step 3: Classification summary")
            logger.info(f"🔍 [CLASSIFICATION] - Databases identified: {unique_database_types}")
            logger.info(f"🔍 [CLASSIFICATION] - Cross-database query: {is_cross_database}")
            logger.info(f"🔍 [CLASSIFICATION] - Total sources: {len(enhanced_sources)}")
            
            # Step 4: Cache results
            logger.info("🔍 [CLASSIFICATION] Step 4: Caching results for future use")
            
            cache_result = {
                "database_types": unique_database_types,
                "sources": enhanced_sources,
                "reasoning": reasoning,
                "is_cross_database": is_cross_database,
                "raw_metadata": schema_metadata,
                "classification_time": classification_time
            }
            
            self._classification_cache[cache_key] = cache_result
            
            # Step 5: Update state
            logger.info("🔍 [CLASSIFICATION] Step 5: Updating LangGraph state")
            
            state.update({
                "databases_identified": unique_database_types,
                "classification_sources": enhanced_sources,
                "classification_reasoning": reasoning,
                "is_cross_database": is_cross_database,
                "classification_metadata": schema_metadata,
                "classification_completed": True,
                "classification_duration": classification_time
            })
            
            logger.info("🔍 [CLASSIFICATION] Classification node completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"🔍 [CLASSIFICATION] Error during classification: {str(e)}")
            logger.exception("🔍 [CLASSIFICATION] Full error traceback:")
            
            # Update state with error information
            state.update({
                "classification_error": str(e),
                "databases_identified": [],
                "classification_sources": [],
                "is_cross_database": False
            })
            
            return state
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming execution of classification with progress updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional arguments
            
        Yields:
            Progress chunks with classification updates
        """
        user_query = state.get("user_query", state.get("question", ""))
        session_id = state.get("session_id", "unknown")
        
        logger.info(f"🔍 [CLASSIFICATION STREAM] Starting streaming classification for: '{user_query}'")
        
        if not user_query:
            yield self.create_progress_chunk(
                100.0,
                "Classification failed - no query provided",
                {"error": "No user query found in state"}
            )
            return
        
        # Check cache first
        cache_key = f"{session_id}_{hash(user_query)}"
        if cache_key in self._classification_cache:
            logger.info("🔍 [CLASSIFICATION STREAM] Using cached classification result")
            
            yield self.create_progress_chunk(
                20.0,
                "Retrieving cached classification results",
                {"cache_used": True, "session_id": session_id}
            )
            
            cached_result = self._classification_cache[cache_key]
            
            yield self.create_progress_chunk(
                50.0,
                f"Found {len(cached_result['database_types'])} relevant databases",
                {
                    "databases": cached_result['database_types'],
                    "cross_database": cached_result['is_cross_database']
                }
            )
            
            # Update state with cached results
            state.update({
                "databases_identified": cached_result["database_types"],
                "classification_sources": cached_result["sources"],
                "classification_reasoning": cached_result["reasoning"],
                "is_cross_database": cached_result["is_cross_database"],
                "classification_metadata": cached_result["raw_metadata"]
            })
            
            yield self.create_progress_chunk(
                100.0,
                "Classification completed using cached results",
                {
                    "databases_identified": cached_result["database_types"],
                    "total_sources": len(cached_result["sources"]),
                    "cache_used": True
                }
            )
            return
        
        try:
            # Step 1: Initialize classification
            yield self.create_progress_chunk(
                10.0,
                "Initializing database classification",
                {
                    "query": user_query,
                    "session_id": session_id,
                    "step": "initialization"
                }
            )
            
            logger.info("🔍 [CLASSIFICATION STREAM] Step 1: Initializing classification")
            
            # Step 2: Analyze query semantics
            yield self.create_progress_chunk(
                25.0,
                "Analyzing query semantics and keywords",
                {"step": "semantic_analysis"}
            )
            
            logger.info("🔍 [CLASSIFICATION STREAM] Step 2: Analyzing query semantics")
            
            # Step 3: Search schema metadata
            yield self.create_progress_chunk(
                40.0,
                "Searching schema metadata for relevant databases",
                {"step": "schema_search"}
            )
            
            logger.info("🔍 [CLASSIFICATION STREAM] Step 3: Searching schema metadata")
            
            # Perform the actual classification
            start_time = time.time()
            classification_result = await self.classifier.classify(user_query)
            classification_time = time.time() - start_time
            
            # Step 4: Process results
            yield self.create_progress_chunk(
                65.0,
                "Processing classification results",
                {"step": "result_processing", "duration": classification_time}
            )
            
            logger.info(f"🔍 [CLASSIFICATION STREAM] Step 4: Processing results (took {classification_time:.2f}s)")
            
            sources = classification_result.get("sources", [])
            reasoning = classification_result.get("reasoning", "")
            schema_metadata = classification_result.get("schema_metadata", {})
            
            # Extract database types from sources
            database_types = []
            enhanced_sources = []
            
            # Get all sources for type mapping
            all_sources = registry_client.get_all_sources()
            sources_by_id = {s["id"]: s for s in all_sources}
            
            for source_id in sources:
                if source_id in sources_by_id:
                    source = sources_by_id[source_id]
                    db_type = source.get("type", "unknown")
                    database_types.append(db_type)
                    
                    enhanced_sources.append({
                        "id": source_id,
                        "type": db_type,
                        "name": source.get("name", source_id),
                        "relevance": "high"
                    })
            
            unique_database_types = list(dict.fromkeys(database_types))
            is_cross_database = len(unique_database_types) > 1
            
            # Step 5: Report findings
            yield self.create_progress_chunk(
                80.0,
                f"Identified {len(unique_database_types)} relevant database types",
                {
                    "databases_found": unique_database_types,
                    "cross_database": is_cross_database,
                    "total_sources": len(enhanced_sources),
                    "step": "findings"
                }
            )
            
            logger.info(f"🔍 [CLASSIFICATION STREAM] Step 5: Found databases: {unique_database_types}")
            logger.info(f"🔍 [CLASSIFICATION STREAM] Cross-database query: {is_cross_database}")
            
            # Step 6: Cache and finalize
            cache_result = {
                "database_types": unique_database_types,
                "sources": enhanced_sources,
                "reasoning": reasoning,
                "is_cross_database": is_cross_database,
                "raw_metadata": schema_metadata,
                "classification_time": classification_time
            }
            
            self._classification_cache[cache_key] = cache_result
            
            # Update state
            state.update({
                "databases_identified": unique_database_types,
                "classification_sources": enhanced_sources,
                "classification_reasoning": reasoning,
                "is_cross_database": is_cross_database,
                "classification_metadata": schema_metadata,
                "classification_completed": True,
                "classification_duration": classification_time
            })
            
            yield self.create_progress_chunk(
                100.0,
                "Database classification completed successfully",
                {
                    "databases_identified": unique_database_types,
                    "is_cross_database": is_cross_database,
                    "total_sources": len(enhanced_sources),
                    "classification_time": classification_time,
                    "reasoning_preview": reasoning[:100] + "..." if len(reasoning) > 100 else reasoning
                }
            )
            
            logger.info("🔍 [CLASSIFICATION STREAM] Classification completed successfully")
            
        except Exception as e:
            logger.error(f"🔍 [CLASSIFICATION STREAM] Error during streaming classification: {str(e)}")
            logger.exception("🔍 [CLASSIFICATION STREAM] Full error traceback:")
            
            yield self.create_progress_chunk(
                100.0,
                f"Classification failed: {str(e)}",
                {
                    "error": str(e),
                    "step": "error"
                }
            )
            
            # Update state with error
            state.update({
                "classification_error": str(e),
                "databases_identified": [],
                "classification_sources": [],
                "is_cross_database": False
            })
    
    def get_classification_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities of the classification node.
        
        Returns:
            Dictionary describing classification capabilities
        """
        return {
            "supported_databases": list(self.classifier.default_keywords.keys()),
            "classification_methods": [
                "keyword_based",
                "schema_based",
                "registry_based"
            ],
            "features": {
                "caching": True,
                "streaming": True,
                "cross_database_detection": True,
                "schema_metadata_integration": True
            },
            "integration": {
                "database_classifier": True,
                "registry_client": True,
                "langgraph_state": True
            }
        }
    
    def get_node_capabilities(self) -> Dict[str, Any]:
        """
        Get node capabilities and metadata (alias for test compatibility).
        
        Returns:
            Dictionary describing node capabilities
        """
        return {
            "node_type": "classification",
            "supports_streaming": True,
            "supports_non_streaming": True,
            "capabilities": [
                "database_classification",
                "cross_database_detection",
                "source_identification",
                "query_routing"
            ],
            "version": "1.0.0"
        } 