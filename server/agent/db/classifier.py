"""
Database Classifier Module

This module determines which databases should be queried for a given natural language question.
It uses the Schema Registry to analyze database metadata and make intelligent decisions.
"""
import logging
import os
import yaml
from typing import List, Set, Dict, Any
import re
from pathlib import Path

# Import the schema registry client
from .registry.integrations import registry_client

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
        
        # Load database types from config.yaml
        self.db_types = self._load_database_types()
        
        # Define default keywords for standard database types
        self.default_keywords = {
            "postgres": ["table", "row", "sql", "query", "join", "database", "relational"],
            "mongodb": ["document", "collection", "json", "nosql", "unstructured"],
            "qdrant": ["similar", "vector", "embedding", "semantic", "similarity", "neural"],
            "slack": ["message", "channel", "chat", "conversation", "slack", "communication"],
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
            default_types = ["postgres", "mongodb", "qdrant", "slack"]
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
    
    def classify(self, question: str) -> Dict[str, Any]:
        """
        Determine which databases to query for a given question
        
        Args:
            question: Natural language question
            
        Returns:
            Dict containing:
              - sources: List of source IDs to query
              - reasoning: Explanation of why these sources were selected
              - schemas: Schema summary for the selected sources
        """
        # Step 1: Get recommended sources from the registry
        sources = self.client.get_recommended_sources_for_query(question)
        
        # Step 2: Apply additional filtering logic
        filtered_sources = self._filter_sources(sources, question)
        
        # Step 3: Generate reasoning
        reasoning = self._generate_reasoning(filtered_sources, question)
        
        # Step 4: Get schema summary for selected sources
        schema_summary = self.client.get_schema_summary_for_sources(list(filtered_sources))
        
        return {
            "sources": list(filtered_sources),
            "reasoning": reasoning,
            "schemas": schema_summary
        }
    
    def _filter_sources(self, sources: Set[str], question: str) -> Set[str]:
        """
        Apply additional filtering logic to refine the source selection
        
        Args:
            sources: Initial set of recommended sources
            question: The original question
            
        Returns:
            Filtered set of sources
        """
        # Enhanced filtering based on database types in config
        sources_by_type = {}
        all_sources = self.client.get_all_sources()
        
        # Group sources by database type
        for source in all_sources:
            source_id = source["id"]
            db_type = source["type"]
            if db_type not in sources_by_type:
                sources_by_type[db_type] = []
            sources_by_type[db_type].append(source_id)
        
        # Analyze question to determine database types
        detected_db_types = set()
        
        # Check for database type keywords in the question
        for db_type, keywords in self.default_keywords.items():
            for keyword in keywords:
                if keyword.lower() in question.lower():
                    detected_db_types.add(db_type)
                    break
        
        # If specific database types were detected, prioritize those sources
        if detected_db_types:
            priority_sources = set()
            for db_type in detected_db_types:
                if db_type in sources_by_type:
                    priority_sources.update(sources_by_type[db_type])
            
            # Combine with registry recommendations
            combined_sources = sources.union(priority_sources)
            
            # If we have a reasonable number of sources, use them
            if len(combined_sources) <= 3:  # Adjust threshold as needed
                return combined_sources
            
            # If too many sources, prioritize detected types
            if len(priority_sources) > 0:
                return priority_sources
        
        # Fall back to registry recommendations
        return sources
    
    def _generate_reasoning(self, sources: Set[str], question: str) -> str:
        """
        Generate an explanation for why these sources were selected
        
        Args:
            sources: Selected data sources
            question: The original question
            
        Returns:
            Explanation string
        """
        reasoning = []
        
        # Get table information for each source
        tables_by_source = {}
        sources_by_type = {}
        
        # Group sources by database type
        all_sources = self.client.get_all_sources()
        for source in all_sources:
            if source["id"] in sources:
                db_type = source["type"]
                if db_type not in sources_by_type:
                    sources_by_type[db_type] = []
                sources_by_type[db_type].append(source["id"])
        
        # Explain selection by database type
        for db_type, source_ids in sources_by_type.items():
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
                
        for source_id in sources:
            tables = self.client.list_tables(source_id)
            if tables:
                tables_by_source[source_id] = tables
        
        # Check for direct table mentions
        mentioned_tables = []
        for source_id, tables in tables_by_source.items():
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