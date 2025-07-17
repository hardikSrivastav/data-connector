"""
Metadata Collection Node for LangGraph Integration

Provides efficient metadata collection and caching for LangGraph workflows,
optimizing schema discovery and database introspection.
"""

import logging
import time
from typing import Dict, List, Any, Optional, AsyncIterator

from ..state import LangGraphState
from ..streaming import StreamingNodeBase
# Import registry functions instead of non-existent SchemaRegistry class
from ...db.registry import get_table_schema, list_tables, search_schema_content
from ...llm.client import get_llm_client

logger = logging.getLogger(__name__)

class MetadataCollectionNode(StreamingNodeBase):
    """
    LangGraph node for collecting and managing database metadata.
    
    Features:
    - Efficient schema discovery across multiple databases
    - Intelligent caching and optimization
    - Real-time progress reporting
    - Error handling and fallbacks
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("metadata_collection")
        
        # Use registry functions directly instead of SchemaRegistry class
        self.registry_available = True
        self.llm_client = get_llm_client()
        self.config = config or {}
        
        # Metadata collection settings
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.parallel_discovery = self.config.get("parallel_discovery", True)
        self.max_concurrent_connections = self.config.get("max_concurrent_connections", 5)
        
        logger.info("Initialized MetadataCollectionNode with schema registry integration")
    
    async def stream(
        self,
        state: LangGraphState,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Collect metadata with streaming progress updates.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Yields:
            Streaming chunks with metadata collection progress
        """
        databases_identified = state.get("databases_identified", [])
        session_id = state["session_id"]
        
        if not databases_identified:
            yield self.create_result_chunk(
                {"warning": "No databases identified for metadata collection"},
                {"schema_metadata": {}, "available_tables": []},
                is_final=True
            )
            return
        
        try:
            # Step 1: Initialize metadata collection
            yield self.create_progress_chunk(
                10.0,
                "Initializing metadata collection",
                {
                    "current_step": 1,
                    "total_steps": 4,
                    "databases_to_scan": databases_identified
                }
            )
            
            all_metadata = {}
            all_tables = []
            
            # Step 2: Collect metadata from each database
            for i, db_type in enumerate(databases_identified):
                db_progress_start = 20.0 + (i / len(databases_identified)) * 50.0
                db_progress_end = 20.0 + ((i + 1) / len(databases_identified)) * 50.0
                
                yield self.create_progress_chunk(
                    db_progress_start,
                    f"Collecting metadata from {db_type}",
                    {
                        "current_step": 2,
                        "current_database": db_type,
                        "database_index": i + 1,
                        "total_databases": len(databases_identified)
                    }
                )
                
                start_time = time.time()
                
                try:
                    # Collect metadata for this database
                    db_metadata = await self._collect_database_metadata(db_type, session_id)
                    collection_time = time.time() - start_time
                    
                    all_metadata[db_type] = db_metadata
                    
                    # Extract table information
                    tables = db_metadata.get("tables", [])
                    for table in tables:
                        table["database_type"] = db_type
                        all_tables.append(table)
                    
                    yield self.create_progress_chunk(
                        db_progress_end,
                        f"Metadata collected from {db_type}",
                        {
                            "schema_metadata": {db_type: db_metadata},
                            "performance_metrics": {
                                f"{db_type}_collection_time": collection_time
                            }
                        },
                        {
                            "database": db_type,
                            "tables_found": len(tables),
                            "collection_time": collection_time
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to collect metadata from {db_type}: {e}")
                    all_metadata[db_type] = {
                        "error": str(e),
                        "tables": [],
                        "status": "failed"
                    }
                    
                    yield self.create_progress_chunk(
                        db_progress_end,
                        f"Failed to collect metadata from {db_type}",
                        {
                            "error_history": [{
                                "database": db_type,
                                "error": str(e),
                                "timestamp": time.time()
                            }]
                        },
                        {
                            "database": db_type,
                            "error": str(e),
                            "status": "failed"
                        }
                    )
            
            # Step 3: Process and optimize metadata
            yield self.create_progress_chunk(
                75.0,
                "Processing and optimizing metadata",
                {"current_step": 3}
            )
            
            start_time = time.time()
            
            # Optimize metadata for query generation
            optimized_metadata = await self._optimize_metadata(all_metadata)
            
            # Generate table relationships and suggestions
            table_relationships = await self._analyze_table_relationships(all_tables)
            
            processing_time = time.time() - start_time
            
            # Step 4: Cache metadata for future use
            yield self.create_progress_chunk(
                90.0,
                "Caching metadata for future use",
                {"current_step": 4}
            )
            
            if self.cache_enabled:
                await self._cache_metadata(session_id, optimized_metadata, all_tables)
            
            # Final result
            yield self.create_result_chunk(
                {
                    "schema_metadata": optimized_metadata,
                    "available_tables": all_tables,
                    "table_relationships": table_relationships,
                    "metadata_summary": {
                        "total_databases": len(databases_identified),
                        "total_tables": len(all_tables),
                        "successful_databases": len([db for db, meta in all_metadata.items() if "error" not in meta]),
                        "failed_databases": len([db for db, meta in all_metadata.items() if "error" in meta])
                    }
                },
                {
                    "schema_metadata": optimized_metadata,
                    "available_tables": all_tables,
                    "current_step": 4,
                    "total_steps": 4,
                    "performance_metrics": {
                        "total_metadata_time": sum(
                            meta.get("collection_time", 0) 
                            for meta in all_metadata.values() 
                            if isinstance(meta, dict)
                        ) + processing_time,
                        "processing_time": processing_time,
                        "databases_processed": len(all_metadata)
                    }
                },
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error in metadata collection node: {e}")
            yield self.create_result_chunk(
                {"error": str(e), "node": "metadata_collection"},
                {
                    "error_history": [{
                        "timestamp": time.time(),
                        "error": str(e),
                        "node": "metadata_collection"
                    }]
                },
                is_final=True
            )
            raise
    
    async def _collect_database_metadata(
        self,
        db_type: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Collect metadata from a specific database type.
        
        Args:
            db_type: Type of database (postgres, mongodb, etc.)
            session_id: Session ID for tracking
            
        Returns:
            Database metadata dictionary
        """
        start_time = time.time()
        
        try:
            # Use schema registry for metadata collection
            metadata = await self.schema_registry.get_database_schema(db_type)
            
            if metadata:
                # Enhance metadata with additional information
                enhanced_metadata = {
                    **metadata,
                    "collection_time": time.time() - start_time,
                    "status": "success",
                    "database_type": db_type,
                    "session_id": session_id
                }
                
                # Add table count and column statistics
                tables = enhanced_metadata.get("tables", [])
                enhanced_metadata["statistics"] = {
                    "table_count": len(tables),
                    "total_columns": sum(len(table.get("columns", [])) for table in tables),
                    "average_columns_per_table": (
                        sum(len(table.get("columns", [])) for table in tables) / len(tables)
                        if tables else 0
                    )
                }
                
                return enhanced_metadata
            else:
                return {
                    "error": f"No metadata available for {db_type}",
                    "tables": [],
                    "status": "no_data",
                    "collection_time": time.time() - start_time
                }
                
        except Exception as e:
            logger.error(f"Error collecting metadata for {db_type}: {e}")
            return {
                "error": str(e),
                "tables": [],
                "status": "error",
                "collection_time": time.time() - start_time
            }
    
    async def _optimize_metadata(
        self,
        all_metadata: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Optimize metadata for efficient query generation.
        
        Args:
            all_metadata: Raw metadata from all databases
            
        Returns:
            Optimized metadata structure
        """
        optimized = {
            "databases": {},
            "global_tables": [],
            "common_patterns": {},
            "optimization_notes": []
        }
        
        for db_type, metadata in all_metadata.items():
            if "error" in metadata:
                optimized["databases"][db_type] = metadata
                continue
            
            # Extract key information for optimization
            tables = metadata.get("tables", [])
            
            # Create optimized database entry
            optimized["databases"][db_type] = {
                "status": metadata.get("status", "unknown"),
                "table_count": len(tables),
                "key_tables": self._identify_key_tables(tables),
                "column_types": self._analyze_column_types(tables),
                "indexing_info": self._extract_indexing_info(tables)
            }
            
            # Add to global tables list
            for table in tables:
                optimized["global_tables"].append({
                    "name": table.get("name"),
                    "database": db_type,
                    "column_count": len(table.get("columns", [])),
                    "primary_key": self._find_primary_key(table),
                    "searchable_columns": self._find_searchable_columns(table)
                })
        
        # Identify common patterns across databases
        optimized["common_patterns"] = self._identify_common_patterns(optimized["global_tables"])
        
        return optimized
    
    def _identify_key_tables(self, tables: List[Dict[str, Any]]) -> List[str]:
        """Identify the most important tables based on naming patterns and structure."""
        key_patterns = ["user", "customer", "order", "product", "transaction", "main", "core"]
        key_tables = []
        
        for table in tables:
            table_name = table.get("name", "").lower()
            if any(pattern in table_name for pattern in key_patterns):
                key_tables.append(table.get("name"))
        
        return key_tables[:10]  # Limit to top 10
    
    def _analyze_column_types(self, tables: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze distribution of column types across tables."""
        type_counts = {}
        
        for table in tables:
            for column in table.get("columns", []):
                col_type = column.get("type", "unknown")
                type_counts[col_type] = type_counts.get(col_type, 0) + 1
        
        return type_counts
    
    def _extract_indexing_info(self, tables: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Extract indexing information from tables."""
        indexes = {}
        
        for table in tables:
            table_name = table.get("name")
            table_indexes = []
            
            for column in table.get("columns", []):
                if column.get("indexed", False) or column.get("primary_key", False):
                    table_indexes.append(column.get("name"))
            
            if table_indexes:
                indexes[table_name] = table_indexes
        
        return indexes
    
    def _find_primary_key(self, table: Dict[str, Any]) -> Optional[str]:
        """Find the primary key column of a table."""
        for column in table.get("columns", []):
            if column.get("primary_key", False):
                return column.get("name")
        return None
    
    def _find_searchable_columns(self, table: Dict[str, Any]) -> List[str]:
        """Find columns that are good for searching (text, indexed, etc.)."""
        searchable = []
        
        for column in table.get("columns", []):
            col_type = column.get("type", "").lower()
            is_indexed = column.get("indexed", False)
            
            # Text columns and indexed columns are generally searchable
            if "text" in col_type or "varchar" in col_type or "string" in col_type or is_indexed:
                searchable.append(column.get("name"))
        
        return searchable
    
    def _identify_common_patterns(self, global_tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify common patterns across all tables."""
        patterns = {
            "common_table_names": {},
            "common_column_patterns": {},
            "cross_database_relationships": []
        }
        
        # Count table name occurrences
        for table in global_tables:
            name = table["name"]
            patterns["common_table_names"][name] = patterns["common_table_names"].get(name, 0) + 1
        
        # Identify potential cross-database relationships (tables with similar names)
        table_by_db = {}
        for table in global_tables:
            db = table["database"]
            if db not in table_by_db:
                table_by_db[db] = []
            table_by_db[db].append(table)
        
        # Find similar table names across databases
        for db1, tables1 in table_by_db.items():
            for db2, tables2 in table_by_db.items():
                if db1 >= db2:  # Avoid duplicates
                    continue
                
                for t1 in tables1:
                    for t2 in tables2:
                        if t1["name"].lower() == t2["name"].lower():
                            patterns["cross_database_relationships"].append({
                                "table_name": t1["name"],
                                "database1": db1,
                                "database2": db2,
                                "potential_join": True
                            })
        
        return patterns
    
    async def _analyze_table_relationships(
        self,
        all_tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze potential relationships between tables."""
        relationships = {
            "potential_joins": [],
            "foreign_key_candidates": [],
            "common_columns": {}
        }
        
        # Group tables by database
        db_tables = {}
        for table in all_tables:
            db = table["database_type"]
            if db not in db_tables:
                db_tables[db] = []
            db_tables[db].append(table)
        
        # Analyze relationships within each database
        for db, tables in db_tables.items():
            db_relationships = await self._analyze_intra_db_relationships(tables)
            relationships["potential_joins"].extend(db_relationships.get("joins", []))
            relationships["foreign_key_candidates"].extend(db_relationships.get("foreign_keys", []))
        
        return relationships
    
    async def _analyze_intra_db_relationships(
        self,
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze relationships within a single database."""
        joins = []
        foreign_keys = []
        
        for i, table1 in enumerate(tables):
            for j, table2 in enumerate(tables[i+1:], i+1):
                # Look for common column names that might indicate relationships
                table1_columns = {col["name"].lower() for col in table1.get("columns", [])}
                table2_columns = {col["name"].lower() for col in table2.get("columns", [])}
                
                common_columns = table1_columns.intersection(table2_columns)
                
                if common_columns:
                    joins.append({
                        "table1": table1["name"],
                        "table2": table2["name"],
                        "common_columns": list(common_columns),
                        "confidence": len(common_columns) / min(len(table1_columns), len(table2_columns))
                    })
        
        return {"joins": joins, "foreign_keys": foreign_keys}
    
    async def _cache_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any],
        tables: List[Dict[str, Any]]
    ):
        """Cache metadata for future use."""
        try:
            # Use schema registry for caching
            await self.schema_registry.cache_session_metadata(session_id, metadata, tables)
            logger.info(f"Cached metadata for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to cache metadata: {e}")
    
    async def __call__(
        self,
        state: LangGraphState,
        **kwargs
    ) -> LangGraphState:
        """
        Execute metadata collection and update state.
        
        Args:
            state: Current LangGraph state
            **kwargs: Additional execution parameters
            
        Returns:
            Updated LangGraph state
        """
        # Collect all streaming results
        final_result = None
        async for chunk in self.stream(state, **kwargs):
            if chunk.get("is_final") and chunk.get("type") == "result":
                final_result = chunk["result_data"]
            
            # Apply state updates
            if "state_update" in chunk:
                state.update(chunk["state_update"])
        
        # Ensure we have a result
        if final_result is None:
            # Fallback to direct execution if streaming failed
            logger.warning("Streaming failed, falling back to direct execution")
            final_result = await self._execute_direct(state)
        
        # Update final state
        if "error" not in final_result:
            state["schema_metadata"] = final_result.get("schema_metadata", {})
            state["available_tables"] = final_result.get("available_tables", [])
        
        return state
    
    async def _execute_direct(self, state: LangGraphState) -> Dict[str, Any]:
        """Direct execution fallback without streaming."""
        try:
            databases_identified = state.get("databases_identified", [])
            session_id = state["session_id"]
            
            all_metadata = {}
            all_tables = []
            
            for db_type in databases_identified:
                db_metadata = await self._collect_database_metadata(db_type, session_id)
                all_metadata[db_type] = db_metadata
                
                tables = db_metadata.get("tables", [])
                for table in tables:
                    table["database_type"] = db_type
                    all_tables.append(table)
            
            optimized_metadata = await self._optimize_metadata(all_metadata)
            table_relationships = await self._analyze_table_relationships(all_tables)
            
            return {
                "schema_metadata": optimized_metadata,
                "available_tables": all_tables,
                "table_relationships": table_relationships
            }
            
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return {"error": str(e), "node": "metadata_collection"}
    
    def get_metadata_capabilities(self) -> Dict[str, Any]:
        """Get information about metadata collection capabilities."""
        return {
            "supported_databases": ["postgres", "mongodb", "qdrant", "slack", "shopify"],
            "caching_enabled": self.cache_enabled,
            "parallel_discovery": self.parallel_discovery,
            "max_concurrent_connections": self.max_concurrent_connections,
            "relationship_analysis": True,
            "optimization": True,
            "streaming_enabled": True
        } 