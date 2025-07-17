"""
Iterative Metadata Collection Node for Enhanced LangGraph Workflows

This node implements the first phase of the iterative LangGraph approach, providing:
- Dynamic metadata fetching based on classification results
- Integration with database-specific implementations in /adapters
- Prevention of re-initialization for already pulled data
- Real-time streaming with comprehensive logging
- Connection to integration.py and builder.py
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator, Set
from datetime import datetime

from ..streaming import StreamingNodeBase
from ..state import LangGraphState
from ...db.adapters import PostgresAdapter, MongoAdapter, QdrantAdapter, SlackAdapter, ShopifyAdapter, GA4Adapter
from ...db.registry.integrations import registry_client
from ...config.settings import Settings

logger = logging.getLogger(__name__)

class IterativeMetadataNode(StreamingNodeBase):
    """
    Enhanced metadata collection node for iterative LangGraph workflows.
    
    Features:
    - Dynamic adapter integration based on classification results
    - Intelligent caching to prevent re-initialization
    - Iterative schema discovery with real-time updates
    - Direct database adapter integration
    - Performance-optimized parallel processing
    - Comprehensive error handling and recovery
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("iterative_metadata")
        
        self.config = config or {}
        self.settings = Settings()
        
        # Database adapter registry
        self._initialize_adapter_registry()
        
        # Active adapter instances
        self.active_adapters: Dict[str, Any] = {}
        
        # Metadata cache to prevent re-initialization
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        self.schema_cache: Dict[str, List[Dict[str, str]]] = {}
        self.connection_cache: Dict[str, bool] = {}
        
        # Session-based tracking
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
        self.initialized_sources: Dict[str, Set[str]] = {}  # session_id -> set of source_ids
        
        # Performance tracking
        self.performance_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "adapter_initializations": 0,
            "schema_discoveries": 0,
            "failed_connections": 0
        }
        
        logger.info("🔧 [ITERATIVE_METADATA] Initialized IterativeMetadataNode with enhanced adapter integration")
    
    def _initialize_adapter_registry(self):
        """Initialize the database adapter registry."""
        # Use the existing adapter registry from the adapters module
        from ...db.adapters import ADAPTER_REGISTRY
        
        # Create a copy and add any additional mappings
        self.adapter_registry = ADAPTER_REGISTRY.copy()
        
        # Add additional aliases
        self.adapter_registry["google_analytics"] = self.adapter_registry["ga4"]
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming execution with iterative metadata collection.
        
        Args:
            state: Current LangGraph state with classification results
            **kwargs: Additional execution parameters
            
        Yields:
            Progress chunks with metadata collection updates
        """
        session_id = state.get("session_id", "unknown")
        classification_sources = state.get("classification_sources", [])
        databases_identified = state.get("databases_identified", [])
        
        logger.info(f"🔧 [ITERATIVE_METADATA] Starting iterative metadata collection for session: {session_id}")
        logger.info(f"🔧 [ITERATIVE_METADATA] Databases identified: {databases_identified}")
        logger.info(f"🔧 [ITERATIVE_METADATA] Sources: {[s.get('id', 'unknown') for s in classification_sources]}")
        
        if not databases_identified and not classification_sources:
            logger.warning("🔧 [ITERATIVE_METADATA] No databases or sources identified for metadata collection")
            yield self.create_result_chunk(
                {"warning": "No databases identified for metadata collection"},
                {"schema_metadata": {}, "available_tables": [], "adapter_status": {}},
                is_final=True
            )
            return
        
        try:
            # Step 1: Initialize session tracking
            yield self.create_progress_chunk(
                5.0,
                "Initializing iterative metadata collection",
                {"current_step": 1, "total_steps": 7, "session_id": session_id}
            )
            
            self._initialize_session_tracking(session_id)
            start_time = time.time()
            
            # Step 2: Determine what needs to be fetched (prevent re-initialization)
            yield self.create_progress_chunk(
                10.0,
                "Analyzing required metadata sources",
                {"current_step": 2}
            )
            
            sources_to_process = await self._determine_sources_to_process(
                session_id,
                classification_sources,
                databases_identified
            )
            
            if not sources_to_process:
                logger.info("🔧 [ITERATIVE_METADATA] All required metadata already cached")
                cached_metadata = self._get_cached_metadata(session_id, classification_sources)
                
                yield self.create_result_chunk(
                    cached_metadata,
                    {"metadata_source": "cache", "cache_performance": self.performance_stats},
                    is_final=True
                )
                return
            
            logger.info(f"🔧 [ITERATIVE_METADATA] Processing {len(sources_to_process)} new sources")
            
            # Step 3: Initialize database adapters
            yield self.create_progress_chunk(
                20.0,
                "Initializing database adapters",
                {"current_step": 3, "sources_to_process": len(sources_to_process)}
            )
            
            adapter_status = await self._initialize_adapters(sources_to_process)
            
            # Step 4: Test connections in parallel
            yield self.create_progress_chunk(
                30.0,
                "Testing database connections",
                {"current_step": 4, "adapter_status": adapter_status}
            )
            
            connection_results = await self._test_connections_parallel(sources_to_process)
            
            # Step 5: Collect metadata iteratively
            yield self.create_progress_chunk(
                40.0,
                "Collecting metadata iteratively",
                {"current_step": 5, "connection_results": connection_results}
            )
            
            metadata_results = {}
            async for progress_update in self._collect_metadata_iteratively(
                sources_to_process,
                connection_results,
                session_id
            ):
                # Forward progress updates from metadata collection
                if progress_update.get("type") == "progress":
                    base_progress = 40.0 + (progress_update.get("progress", 0) * 0.3)  # Map to 40-70%
                    yield self.create_progress_chunk(
                        base_progress,
                        progress_update.get("operation", "Collecting metadata"),
                        {"metadata_progress": progress_update}
                    )
                elif progress_update.get("type") == "result":
                    metadata_results.update(progress_update.get("data", {}))
            
            # Step 6: Process and optimize collected metadata
            yield self.create_progress_chunk(
                75.0,
                "Processing and optimizing metadata",
                {"current_step": 6}
            )
            
            optimized_metadata = await self._process_and_optimize_metadata(
                metadata_results,
                session_id
            )
            
            # Step 7: Update caches and prepare final result
            yield self.create_progress_chunk(
                90.0,
                "Updating caches and finalizing",
                {"current_step": 7}
            )
            
            await self._update_caches(session_id, optimized_metadata, sources_to_process)
            
            # Prepare comprehensive result
            final_result = await self._prepare_final_result(
                optimized_metadata,
                adapter_status,
                connection_results,
                start_time,
                session_id
            )
            
            # Final result with comprehensive metadata
            yield self.create_result_chunk(
                final_result,
                {
                    "metadata_collection_complete": True,
                    "session_metadata_updated": True,
                    "performance_stats": self.performance_stats
                },
                is_final=True
            )
            
            logger.info(f"🔧 [ITERATIVE_METADATA] Completed iterative metadata collection in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            logger.error(f"🔧 [ITERATIVE_METADATA] Error during iterative metadata collection: {e}")
            logger.exception("🔧 [ITERATIVE_METADATA] Full error traceback:")
            
            yield self.create_result_chunk(
                {"error": str(e), "metadata_collection_failed": True},
                {"schema_metadata": {}, "available_tables": [], "error_details": str(e)},
                is_final=True
            )
    
    def _initialize_session_tracking(self, session_id: str):
        """Initialize tracking for this session."""
        if session_id not in self.session_metadata:
            self.session_metadata[session_id] = {
                "start_time": time.time(),
                "adapters_initialized": {},
                "metadata_collected": {},
                "last_update": time.time()
            }
        
        if session_id not in self.initialized_sources:
            self.initialized_sources[session_id] = set()
    
    async def _determine_sources_to_process(
        self,
        session_id: str,
        classification_sources: List[Dict[str, Any]],
        databases_identified: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Determine which sources need processing to prevent re-initialization.
        
        Args:
            session_id: Current session ID
            classification_sources: Sources from classification
            databases_identified: Database types identified
            
        Returns:
            List of sources that need processing
        """
        sources_to_process = []
        already_initialized = self.initialized_sources.get(session_id, set())
        
        logger.info(f"🔧 [ITERATIVE_METADATA] Already initialized sources: {already_initialized}")
        
        # Process classification sources
        for source in classification_sources:
            source_id = source.get("id")
            if source_id and source_id not in already_initialized:
                sources_to_process.append(source)
                logger.info(f"🔧 [ITERATIVE_METADATA] Will process source: {source_id} ({source.get('type', 'unknown')})")
            else:
                logger.info(f"🔧 [ITERATIVE_METADATA] Skipping already initialized source: {source_id}")
                self.performance_stats["cache_hits"] += 1
        
        # If no classification sources, create sources from database types
        if not classification_sources and databases_identified:
            logger.info("🔧 [ITERATIVE_METADATA] No classification sources, creating from database types")
            
            # Get all available sources to match with database types
            all_sources = registry_client.get_all_sources()
            for db_type in databases_identified:
                matching_sources = [s for s in all_sources if s.get("type") == db_type]
                for source in matching_sources:
                    source_id = source.get("id")
                    if source_id not in already_initialized:
                        sources_to_process.append({
                            "id": source_id,
                            "type": db_type,
                            "name": source.get("name", source_id),
                            "relevance": "high"
                        })
        
        if sources_to_process:
            self.performance_stats["cache_misses"] += len(sources_to_process)
        
        logger.info(f"🔧 [ITERATIVE_METADATA] Determined {len(sources_to_process)} sources to process")
        return sources_to_process
    
    async def _initialize_adapters(
        self,
        sources_to_process: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Initialize database adapters for the sources that need processing.
        
        Args:
            sources_to_process: Sources requiring adapter initialization
            
        Returns:
            Adapter initialization status
        """
        adapter_status = {}
        
        for source in sources_to_process:
            source_id = source.get("id")
            db_type = source.get("type", "").lower()
            
            logger.info(f"🔧 [ITERATIVE_METADATA] Initializing adapter for {source_id} ({db_type})")
            
            try:
                if db_type in self.adapter_registry:
                    # Get connection details from registry
                    source_details = registry_client.get_source_details(source_id)
                    if source_details and source_details.get("connection_uri"):
                        adapter_class = self.adapter_registry[db_type]
                        adapter_instance = adapter_class(source_details["connection_uri"])
                        
                        self.active_adapters[source_id] = adapter_instance
                        adapter_status[source_id] = {
                            "status": "initialized",
                            "type": db_type,
                            "adapter_class": adapter_class.__name__
                        }
                        
                        self.performance_stats["adapter_initializations"] += 1
                        logger.info(f"🔧 [ITERATIVE_METADATA] Successfully initialized {db_type} adapter for {source_id}")
                    else:
                        adapter_status[source_id] = {
                            "status": "failed",
                            "error": "No connection URI available"
                        }
                        logger.warning(f"🔧 [ITERATIVE_METADATA] No connection URI for source: {source_id}")
                else:
                    adapter_status[source_id] = {
                        "status": "unsupported",
                        "error": f"No adapter available for database type: {db_type}"
                    }
                    logger.warning(f"🔧 [ITERATIVE_METADATA] Unsupported database type: {db_type}")
                    
            except Exception as e:
                adapter_status[source_id] = {
                    "status": "error",
                    "error": str(e)
                }
                logger.error(f"🔧 [ITERATIVE_METADATA] Failed to initialize adapter for {source_id}: {e}")
        
        return adapter_status
    
    async def _test_connections_parallel(
        self,
        sources_to_process: List[Dict[str, Any]]
    ) -> Dict[str, bool]:
        """
        Test database connections in parallel for performance.
        
        Args:
            sources_to_process: Sources to test connections for
            
        Returns:
            Connection test results
        """
        connection_results = {}
        
        async def test_single_connection(source: Dict[str, Any]) -> tuple:
            source_id = source.get("id")
            try:
                if source_id in self.active_adapters:
                    adapter = self.active_adapters[source_id]
                    is_connected = await adapter.test_connection()
                    logger.info(f"🔧 [ITERATIVE_METADATA] Connection test for {source_id}: {'SUCCESS' if is_connected else 'FAILED'}")
                    return source_id, is_connected
                else:
                    logger.warning(f"🔧 [ITERATIVE_METADATA] No adapter found for {source_id}")
                    return source_id, False
            except Exception as e:
                logger.error(f"🔧 [ITERATIVE_METADATA] Connection test failed for {source_id}: {e}")
                self.performance_stats["failed_connections"] += 1
                return source_id, False
        
        # Run connection tests in parallel
        tasks = [test_single_connection(source) for source in sources_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, tuple):
                source_id, is_connected = result
                connection_results[source_id] = is_connected
            else:
                logger.error(f"🔧 [ITERATIVE_METADATA] Unexpected connection test result: {result}")
        
        successful_connections = sum(1 for connected in connection_results.values() if connected)
        logger.info(f"🔧 [ITERATIVE_METADATA] Connection tests completed: {successful_connections}/{len(sources_to_process)} successful")
        
        return connection_results
    
    async def _collect_metadata_iteratively(
        self,
        sources_to_process: List[Dict[str, Any]],
        connection_results: Dict[str, bool],
        session_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Collect metadata iteratively with progress updates.
        
        Args:
            sources_to_process: Sources to collect metadata from
            connection_results: Connection test results
            session_id: Current session ID
            
        Yields:
            Progress updates and results
        """
        metadata_results = {}
        total_sources = len([s for s in sources_to_process 
                           if connection_results.get(s.get("id"), False)])
        processed = 0
        
        for source in sources_to_process:
            source_id = source.get("id")
            
            if not connection_results.get(source_id, False):
                logger.warning(f"🔧 [ITERATIVE_METADATA] Skipping {source_id} - connection failed")
                continue
            
            yield {
                "type": "progress",
                "progress": (processed / total_sources) * 100 if total_sources > 0 else 0,
                "operation": f"Collecting metadata from {source_id}",
                "current_source": source_id,
                "processed": processed,
                "total": total_sources
            }
            
            try:
                logger.info(f"🔧 [ITERATIVE_METADATA] Collecting metadata from {source_id}")
                start_time = time.time()
                
                adapter = self.active_adapters[source_id]
                schema_metadata = await adapter.introspect_schema()
                
                collection_time = time.time() - start_time
                
                # Process and structure the metadata
                processed_metadata = {
                    "source_id": source_id,
                    "database_type": source.get("type"),
                    "schema_metadata": schema_metadata,
                    "collection_time": collection_time,
                    "table_count": len(schema_metadata),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                metadata_results[source_id] = processed_metadata
                
                # Mark as initialized for this session
                self.initialized_sources[session_id].add(source_id)
                
                self.performance_stats["schema_discoveries"] += 1
                logger.info(f"🔧 [ITERATIVE_METADATA] Collected metadata from {source_id}: {len(schema_metadata)} tables in {collection_time:.2f}s")
                
                processed += 1
                
            except Exception as e:
                logger.error(f"🔧 [ITERATIVE_METADATA] Failed to collect metadata from {source_id}: {e}")
                metadata_results[source_id] = {
                    "source_id": source_id,
                    "error": str(e),
                    "collection_failed": True
                }
        
        yield {
            "type": "result",
            "data": metadata_results,
            "summary": {
                "total_sources": total_sources,
                "successful": len([r for r in metadata_results.values() if not r.get("collection_failed", False)]),
                "failed": len([r for r in metadata_results.values() if r.get("collection_failed", False)])
            }
        }
    
    async def _process_and_optimize_metadata(
        self,
        metadata_results: Dict[str, Dict[str, Any]],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Process and optimize collected metadata for query generation.
        
        Args:
            metadata_results: Raw metadata collection results
            session_id: Current session ID
            
        Returns:
            Optimized metadata structure
        """
        logger.info(f"🔧 [ITERATIVE_METADATA] Processing and optimizing metadata for {len(metadata_results)} sources")
        
        optimized_metadata = {
            "sources": {},
            "global_schema": {
                "all_tables": [],
                "table_relationships": {},
                "common_patterns": {},
                "cross_database_opportunities": []
            },
            "query_optimization": {
                "recommended_joins": [],
                "performance_hints": [],
                "indexing_suggestions": []
            }
        }
        
        all_tables = []
        
        # Process each source's metadata
        for source_id, source_metadata in metadata_results.items():
            if source_metadata.get("collection_failed"):
                continue
                
            schema_metadata = source_metadata.get("schema_metadata", [])
            database_type = source_metadata.get("database_type")
            
            # Structure source-specific metadata
            optimized_metadata["sources"][source_id] = {
                "database_type": database_type,
                "tables": [],
                "key_tables": [],
                "searchable_columns": [],
                "performance_characteristics": {
                    "collection_time": source_metadata.get("collection_time", 0),
                    "table_count": len(schema_metadata),
                    "estimated_query_performance": "fast" if len(schema_metadata) < 50 else "moderate"
                }
            }
            
            # Process each table
            for table_info in schema_metadata:
                table_name = table_info.get("id", "unknown_table")
                table_content = table_info.get("content", "")
                
                table_entry = {
                    "name": table_name,
                    "source_id": source_id,
                    "database_type": database_type,
                    "schema_info": table_content,
                    "searchable": self._is_table_searchable(table_content),
                    "estimated_size": self._estimate_table_size(table_content)
                }
                
                optimized_metadata["sources"][source_id]["tables"].append(table_entry)
                all_tables.append(table_entry)
                
                # Identify key tables
                if self._is_key_table(table_name, table_content):
                    optimized_metadata["sources"][source_id]["key_tables"].append(table_name)
        
        # Global analysis
        optimized_metadata["global_schema"]["all_tables"] = all_tables
        optimized_metadata["global_schema"]["table_relationships"] = self._analyze_table_relationships(all_tables)
        optimized_metadata["global_schema"]["common_patterns"] = self._identify_common_patterns(all_tables)
        
        # Cross-database optimization opportunities
        if len(metadata_results) > 1:
            optimized_metadata["global_schema"]["cross_database_opportunities"] = \
                self._identify_cross_database_opportunities(all_tables)
        
        logger.info(f"🔧 [ITERATIVE_METADATA] Metadata optimization completed: {len(all_tables)} total tables processed")
        
        return optimized_metadata
    
    def _is_table_searchable(self, table_content: str) -> bool:
        """Determine if a table is suitable for text search."""
        searchable_indicators = ["text", "varchar", "char", "string", "description", "name", "title"]
        return any(indicator in table_content.lower() for indicator in searchable_indicators)
    
    def _estimate_table_size(self, table_content: str) -> str:
        """Estimate table size based on schema information."""
        if "primary key" in table_content.lower() or "id" in table_content.lower():
            return "large" if len(table_content) > 500 else "medium"
        return "small"
    
    def _is_key_table(self, table_name: str, table_content: str) -> bool:
        """Identify if this is a key table for queries."""
        key_indicators = ["user", "customer", "order", "product", "transaction", "main", "primary"]
        table_name_lower = table_name.lower()
        return any(indicator in table_name_lower for indicator in key_indicators)
    
    def _analyze_table_relationships(self, all_tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze potential relationships between tables."""
        relationships = {
            "potential_joins": [],
            "foreign_key_candidates": [],
            "naming_patterns": {}
        }
        
        # Simple relationship analysis based on column names
        for i, table1 in enumerate(all_tables):
            for j, table2 in enumerate(all_tables[i+1:], i+1):
                # Look for common column patterns
                if self._tables_likely_related(table1, table2):
                    relationships["potential_joins"].append({
                        "table1": table1["name"],
                        "table2": table2["name"],
                        "confidence": "medium",
                        "suggested_join": "id-based"
                    })
        
        return relationships
    
    def _tables_likely_related(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> bool:
        """Determine if two tables are likely related."""
        # Simple heuristic based on table names and content
        content1 = table1.get("schema_info", "").lower()
        content2 = table2.get("schema_info", "").lower()
        
        # Look for common patterns like "user_id", "customer_id", etc.
        common_patterns = ["id", "user", "customer", "order"]
        
        for pattern in common_patterns:
            if pattern in content1 and pattern in content2:
                return True
        
        return False
    
    def _identify_common_patterns(self, all_tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify common patterns across tables."""
        patterns = {
            "common_columns": {},
            "data_types": {},
            "naming_conventions": []
        }
        
        # Analyze column names across tables
        all_columns = []
        for table in all_tables:
            schema_info = table.get("schema_info", "")
            # Extract column-like patterns (simplified)
            import re
            columns = re.findall(r'\b(\w+):\s*(\w+)', schema_info)
            all_columns.extend(columns)
        
        # Count common column names
        from collections import Counter
        column_counts = Counter([col[0] for col in all_columns])
        patterns["common_columns"] = dict(column_counts.most_common(10))
        
        return patterns
    
    def _identify_cross_database_opportunities(self, all_tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify opportunities for cross-database queries."""
        opportunities = []
        
        # Group tables by database type
        by_db_type = {}
        for table in all_tables:
            db_type = table.get("database_type", "unknown")
            if db_type not in by_db_type:
                by_db_type[db_type] = []
            by_db_type[db_type].append(table)
        
        # Look for complementary data across database types
        if len(by_db_type) > 1:
            opportunities.append({
                "type": "data_enrichment",
                "description": f"Combine data from {list(by_db_type.keys())}",
                "databases_involved": list(by_db_type.keys()),
                "confidence": "medium"
            })
        
        return opportunities
    
    async def _update_caches(
        self,
        session_id: str,
        optimized_metadata: Dict[str, Any],
        sources_processed: List[Dict[str, Any]]
    ):
        """Update various caches with the collected metadata."""
        logger.info(f"🔧 [ITERATIVE_METADATA] Updating caches for session {session_id}")
        
        # Update session metadata
        self.session_metadata[session_id]["metadata_collected"] = optimized_metadata
        self.session_metadata[session_id]["last_update"] = time.time()
        
        # Update global metadata cache
        cache_key = f"{session_id}_metadata"
        self.metadata_cache[cache_key] = optimized_metadata
        
        # Update schema cache for each source
        for source in sources_processed:
            source_id = source.get("id")
            if source_id in optimized_metadata.get("sources", {}):
                source_metadata = optimized_metadata["sources"][source_id]
                self.schema_cache[source_id] = source_metadata.get("tables", [])
    
    async def _prepare_final_result(
        self,
        optimized_metadata: Dict[str, Any],
        adapter_status: Dict[str, Dict[str, Any]],
        connection_results: Dict[str, bool],
        start_time: float,
        session_id: str
    ) -> Dict[str, Any]:
        """Prepare the comprehensive final result."""
        execution_time = time.time() - start_time
        
        # Extract key information for state updates
        all_tables = optimized_metadata.get("global_schema", {}).get("all_tables", [])
        successful_sources = len([s for s, status in adapter_status.items() 
                                if status.get("status") == "initialized" and connection_results.get(s, False)])
        
        final_result = {
            "schema_metadata": optimized_metadata,
            "available_tables": all_tables,
            "adapter_integration": {
                "adapters_initialized": len(adapter_status),
                "successful_connections": sum(connection_results.values()),
                "active_adapters": list(self.active_adapters.keys()),
                "adapter_status": adapter_status
            },
            "performance_metrics": {
                "execution_time": execution_time,
                "sources_processed": successful_sources,
                "total_tables_discovered": len(all_tables),
                "cache_efficiency": {
                    "hits": self.performance_stats["cache_hits"],
                    "misses": self.performance_stats["cache_misses"],
                    "hit_rate": self.performance_stats["cache_hits"] / 
                              max(1, self.performance_stats["cache_hits"] + self.performance_stats["cache_misses"])
                }
            },
            "iterative_features": {
                "session_tracking_enabled": True,
                "initialized_sources": list(self.initialized_sources.get(session_id, set())),
                "prevents_reinitialization": True,
                "supports_dynamic_expansion": True
            },
            "query_optimization_ready": {
                "cross_database_opportunities": len(optimized_metadata.get("global_schema", {})
                                                   .get("cross_database_opportunities", [])),
                "recommended_joins": len(optimized_metadata.get("query_optimization", {})
                                        .get("recommended_joins", [])),
                "performance_hints_available": True
            }
        }
        
        logger.info(f"🔧 [ITERATIVE_METADATA] Final result prepared: {len(all_tables)} tables, "
                   f"{successful_sources} sources, {execution_time:.2f}s execution time")
        
        return final_result
    
    def _get_cached_metadata(
        self,
        session_id: str,
        classification_sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Retrieve cached metadata for the session."""
        cache_key = f"{session_id}_metadata"
        cached_data = self.metadata_cache.get(cache_key, {})
        
        if cached_data:
            logger.info(f"🔧 [ITERATIVE_METADATA] Retrieved cached metadata for session {session_id}")
            # Add cache metadata
            cached_data["cache_info"] = {
                "cached": True,
                "cache_key": cache_key,
                "sources_requested": [s.get("id") for s in classification_sources],
                "cache_timestamp": self.session_metadata.get(session_id, {}).get("last_update")
            }
        
        return cached_data
    
    async def __call__(self, state: LangGraphState, **kwargs) -> LangGraphState:
        """
        Non-streaming execution of iterative metadata collection.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Returns:
            Updated LangGraph state with metadata
        """
        logger.info("🔧 [ITERATIVE_METADATA] Starting non-streaming iterative metadata collection")
        
        # Collect results from streaming execution
        final_result = None
        final_state_update = {}
        
        async for chunk in self.stream(state, **kwargs):
            if chunk.get("is_final", False):
                final_result = chunk.get("result_data", {})
                final_state_update = chunk.get("state_update", {})
                break
        
        if final_result or final_state_update:
            # Ensure we have schema metadata even if empty
            if "schema_metadata" not in final_state_update:
                final_state_update["schema_metadata"] = final_result.get("schema_metadata", {}) if final_result else {}
            
            if "available_tables" not in final_state_update:
                final_state_update["available_tables"] = final_result.get("available_tables", []) if final_result else []
            
            # Track initialized sources to prevent re-initialization
            session_id = state.get("session_id", "default")
            
            # Get sources that were processed from the result
            adapter_integration = final_result.get("adapter_integration", {}) if final_result else {}
            active_adapters = adapter_integration.get("active_adapters", [])
            
            # Update initialized sources tracking
            if session_id not in self.initialized_sources:
                self.initialized_sources[session_id] = set()
            
            for adapter_id in active_adapters:
                self.initialized_sources[session_id].add(adapter_id)
            
            # Update state with comprehensive metadata
            state.update(final_state_update)
            state["iterative_metadata_completed"] = True
            state["metadata_collection_method"] = "iterative_enhanced"
            state["metadata_sources_initialized"] = list(self.initialized_sources.get(session_id, set()))
            
            # Pass initialized adapters to state for execution node
            state["available_adapters"] = dict(self.active_adapters)
            state["adapter_registry"] = dict(self.adapter_registry)
            
            logger.info(f"🔧 [ITERATIVE_METADATA] Successfully updated state with {len(final_state_update.get('available_tables', []))} tables")
            logger.info(f"🔧 [ITERATIVE_METADATA] Passed {len(self.active_adapters)} active adapters to state")
        else:
            logger.error("🔧 [ITERATIVE_METADATA] No final result received from streaming execution")
            state.update({
                "iterative_metadata_error": "No final result received",
                "schema_metadata": {},
                "available_tables": [],
                "iterative_metadata_completed": True
            })
        
        return state
    
    def get_node_capabilities(self) -> Dict[str, Any]:
        """Get capabilities and status of this node."""
        return {
            "node_type": "iterative_metadata",
            "features": [
                "dynamic_adapter_integration",
                "intelligent_caching",
                "session_based_tracking",
                "parallel_processing",
                "real_time_streaming",
                "cross_database_optimization"
            ],
            "supported_databases": list(self.adapter_registry.keys()),
            "active_adapters": len(self.active_adapters),
            "performance_stats": self.performance_stats,
            "cache_status": {
                "metadata_cache_entries": len(self.metadata_cache),
                "schema_cache_entries": len(self.schema_cache),
                "active_sessions": len(self.session_metadata)
            }
        }
    
    def cleanup_session(self, session_id: str):
        """Clean up resources for a completed session."""
        logger.info(f"🔧 [ITERATIVE_METADATA] Cleaning up session: {session_id}")
        
        # Remove session tracking
        self.session_metadata.pop(session_id, None)
        self.initialized_sources.pop(session_id, None)
        
        # Clean up cache entries for this session
        cache_keys_to_remove = [key for key in self.metadata_cache.keys() 
                               if key.startswith(f"{session_id}_")]
        
        for key in cache_keys_to_remove:
            self.metadata_cache.pop(key, None)
        
        logger.info(f"🔧 [ITERATIVE_METADATA] Session cleanup completed: {session_id}") 