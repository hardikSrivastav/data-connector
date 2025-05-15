#!/usr/bin/env python3
"""
Test script for the classifier and cross-database orchestration functionality.
This is a simple standalone test to verify basic functionality.
With VERBOSE output to show all internal steps and thinking.
"""
import sys
import os
import logging
import json
import asyncio
import pprint
from pathlib import Path

# Configure logging - more verbose
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set this to True for even more verbose output
VERBOSE = True

def log_section(title):
    """Log a section header"""
    logger.info("\n" + "="*80)
    logger.info(f"  {title}  ".center(80, "="))
    logger.info("="*80)

def log_step(step_number, description):
    """Log a step in the process"""
    logger.info(f"\n[STEP {step_number}] {description}\n" + "-"*80)

def log_details(title, data):
    """Log detailed information"""
    if VERBOSE:
        if isinstance(data, str):
            logger.info(f"[DETAILS] {title}:\n{data}")
        else:
            logger.info(f"[DETAILS] {title}:\n{pprint.pformat(data)}")

async def test_classifier():
    """Test the database classifier with verbose output"""
    log_section("DATABASE CLASSIFIER TEST")
    
    # Import the classifier directly
    log_step(1, "Importing database classifier")
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from server.agent.db.classifier import classifier, DatabaseClassifier
    
    # Log the classifier configuration
    log_step(2, "Examining classifier configuration")
    log_details("Database types", classifier.db_types)
    log_details("Default keywords for each database type", classifier.default_keywords)
    
    # Test queries for different database types
    test_queries = [
        "Show me all users who made purchases in the last month",  # SQL
        "Find products with the highest ratings",  # General
        "Search for documents about machine learning",  # MongoDB
        "Find similar products to the one with ID 1234",  # Qdrant
        "How many messages were sent in the #general channel yesterday?",  # Slack
        "Which customers have spent more than $1000 this year?",  # SQL
        "Find users who posted messages in Slack and also made purchases",  # Cross-DB
    ]
    
    # Process each query
    for i, query in enumerate(test_queries):
        log_step(3 + i, f"Testing query: '{query}'")
        
        # Show internal thinking process
        logger.info(f"QUERY ANALYSIS:")
        logger.info(f"  Looking for database-specific keywords in query...")
        
        # Log the expected database types for this query (manually added for clarity)
        expected_db_types = []
        if "users" in query.lower() or "purchases" in query.lower():
            expected_db_types.append("postgres")
        if "document" in query.lower() or "collection" in query.lower():
            expected_db_types.append("mongodb")
        if "similar" in query.lower() or "vector" in query.lower():
            expected_db_types.append("qdrant")
        if "message" in query.lower() or "channel" in query.lower():
            expected_db_types.append("slack")
        
        logger.info(f"  Expected database types based on keywords: {expected_db_types}")
        
        # Classify the query
        logger.info(f"  Classifying query...")
        result = classifier.classify(query)
        
        # Print full classification details
        logger.info(f"\nCLASSIFICATION RESULT:")
        logger.info(f"  Relevant sources: {result['sources']}")
        logger.info(f"  Reasoning:\n{result['reasoning']}")
        
        # Print the full schema summary
        if VERBOSE:
            logger.info(f"\nFULL SCHEMA SUMMARY:")
            logger.info(f"{result['schemas']}")
        else:
            logger.info(f"\nSCHEMA SUMMARY (truncated):")
            logger.info(f"{result['schemas'][:200]}...")

async def test_result_aggregator():
    """Test the result aggregator with verbose output"""
    log_section("RESULT AGGREGATOR TEST")
    
    # Import the result aggregator directly
    log_step(1, "Importing result aggregator")
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from server.agent.db.orchestrator.result_aggregator import ResultAggregator
    
    # Create sample results from different databases
    log_step(2, "Creating sample test data")
    sample_results = [
        {
            "source_id": "postgres",
            "success": True,
            "data": [
                {"id": 1, "name": "John", "age": 30},
                {"id": 2, "name": "Alice", "age": 25},
                {"id": 3, "name": "Bob", "age": 40}
            ]
        },
        {
            "source_id": "mongodb",
            "success": True,
            "data": [
                {"id": 1, "email": "john@example.com", "active": True},
                {"id": 4, "email": "dave@example.com", "active": False},
                {"id": 5, "email": "sarah@example.com", "active": True}
            ]
        },
        {
            "source_id": "slack",
            "success": False,
            "error": "Connection failed",
            "data": []
        }
    ]
    
    log_details("Test data - Postgres records", sample_results[0]["data"])
    log_details("Test data - MongoDB records", sample_results[1]["data"])
    log_details("Test data - Slack (failing source)", sample_results[2])
    
    # Initialize the aggregator
    log_step(3, "Initializing result aggregator")
    aggregator = ResultAggregator()
    log_details("Type coercion functions available", {k: str(v)[:50] + "..." for k, v in aggregator.type_coercers.items()})
    
    # Test merge operation
    log_step(4, "Testing MERGE operation")
    logger.info("THINKING: The merge operation will combine all successful results into a single list,")
    logger.info("          while adding a '_source' field to track the origin of each record.")
    
    merge_result = aggregator.aggregate_results(sample_results, operation="merge")
    log_details("Merge operation metadata", {
        "sources_queried": merge_result["sources_queried"],
        "sources_succeeded": merge_result["sources_succeeded"],
        "sources_failed": merge_result["sources_failed"],
        "warnings": merge_result["warnings"],
    })
    logger.info(f"\nMERGED RESULTS: {len(merge_result['results'])} records")
    logger.info(json.dumps(merge_result['results'], indent=2))
    
    # Test join operation
    log_step(5, "Testing JOIN operation")
    logger.info("THINKING: The join operation will join records from different sources based on a common field (id).")
    logger.info("          Records will be merged when they have the same join field value.")
    
    join_fields = {"postgres": "id", "mongodb": "id"}
    log_details("Join fields configuration", join_fields)
    
    # Create type mappings for more accurate joining
    type_mappings = {
        "postgres": {"id": "int", "name": "str", "age": "int"},
        "mongodb": {"id": "int", "email": "str", "active": "bool"}
    }
    log_details("Type mappings for coercion", type_mappings)
    
    join_result = aggregator.aggregate_results(
        sample_results, 
        operation="join",
        join_fields=join_fields,
        type_mappings=type_mappings
    )
    
    # Show detailed step-by-step join process (mock for clarity)
    logger.info("\nJOIN PROCESS DETAILS:")
    logger.info("1. Coercing data types for each source using type mappings")
    logger.info("2. Selecting postgres as primary source (most records)")
    logger.info("3. Creating index on 'id' field for mongodb data")
    logger.info("4. For each postgres record, looking up matching record in mongodb by id")
    logger.info("5. Merging matching records with prefixed field names")
    
    log_details("Join operation metadata", {
        "sources_queried": join_result["sources_queried"],
        "sources_succeeded": join_result["sources_succeeded"],
        "sources_failed": join_result["sources_failed"],
        "warnings": join_result["warnings"],
    })
    
    logger.info(f"\nJOINED RESULTS: {len(join_result['results'])} records")
    logger.info(json.dumps(join_result['results'], indent=2))
    
    # Test union operation
    log_step(6, "Testing UNION operation")
    logger.info("THINKING: The union operation will combine all records but remove duplicates,")
    logger.info("          based on the field values (ignoring the source).")
    
    union_result = aggregator.aggregate_results(sample_results, operation="union")
    
    # Show detailed union process (mock for clarity)
    logger.info("\nUNION PROCESS DETAILS:")
    logger.info("1. Merging all records from successful sources")
    logger.info("2. Converting each record to a hashable tuple of sorted items")
    logger.info("3. Using a set to track already seen records")
    logger.info("4. Building a new list with only unique records")
    
    log_details("Union operation metadata", {
        "sources_queried": union_result["sources_queried"],
        "sources_succeeded": union_result["sources_succeeded"],
        "sources_failed": union_result["sources_failed"],
        "warnings": union_result["warnings"],
    })
    
    logger.info(f"\nUNION RESULTS: {len(union_result['results'])} records")
    logger.info(json.dumps(union_result['results'], indent=2))
    
    # Test with type coercion
    log_step(7, "Testing type coercion")
    logger.info("THINKING: Testing type coercion for different data types")
    
    # Create test data with mixed types
    mixed_data = [
        {"date_str": "2023-05-15T10:30:00Z", "target_type": "date"},
        {"int_as_str": "42", "target_type": "int"},
        {"float_as_str": "3.14", "target_type": "float"},
        {"bool_as_int": 1, "target_type": "bool"},
        {"list_as_single": "item", "target_type": "array"},
        {"json_as_str": '{"key": "value"}', "target_type": "object"}
    ]
    
    logger.info("\nTYPE COERCION TESTS:")
    for item in mixed_data:
        value = item[next(k for k in item.keys() if k != 'target_type')]
        target_type = item["target_type"]
        coerced = aggregator.coerce_value(value, target_type)
        logger.info(f"  {value} ({type(value).__name__}) → {target_type} = {coerced} ({type(coerced).__name__})")

async def main():
    """Main test function with timing information"""
    start_time = asyncio.get_event_loop().time()
    logger.info("Starting tests...")
    
    # Test the classifier
    classifier_start = asyncio.get_event_loop().time()
    await test_classifier()
    classifier_end = asyncio.get_event_loop().time()
    
    # Test the result aggregator
    aggregator_start = asyncio.get_event_loop().time()
    await test_result_aggregator()
    aggregator_end = asyncio.get_event_loop().time()
    
    # Log timing information
    total_time = asyncio.get_event_loop().time() - start_time
    log_section("TEST SUMMARY")
    logger.info(f"Classifier test: {classifier_end - classifier_start:.2f} seconds")
    logger.info(f"Aggregator test: {aggregator_end - aggregator_start:.2f} seconds")
    logger.info(f"Total test time: {total_time:.2f} seconds")
    logger.info("\nTests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 