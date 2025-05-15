"""
Database Classifier Module

This module determines which databases should be queried for a given natural language question.
It uses the Schema Registry to analyze database metadata and make intelligent decisions.
"""
import logging
from typing import List, Set, Dict, Any
import re

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
        # For now, just use the registry's recommendations
        # This can be expanded with more sophisticated filtering logic
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
        
        # Check for keyword matches
        keyword_matches = {
            "postgres": ["table", "row", "sql", "query", "join"],
            "mongodb": ["document", "collection", "json", "nosql"],
            "qdrant": ["similar", "vector", "embedding", "semantic"],
            "slack": ["message", "channel", "chat", "conversation"]
        }
        
        for db_type, keywords in keyword_matches.items():
            for keyword in keywords:
                if keyword in question.lower():
                    reasoning.append(f"Question contains '{keyword}' which suggests {db_type}")
                    break
        
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