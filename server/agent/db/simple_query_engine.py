"""
Simple Registry Query Engine

A simplified query engine that bypasses the plan-execution mechanism and 
directly executes queries through adapters. Suitable for independent 
multi-database queries without complex cross-DB joins or dependencies.

Features:
- Direct adapter execution (no planning overhead)
- Parallel query execution across multiple databases
- Simple result merging (concatenation)
- Registry-based database discovery
- Classifier-based database selection

Limitations:
- No cross-database joins
- No operation dependencies
- No complex aggregations across databases
- Simple result merging only
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from .classifier import classifier as db_classifier
from .registry.integrations import registry_client
from .db_orchestrator import Orchestrator
from ..llm.client import get_llm_client

# Configure logging
logger = logging.getLogger(__name__)

class SimpleRegistryQueryEngine:
    """
    Simplified query engine that executes queries directly through adapters
    without the overhead of plan generation and validation.
    
    This engine is optimized for:
    - Fast independent queries across multiple databases
    - Simple result aggregation
    - Scenarios where cross-DB joins are not required
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the simple query engine.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.classifier = db_classifier
        self.registry = registry_client
        self.llm_client = get_llm_client()
        
        # Configuration options
        self.max_parallel_queries = self.config.get("max_parallel_queries", 5)
        self.query_timeout_seconds = self.config.get("query_timeout_seconds", 60)
        
        logger.info(f"🚀 SimpleRegistryQueryEngine initialized (max_parallel: {self.max_parallel_queries})")
    
    async def execute(
        self, 
        question: str, 
        analyze: bool = False,
        db_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute a query across one or more databases.
        
        Args:
            question: Natural language question
            analyze: Whether to include LLM analysis of results
            db_types: Optional list of specific database types to query
                     (bypasses classification if provided)
        
        Returns:
            Dictionary containing:
            - question: Original question
            - databases_queried: List of database types queried
            - results: Combined results from all databases
            - individual_results: Results per database
            - execution_time: Total execution time
            - success: Whether execution succeeded
            - analysis: Optional LLM analysis (if analyze=True)
        """
        start_time = time.time()
        logger.info(f"📋 Executing simple query: {question[:100]}...")
        
        try:
            # Step 1: Get sources to query
            sources = await self._classify_and_get_sources(question, db_types)
            
            if not sources:
                logger.warning("⚠️ No data sources identified for query")
                return {
                    "question": question,
                    "databases_queried": [],
                    "results": [],
                    "individual_results": {},
                    "execution_time": time.time() - start_time,
                    "success": False,
                    "error": "No relevant data sources found for this query"
                }
            
            logger.info(f"🎯 Identified {len(sources)} source(s): {[s['id'] for s in sources]}")
            
            # Step 2: Execute queries in parallel
            individual_results = await self._execute_parallel(question, sources)
            
            # Step 3: Merge results
            merged_results = self._merge_results(individual_results)
            
            # Step 4: Optional analysis
            analysis = None
            if analyze and merged_results:
                analysis = await self._analyze_results(question, merged_results)
            
            execution_time = time.time() - start_time
            
            result = {
                "question": question,
                "databases_queried": [s['id'] for s in sources],
                "results": merged_results,
                "individual_results": individual_results,
                "execution_time": execution_time,
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
            
            if analysis:
                result["analysis"] = analysis
            
            logger.info(f"✅ Query completed successfully in {execution_time:.2f}s")
            logger.info(f"📊 Total results: {len(merged_results)} rows")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Query execution failed: {e}", exc_info=True)
            return {
                "question": question,
                "databases_queried": [],
                "results": [],
                "individual_results": {},
                "execution_time": execution_time,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _classify_and_get_sources(
        self, 
        question: str,
        explicit_db_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Classify which databases to query and get their connection info.
        
        Args:
            question: Natural language question
            explicit_db_types: Optional explicit database types (bypasses classification)
        
        Returns:
            List of source dictionaries with connection info
        """
        sources = []
        
        if explicit_db_types:
            # Explicit database types provided - find sources of these types
            logger.info(f"🎯 Using explicit database types: {explicit_db_types}")
            all_sources = self.registry.get_all_sources()
            
            for db_type in explicit_db_types:
                # Find sources of this type in registry
                matching_sources = [s for s in all_sources if s.get('type', '').lower() == db_type.lower()]
                
                if matching_sources:
                    for source in matching_sources:
                        # Get full source info including connection URI
                        source_info = self.registry.get_source_by_id(source['id'])
                        if source_info:
                            sources.append(source_info)
                            logger.info(f"✅ Found source: {source_info['id']} (type: {source_info['type']})")
                else:
                    logger.warning(f"⚠️ No sources found in registry for type: {db_type}")
        else:
            # Use classifier to determine sources
            logger.info("🔍 Classifying databases for query...")
            classification_result = await self.classifier.classify(question)
            source_ids = classification_result.get("sources", [])
            logger.info(f"🔍 Classification result: {source_ids}")
            
            if not source_ids:
                logger.warning("⚠️ No source IDs identified by classifier")
                return []
            
            # Get full source info for each source ID from classifier
            for source_id in source_ids:
                source_info = self.registry.get_source_by_id(source_id)
                if source_info:
                    sources.append(source_info)
                    logger.info(f"✅ Found source: {source_info['id']} (type: {source_info['type']})")
                else:
                    logger.warning(f"⚠️ Source not found in registry: {source_id}")
        
        return sources
    
    async def _execute_single_source(
        self, 
        question: str, 
        source: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute query on a single database source.
        
        Args:
            question: Natural language question
            source: Source information from registry
        
        Returns:
            Dictionary with results and metadata
        """
        source_id = source.get('id', 'unknown')
        db_type = source.get('type', 'unknown')
        connection_uri = source.get('connection_uri') or source.get('uri')
        
        logger.info(f"🔄 Executing query on {source_id} ({db_type})...")
        
        start_time = time.time()
        
        try:
            # Create orchestrator for this source
            orchestrator = Orchestrator(connection_uri, db_type=db_type)
            
            # Test connection
            if not await orchestrator.test_connection():
                logger.error(f"❌ Connection test failed for {source_id}")
                return {
                    "source_id": source_id,
                    "db_type": db_type,
                    "success": False,
                    "error": "Database connection failed",
                    "results": [],
                    "execution_time": time.time() - start_time
                }
            
            # Execute query with timeout
            try:
                results = await asyncio.wait_for(
                    orchestrator.run(question),
                    timeout=self.query_timeout_seconds
                )
                
                execution_time = time.time() - start_time
                
                logger.info(f"✅ {source_id}: Retrieved {len(results) if results else 0} rows in {execution_time:.2f}s")
                
                return {
                    "source_id": source_id,
                    "db_type": db_type,
                    "success": True,
                    "results": results or [],
                    "row_count": len(results) if results else 0,
                    "execution_time": execution_time
                }
                
            except asyncio.TimeoutError:
                logger.error(f"⏱️ {source_id}: Query timed out after {self.query_timeout_seconds}s")
                return {
                    "source_id": source_id,
                    "db_type": db_type,
                    "success": False,
                    "error": f"Query timeout after {self.query_timeout_seconds}s",
                    "results": [],
                    "execution_time": time.time() - start_time
                }
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ {source_id}: Query failed - {e}")
            return {
                "source_id": source_id,
                "db_type": db_type,
                "success": False,
                "error": str(e),
                "results": [],
                "execution_time": execution_time
            }
    
    async def _execute_parallel(
        self, 
        question: str, 
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute queries in parallel across multiple sources.
        
        Args:
            question: Natural language question
            sources: List of source dictionaries
        
        Returns:
            Dictionary mapping source_id to result dictionary
        """
        logger.info(f"⚡ Executing {len(sources)} queries in parallel...")
        
        # Create tasks for parallel execution
        tasks = [
            self._execute_single_source(question, source)
            for source in sources
        ]
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dictionary
        individual_results = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ Task failed with exception: {result}")
                continue
            
            source_id = result.get('source_id', 'unknown')
            individual_results[source_id] = result
        
        return individual_results
    
    def _merge_results(self, individual_results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge results from multiple databases into a single list.
        
        This is a simple concatenation strategy. For more sophisticated
        merging (joins, deduplication), use the full plan-execution system.
        
        Args:
            individual_results: Dictionary of results per source
        
        Returns:
            Combined list of result dictionaries
        """
        merged = []
        
        for source_id, result_data in individual_results.items():
            if result_data.get('success') and result_data.get('results'):
                results = result_data['results']
                
                # Add source metadata to each result row
                for row in results:
                    if isinstance(row, dict):
                        row['_source_id'] = source_id
                        row['_source_type'] = result_data.get('db_type')
                
                merged.extend(results)
        
        logger.info(f"📊 Merged {len(merged)} total rows from {len(individual_results)} sources")
        return merged
    
    async def _analyze_results(self, question: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate LLM analysis of query results.
        
        Args:
            question: Original question
            results: Query results
        
        Returns:
            Analysis text
        """
        logger.info("🤖 Generating LLM analysis of results...")
        
        try:
            # Prepare result summary for LLM
            result_summary = {
                "total_rows": len(results),
                "sample_data": results[:5] if len(results) > 5 else results,
                "sources": list(set(r.get('_source_type') for r in results if '_source_type' in r))
            }
            
            prompt = f"""Analyze the following query results and provide insights.

Question: {question}

Results Summary:
- Total rows: {result_summary['total_rows']}
- Data sources: {', '.join(result_summary['sources'])}
- Sample data: {result_summary['sample_data']}

Provide a concise analysis of what the data shows in relation to the question.
Focus on key insights, patterns, and anomalies.
"""
            
            # Generate analysis using LLM
            if hasattr(self.llm_client, 'client') and hasattr(self.llm_client.client, 'chat'):
                # OpenAI-style client
                response = await self.llm_client.client.chat.completions.create(
                    model=self.llm_client.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500
                )
                analysis = response.choices[0].message.content
            else:
                # Fallback for other client types
                analysis = "Analysis not available - LLM client not configured"
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Analysis generation failed: {e}")
            return f"Analysis failed: {str(e)}"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get information about engine capabilities.
        
        Returns:
            Dictionary describing what the engine can and cannot do
        """
        return {
            "name": "SimpleRegistryQueryEngine",
            "description": "Direct adapter-based query execution without planning overhead",
            "capabilities": {
                "parallel_queries": True,
                "multi_database": True,
                "simple_merging": True,
                "timeout_handling": True,
                "connection_testing": True,
                "llm_analysis": True
            },
            "limitations": {
                "cross_db_joins": False,
                "operation_dependencies": False,
                "complex_aggregations": False,
                "result_transformations": False,
                "adaptive_parallelism": False
            },
            "configuration": {
                "max_parallel_queries": self.max_parallel_queries,
                "query_timeout_seconds": self.query_timeout_seconds
            }
        }

