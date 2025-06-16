"""
Database Classifier Module

This module determines which databases should be queried for a given natural language question.
It uses the Schema Registry to analyze database metadata and make intelligent decisions.
"""
import logging
import os
import yaml
from typing import List, Set, Dict, Any, Tuple
import re
from pathlib import Path

# Import the schema registry client
from .registry.integrations import registry_client

# Import schema searcher
from ..meta.ingest import SchemaSearcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseClassifier:
    """
    Classifier that determines which databases should be queried for a given question.
    
    This is a rule-based implementation that uses the schema registry.
    It can be extended with more sophisticated ML/LLM techniques in the future.
    """
    
    def __init__(self):
        """Initialize the classifier"""
        # Make sure the registry client is initialized
        self.client = registry_client
        
        # Initialize the schema searcher for FAISS access
        self.schema_searcher = SchemaSearcher()
        
        # Load database types from config.yaml
        self.db_types = self._load_database_types()
        
        # Define default keywords for standard database types
        self.default_keywords = {
            "postgres": ["table", "row", "sql", "query", "join", "database", "relational"],
            "mongodb": ["document", "collection", "json", "nosql", "unstructured"],
            "qdrant": ["similar", "vector", "embedding", "semantic", "similarity", "neural"],
            "slack": ["message", "channel", "chat", "conversation", "slack", "communication"],
            "shopify": ["order", "product", "customer", "inventory", "checkout", "cart", "purchase", "sale", "revenue", "ecommerce", "e-commerce", "shopify", "store", "merchant", "variant", "fulfillment", "shipping", "billing", "payment", "discount", "coupon", "abandoned cart"],
        }
        
        # Extend with keywords for any new database types from config
        self._extend_keywords()
    
    def _load_database_types(self) -> List[str]:
        """
        Load database types from config.yaml
        
        Returns:
            List of database types defined in the config
        """
        config_path = os.environ.get("DATA_CONNECTOR_CONFIG", 
                                    str(Path.home() / ".data-connector" / "config.yaml"))
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Get all database types from config.yaml
            db_types = [k for k in config.keys() if k not in 
                       ['default_database', 'vector_db', 'additional_settings']]
            
            logger.info(f"Loaded database types from config: {db_types}")
            return db_types
        except Exception as e:
            logger.warning(f"Failed to load config.yaml: {e}")
            # Fall back to default database types
            default_types = ["postgres", "mongodb", "qdrant", "slack", "shopify"]
            logger.info(f"Using default database types: {default_types}")
            return default_types
    
    def _extend_keywords(self):
        """Extend keywords for new database types not in the default mapping"""
        for db_type in self.db_types:
            if db_type not in self.default_keywords:
                # Generate keywords based on the database type
                # This is a simple approach and can be improved
                self.default_keywords[db_type] = [
                    db_type,  # The name itself
                    f"{db_type} database",  # "<type> database"
                    # Add more generic keywords based on database categories
                    # For example, if it's a new SQL database
                    "table" if "sql" in db_type.lower() else "",
                    "document" if "document" in db_type.lower() or "nosql" in db_type.lower() else "",
                ]
                # Filter out empty strings
                self.default_keywords[db_type] = [k for k in self.default_keywords[db_type] if k]
                
                logger.info(f"Added keywords for new database type {db_type}: {self.default_keywords[db_type]}")
    
    async def _get_schema_metadata(self, question: str) -> Dict[str, Any]:
        """
        Fetch relevant schema metadata from FAISS based on the question
        
        Args:
            question: Natural language question
            
        Returns:
            Dictionary mapping db_types to their schema metadata and relevance scores
        """
        try:
            # Get all database types
            all_db_types = set()
            for source in self.client.get_all_sources():
                if "type" in source:
                    all_db_types.add(source["type"])
            
            # Check if the question explicitly mentions a specific database type
            question_lower = question.lower()
            explicit_db_types = set()
            for db_type in all_db_types:
                if db_type.lower() in question_lower:
                    explicit_db_types.add(db_type)
                    logger.info(f"🎯 EXPLICIT DB MENTION: Found '{db_type}' mentioned in question")
            
            # If explicit database types are mentioned, only search those
            if explicit_db_types:
                search_db_types = explicit_db_types
                logger.info(f"🎯 EXPLICIT DB SEARCH: Only searching explicitly mentioned databases: {search_db_types}")
            else:
                search_db_types = all_db_types
                logger.info(f"🌐 FULL DB SEARCH: No explicit database mentions, searching all: {search_db_types}")
            
            # Search for relevant schema in FAISS for each db type
            schema_info = {}
            relevance_scores = {}
            
            for db_type in search_db_types:
                # Search FAISS index for this db_type
                try:
                    schema_results = await self.schema_searcher.search(
                        query=question,
                        top_k=5,  # Get top 5 results
                        db_type=db_type
                    )
                    
                    if schema_results:
                        # Store schema info
                        schema_info[db_type] = schema_results
                        
                        # Print schema details for debugging
                        logger.info(f"==== Schema results for {db_type} ====")
                        for i, result in enumerate(schema_results):
                            # Print basic metadata
                            distance = result.get('distance', 0)
                            score = 1.0 / (1.0 + distance)  # Convert distance to score (lower distance = higher score)
                            logger.info(f"  Result {i+1}: Distance {distance:.4f}, Score {score:.4f}")
                            
                            # Print table info if available
                            if 'table_name' in result:
                                logger.info(f"  Table: {result.get('table_name')}")
                            
                            # Print column info if available
                            if 'columns' in result:
                                columns = result.get('columns', [])
                                if isinstance(columns, list) and columns:
                                    col_str = ", ".join(col.get('name', 'unknown') for col in columns[:5])
                                    logger.info(f"  Columns: {col_str}...")
                                elif isinstance(columns, dict):
                                    col_str = ", ".join(list(columns.keys())[:5])
                                    logger.info(f"  Columns: {col_str}...")
                            
                            # Print schema content if available
                            if 'schema' in result:
                                schema = result.get('schema')
                                if isinstance(schema, dict):
                                    logger.info(f"  Schema keys: {', '.join(list(schema.keys())[:5])}")
                            
                            # Print text content if available
                            if 'content' in result:
                                content = result.get('content', '')
                                if content and isinstance(content, str):
                                    preview = content[:100] + "..." if len(content) > 100 else content
                                    logger.info(f"  Content preview: {preview}")
                        
                        # Calculate a relevance score based on the search results
                        # Convert distances to scores (lower distance = higher score)
                        total_score = sum(1.0 / (1.0 + result.get("distance", 0)) for result in schema_results)
                        avg_score = total_score / len(schema_results) if schema_results else 0
                        relevance_scores[db_type] = avg_score
                        
                        logger.info(f"FAISS schema relevance for {db_type}: {avg_score:.3f}")
                except Exception as e:
                    logger.warning(f"Error searching FAISS for {db_type}: {e}")
                    # Skip this db_type on error
                    continue
            
            logger.info(f"📊 SCHEMA SEARCH COMPLETE: Searched {len(search_db_types)} database types, found results for {len(schema_info)} types")
            
            return {
                "schema_info": schema_info,
                "relevance_scores": relevance_scores
            }
        
        except Exception as e:
            logger.error(f"Error fetching schema metadata: {e}")
            return {"schema_info": {}, "relevance_scores": {}}
    
    def _get_schema_based_sources(self, question: str, metadata: Dict[str, Any]) -> Set[str]:
        """
        Determine relevant sources based on schema metadata from FAISS
        
        Args:
            question: Natural language question
            metadata: Schema metadata and relevance scores
            
        Returns:
            Set of relevant source IDs
        """
        relevant_sources = set()
        relevance_scores = metadata.get("relevance_scores", {})
        schema_info = metadata.get("schema_info", {})
        
        # Set a threshold for relevance scores
        threshold = 0.5  # Adjust as needed
        
        # Get all sources to map db_types to source IDs
        all_sources = self.client.get_all_sources()
        
        # Select db_types with relevance scores above threshold
        selected_db_types = set()
        for db_type, score in relevance_scores.items():
            if score >= threshold:
                selected_db_types.add(db_type)
                logger.info(f"Selected {db_type} based on schema relevance (score: {score:.3f})")
        
        # Find sources matching selected db_types
        for source in all_sources:
            source_id = source["id"]
            db_type = source.get("type")
            
            if db_type in selected_db_types:
                relevant_sources.add(source_id)
                logger.info(f"Added source {source_id} of type {db_type} based on schema relevance")
        
        # If schema-based selection found nothing, return empty set
        if not relevant_sources:
            logger.info("No sources selected based on schema relevance")
        
        return relevant_sources
    
    async def classify(self, question: str) -> Dict[str, Any]:
        """
        Determine which databases to query for a given question
        
        Args:
            question: Natural language question
            
        Returns:
            Dict containing:
              - sources: List of source IDs to query
              - reasoning: Explanation of why these sources were selected
              - schemas: Schema summary for the selected sources
              - schema_metadata: Raw schema metadata from FAISS (for reuse in planning)
        """
        # Step 1: Get schema metadata from FAISS
        schema_metadata = await self._get_schema_metadata(question)
        
        # Step 2: Get schema-based source recommendations
        schema_sources = self._get_schema_based_sources(question, schema_metadata)
        
        # Step 3: Get recommended sources from the registry
        registry_sources = self.client.get_recommended_sources_for_query(question)
        
        # Step 4: Apply additional filtering and keyword-based logic
        keyword_sources = self._keyword_based_selection(question)
        
        # Step 5: Combine sources from different methods
        combined_sources = schema_sources.union(registry_sources).union(keyword_sources)
        
        # Step 6: Apply final filtering
        filtered_sources = self._filter_sources(combined_sources, question)
        
        # Step 7: Generate reasoning
        reasoning = self._generate_reasoning(filtered_sources, question, schema_metadata)
        
        # Step 8: Get schema summary for selected sources
        schema_summary = self.client.get_schema_summary_for_sources(list(filtered_sources))
        
        return {
            "sources": list(filtered_sources),
            "reasoning": reasoning,
            "schemas": schema_summary,
            "schema_metadata": schema_metadata  # Include the raw schema metadata for reuse
        }
    
    def _keyword_based_selection(self, question: str) -> Set[str]:
        """
        Select sources based on keywords in the question
        
        Args:
            question: Natural language question
            
        Returns:
            Set of source IDs selected based on keywords
        """
        # Detect database types based on keywords
        detected_db_types = set()
        for db_type, keywords in self.default_keywords.items():
            for keyword in keywords:
                if keyword.lower() in question.lower():
                    detected_db_types.add(db_type)
                    logger.info(f"Detected database type {db_type} from keyword '{keyword}'")
                    break
        
        # Find sources matching detected db_types
        keyword_sources = set()
        all_sources = self.client.get_all_sources()
        
        for source in all_sources:
            source_id = source["id"]
            db_type = source.get("type")
            
            if db_type in detected_db_types:
                keyword_sources.add(source_id)
                logger.info(f"Added source {source_id} of type {db_type} based on keywords")
        
        return keyword_sources
    
    def _filter_sources(self, sources: Set[str], question: str) -> Set[str]:
        """
        Apply additional filtering logic to refine the source selection
        
        Args:
            sources: Initial set of recommended sources
            question: The original question
            
        Returns:
            Filtered set of sources
        """
        # Get all sources
        all_sources = self.client.get_all_sources()
        sources_by_id = {s["id"]: s for s in all_sources}
        
        # Check if we need to limit the number of sources
        if len(sources) > 3:  # Adjust threshold as needed
            # Prioritize sources based on table/collection mentions
            priority_sources = set()
            
            for source_id in sources:
                if source_id not in sources_by_id:
                    continue
                    
                # Check if any tables from this source are mentioned
                tables = self.client.list_tables(source_id)
                for table in tables:
                    if table.lower() in question.lower():
                        priority_sources.add(source_id)
                        logger.info(f"Prioritized source {source_id} due to table mention: {table}")
                        break
            
            # If we found priority sources, use those
            if priority_sources:
                return priority_sources
        
        # If we don't need to filter or no priority sources found, return all
        return sources
    
    def _generate_reasoning(self, sources: Set[str], question: str, 
                          schema_metadata: Dict[str, Any] = None) -> str:
        """
        Generate an explanation for why these sources were selected
        
        Args:
            sources: Selected data sources
            question: The original question
            schema_metadata: Optional schema metadata from FAISS
            
        Returns:
            Explanation string
        """
        reasoning = []
        
        # Group sources by database type
        sources_by_type = {}
        all_sources = self.client.get_all_sources()
        for source in all_sources:
            if source["id"] in sources:
                db_type = source["type"]
                if db_type not in sources_by_type:
                    sources_by_type[db_type] = []
                sources_by_type[db_type].append(source["id"])
        
        # Include schema-based reasoning if available
        if schema_metadata and "relevance_scores" in schema_metadata:
            for db_type, score in schema_metadata["relevance_scores"].items():
                if db_type in sources_by_type:
                    source_names = ", ".join(sources_by_type[db_type])
                    reasoning.append(f"Selected {db_type} source(s) [{source_names}] based on schema relevance (score: {score:.3f})")
        
        # Explain selection by database type and keywords
        for db_type, source_ids in sources_by_type.items():
            # Skip if already explained by schema relevance
            if schema_metadata and "relevance_scores" in schema_metadata and db_type in schema_metadata["relevance_scores"]:
                continue
                
            source_names = ", ".join(source_ids)
            
            # Check if any keywords for this db_type appear in the question
            matched_keywords = []
            if db_type in self.default_keywords:
                for keyword in self.default_keywords[db_type]:
                    if keyword.lower() in question.lower():
                        matched_keywords.append(keyword)
            
            if matched_keywords:
                keyword_list = ", ".join(f"'{kw}'" for kw in matched_keywords)
                reasoning.append(f"Selected {db_type} source(s) [{source_names}] because question contains keywords: {keyword_list}")
            else:
                reasoning.append(f"Selected {db_type} source(s) [{source_names}] based on schema relevance")
        
        # Check for direct table mentions
        mentioned_tables = []
        for source_id in sources:
            tables = self.client.list_tables(source_id)
            for table in tables:
                if table.lower() in question.lower():
                    mentioned_tables.append(f"{source_id}.{table}")
        
        if mentioned_tables:
            reasoning.append(f"Question directly mentions tables: {', '.join(mentioned_tables)}")
        
        # Check for business entity mentions
        ontology = self.client.get_ontology_to_tables_mapping()
        for entity, table_refs in ontology.items():
            if entity.lower() in question.lower():
                reasoning.append(f"Question references business entity '{entity}' mapped to {table_refs}")
        
        # If no specific reason was found
        if not reasoning:
            reasoning.append("No specific indicators found, selecting based on available data sources")
        
        return "\n".join(reasoning)


# Create a singleton instance for easy import
classifier = DatabaseClassifier()

# Simple test function
def test_classifier():
    """Test the classifier with some example questions"""
    test_questions = [
        "Show me all users who made purchases in the last month",
        "Find products with the highest ratings",
        "Search for documents about machine learning",
        "How many messages were sent in the #general channel yesterday?",
        "Which customers have spent more than $1000 this year?"
    ]
    
    for question in test_questions:
        result = classifier.classify(question)
        print(f"\nQuestion: {question}")
        print(f"Sources: {result['sources']}")
        print(f"Reasoning:\n{result['reasoning']}")
        print("Schema Summary:\n" + result['schemas'][:200] + "...")  # Truncated for brevity
        print("-" * 80)

if __name__ == "__main__":
    test_classifier() 