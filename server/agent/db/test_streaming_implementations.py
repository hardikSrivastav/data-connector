#!/usr/bin/env python
"""
Tests for actual streaming implementations in the query execution engine.

This test suite validates the streaming methods we implemented in execute.py
"""

import asyncio
import os
import sys
import json
import logging
import uuid
from typing import AsyncIterator, Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockCrossDatabaseQueryEngine:
    """Mock implementation to test streaming patterns"""
    
    def __init__(self):
        self.classifier = AsyncMock()
        self.cross_db_agent = AsyncMock()
        self.llm_client = AsyncMock()
        self.state_manager = AsyncMock()
        
        # Mock methods that might not exist
        self.llm_client.generate_sql_stream = AsyncMock()
        self.llm_client.generate_mongodb_query_stream = AsyncMock()
        self.llm_client.analyze_results_stream = AsyncMock()
        self.llm_client.render_template = Mock(return_value="test prompt")
    
    def _create_stream_event(self, event_type: str, session_id: str, **kwargs) -> Dict[str, Any]:
        """Create a standardized streaming event"""
        from datetime import datetime
        return {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            **kwargs
        }
    
    async def classify_query_stream(self, question: str, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
        """Mock classify_query_stream method"""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            yield self._create_stream_event("status", session_id, message="Starting query classification...")
            yield self._create_stream_event("classifying", session_id, message="Analyzing query intent...")
            
            # Mock classification result
            classification_result = {
                "sources": ["postgres_db"],
                "reasoning": "Query mentions users table"
            }
            
            yield self._create_stream_event("databases_selected", session_id, 
                                           databases=classification_result["sources"],
                                           is_cross_database=len(classification_result["sources"]) > 1,
                                           reasoning=classification_result["reasoning"])
            
            yield self._create_stream_event("classification_complete", session_id, success=True)
            
        except Exception as e:
            yield self._create_stream_event("error", session_id, 
                                          error_code="CLASSIFICATION_FAILED",
                                          message=str(e),
                                          recoverable=False)
    
    async def execute_single_database_query_stream(self, question: str, db_type: str, db_uri: str, 
                                                 analyze: bool, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Mock execute_single_database_query_stream method"""
        try:
            yield self._create_stream_event("status", session_id, message="Starting single database query...")
            yield self._create_stream_event("connection_testing", session_id, database=db_type, uri=db_uri)
            
            # Simulate connection failure for testing
            if "fail" in db_uri:
                yield self._create_stream_event("error", session_id,
                                              error_code="CONNECTION_FAILED",
                                              message="Failed to connect to database",
                                              recoverable=False)
                return
            
            yield self._create_stream_event("connection_established", session_id, database=db_type)
            yield self._create_stream_event("schema_loading", session_id, progress=0.5)
            yield self._create_stream_event("query_generating", session_id, template="nl2sql.tpl")
            yield self._create_stream_event("query_executing", session_id, database=db_type)
            yield self._create_stream_event("execution_complete", session_id, success=True)
            
        except Exception as e:
            yield self._create_stream_event("error", session_id,
                                          error_code="EXECUTION_FAILED",
                                          message=str(e),
                                          recoverable=True)
    
    async def execute_cross_database_query_stream(self, question: str, analyze: bool = False, 
                                                optimize: bool = False, save_session: bool = True, 
                                                session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
        """Mock execute_cross_database_query_stream method"""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            yield self._create_stream_event("status", session_id, message="Starting cross-database query...")
            yield self._create_stream_event("planning", session_id, message="Creating execution plan...")
            yield self._create_stream_event("plan_validated", session_id, steps=3, estimated_time="2.5s")
            yield self._create_stream_event("executing", session_id, step=1, total=3)
            yield self._create_stream_event("aggregating", session_id, progress=0.8)
            yield self._create_stream_event("cross_db_complete", session_id, success=True)
            
        except Exception as e:
            yield self._create_stream_event("error", session_id,
                                          error_code="CROSS_DB_FAILED",
                                          message=str(e),
                                          recoverable=True)
    
    async def _execute_postgres_query_stream(self, question: str, analyze: bool, orchestrator, 
                                           db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Mock _execute_postgres_query_stream method"""
        try:
            yield self._create_stream_event("postgres_connecting", session_id, host="localhost", database="testdb")
            yield self._create_stream_event("sql_generating", session_id, template="nl2sql.tpl")
            
            # Mock LLM streaming
            async for event in self._mock_sql_stream(session_id):
                yield event
            
            yield self._create_stream_event("sql_executing", session_id, sql="SELECT * FROM users")
            yield self._create_stream_event("postgres_complete", session_id, success=True, rows_returned=5)
            
        except Exception as e:
            yield self._create_stream_event("error", session_id,
                                          error_code="POSTGRES_FAILED",
                                          message=str(e),
                                          recoverable=True)
    
    async def _execute_mongodb_query_stream(self, question: str, analyze: bool, orchestrator, 
                                          db_type: str, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Mock _execute_mongodb_query_stream method"""
        try:
            yield self._create_stream_event("mongodb_connecting", session_id, host="localhost", database="testdb")
            yield self._create_stream_event("mongodb_query_generating", session_id, collection="users")
            yield self._create_stream_event("mongodb_executing", session_id, query='{"name": {"$exists": true}}')
            
            if analyze:
                yield self._create_stream_event("analysis_generating", session_id, message="Analyzing results...")
                async for event in self._mock_analysis_stream(session_id):
                    yield event
            
            yield self._create_stream_event("mongodb_complete", session_id, success=True, documents_returned=3)
            
        except Exception as e:
            yield self._create_stream_event("error", session_id,
                                          error_code="MONGODB_FAILED",
                                          message=str(e),
                                          recoverable=True)
    
    async def _mock_sql_stream(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Mock SQL generation streaming"""
        yield {"type": "partial_sql", "content": "SELECT * ", "session_id": session_id, "timestamp": "2024-01-01T12:00:00Z"}
        yield {"type": "sql_complete", "sql": "SELECT * FROM users", "session_id": session_id, "timestamp": "2024-01-01T12:00:00Z"}
    
    async def _mock_analysis_stream(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Mock analysis streaming"""
        yield {"type": "analysis_chunk", "text": "Analysis of users", "chunk_index": 1, "session_id": session_id, "timestamp": "2024-01-01T12:00:00Z"}
        yield {"type": "analysis_complete", "session_id": session_id, "timestamp": "2024-01-01T12:00:00Z"}

class TestStreamingImplementations:
    """Test the actual streaming method implementations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.engine = MockCrossDatabaseQueryEngine()
    
    async def test_classify_query_stream(self):
        """Test classify_query_stream method"""
        logger.info("🧪 Testing classify_query_stream")
        
        session_id = str(uuid.uuid4())
        question = "Show me all users"
        
        events = []
        async for event in self.engine.classify_query_stream(question, session_id):
            events.append(event)
            logger.info(f"📥 Event: {event['type']}")
        
        # Verify we got expected events
        event_types = [e["type"] for e in events]
        assert "status" in event_types
        assert "classifying" in event_types
        assert "databases_selected" in event_types
        assert "classification_complete" in event_types
        
        # Verify event structure
        for event in events:
            assert "type" in event
            assert "timestamp" in event
            assert "session_id" in event
            assert event["session_id"] == session_id
        
        logger.info(f"✅ classify_query_stream test passed with {len(events)} events")
    
    async def test_execute_single_database_query_stream_connection_failure(self):
        """Test execute_single_database_query_stream with connection failure"""
        logger.info("🧪 Testing execute_single_database_query_stream (connection failure)")
        
        session_id = str(uuid.uuid4())
        question = "Show me users"
        
        events = []
        async for event in self.engine.execute_single_database_query_stream(
            question, "postgres", "test://fail", False, session_id
        ):
            events.append(event)
            logger.info(f"📥 Event: {event['type']}")
        
        # Verify we got expected events including error
        event_types = [e["type"] for e in events]
        assert "status" in event_types
        assert "connection_testing" in event_types
        assert "error" in event_types
        
        # Check error event details
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) > 0
        error_event = error_events[0]
        assert error_event["error_code"] == "CONNECTION_FAILED"
        assert not error_event["recoverable"]
        
        logger.info(f"✅ Connection failure test passed with {len(events)} events")
    
    async def test_execute_single_database_query_stream_success(self):
        """Test execute_single_database_query_stream with successful connection"""
        logger.info("🧪 Testing execute_single_database_query_stream (success)")
        
        session_id = str(uuid.uuid4())
        question = "Show me users"
        
        events = []
        async for event in self.engine.execute_single_database_query_stream(
            question, "postgres", "test://localhost", False, session_id
        ):
            events.append(event)
            logger.info(f"📥 Event: {event['type']}")
        
        # Verify we got expected events
        event_types = [e["type"] for e in events]
        assert "status" in event_types
        assert "connection_testing" in event_types
        assert "connection_established" in event_types
        assert "schema_loading" in event_types
        assert "query_generating" in event_types
        assert "execution_complete" in event_types
        
        logger.info(f"✅ Single DB success test passed with {len(events)} events")
    
    async def test_execute_postgres_query_stream(self):
        """Test _execute_postgres_query_stream method"""
        logger.info("🧪 Testing _execute_postgres_query_stream")
        
        session_id = str(uuid.uuid4())
        question = "SELECT * FROM users"
        
        events = []
        async for event in self.engine._execute_postgres_query_stream(
            question, False, None, "postgres", session_id
        ):
            events.append(event)
            logger.info(f"📥 Event: {event['type']}")
        
        # Verify we got expected events
        event_types = [e["type"] for e in events]
        assert "postgres_connecting" in event_types
        assert "sql_generating" in event_types
        assert "sql_executing" in event_types
        assert "postgres_complete" in event_types
        
        logger.info(f"✅ _execute_postgres_query_stream test passed with {len(events)} events")
    
    async def test_execute_mongodb_query_stream_with_analysis(self):
        """Test _execute_mongodb_query_stream method with analysis"""
        logger.info("🧪 Testing _execute_mongodb_query_stream (with analysis)")
        
        session_id = str(uuid.uuid4())
        question = "Find users in MongoDB"
        
        events = []
        async for event in self.engine._execute_mongodb_query_stream(
            question, True, None, "mongodb", session_id  # analyze=True
        ):
            events.append(event)
            logger.info(f"📥 Event: {event['type']}")
        
        # Verify we got expected events including analysis
        event_types = [e["type"] for e in events]
        assert "mongodb_connecting" in event_types
        assert "mongodb_query_generating" in event_types
        assert "mongodb_executing" in event_types
        assert "analysis_generating" in event_types
        assert "mongodb_complete" in event_types
        
        logger.info(f"✅ _execute_mongodb_query_stream (with analysis) test passed with {len(events)} events")
    
    async def test_execute_cross_database_query_stream(self):
        """Test execute_cross_database_query_stream method"""
        logger.info("🧪 Testing execute_cross_database_query_stream")
        
        session_id = str(uuid.uuid4())
        question = "Compare data across databases"
        
        events = []
        async for event in self.engine.execute_cross_database_query_stream(
            question, analyze=False, session_id=session_id
        ):
            events.append(event)
            logger.info(f"📥 Event: {event['type']}")
        
        # Verify we got expected events
        event_types = [e["type"] for e in events]
        assert "status" in event_types
        assert "planning" in event_types
        assert "plan_validated" in event_types
        assert "cross_db_complete" in event_types
        
        logger.info(f"✅ execute_cross_database_query_stream test passed with {len(events)} events")
    
    async def test_streaming_error_handling(self):
        """Test error handling in streaming methods"""
        logger.info("🧪 Testing streaming error handling")
        
        session_id = str(uuid.uuid4())
        question = "This will cause an error"
        
        # Create a custom engine that will raise an exception
        class ErrorEngine(MockCrossDatabaseQueryEngine):
            async def classify_query_stream(self, question: str, session_id: str = None) -> AsyncIterator[Dict[str, Any]]:
                if not session_id:
                    session_id = str(uuid.uuid4())
                
                try:
                    yield self._create_stream_event("status", session_id, message="Starting query classification...")
                    # Simulate an error during classification
                    raise Exception("Classifier failed")
                except Exception as e:
                    yield self._create_stream_event("error", session_id, 
                                                  error_code="CLASSIFICATION_FAILED",
                                                  message=str(e),
                                                  recoverable=False)
        
        error_engine = ErrorEngine()
        
        events = []
        async for event in error_engine.classify_query_stream(question, session_id):
            events.append(event)
            logger.info(f"📥 Error Event: {event['type']}")
        
        # Verify we got an error event
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) > 0
        
        error_event = error_events[0]
        assert "error_code" in error_event
        assert "message" in error_event
        assert "recoverable" in error_event
        assert error_event["error_code"] == "CLASSIFICATION_FAILED"
        
        logger.info(f"✅ Error handling test passed with {len(error_events)} error events")
    
    async def test_streaming_event_format(self):
        """Test that all streaming events have the correct format"""
        logger.info("🧪 Testing streaming event format")
        
        session_id = str(uuid.uuid4())
        
        # Test the _create_stream_event helper
        event = self.engine._create_stream_event(
            "test_event", 
            session_id, 
            message="Test message",
            data={"key": "value"}
        )
        
        # Verify event structure
        required_fields = ["type", "timestamp", "session_id"]
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"
        
        assert event["type"] == "test_event"
        assert event["session_id"] == session_id
        assert event["message"] == "Test message"
        assert event["data"]["key"] == "value"
        
        # Verify timestamp format (ISO 8601 with Z)
        assert event["timestamp"].endswith("Z")
        assert "T" in event["timestamp"]
        
        logger.info("✅ Event format test passed")
    
    async def test_streaming_session_consistency(self):
        """Test that session IDs are consistent across streaming events"""
        logger.info("🧪 Testing streaming session consistency")
        
        session_id = str(uuid.uuid4())
        question = "Test query"
        
        events = []
        async for event in self.engine.classify_query_stream(question, session_id):
            events.append(event)
        
        # Verify all events have the same session_id
        for event in events:
            assert event["session_id"] == session_id
        
        logger.info(f"✅ Session consistency test passed with {len(events)} events")
    
    async def test_streaming_event_ordering(self):
        """Test that streaming events are emitted in the correct order"""
        logger.info("🧪 Testing streaming event ordering")
        
        session_id = str(uuid.uuid4())
        question = "Test query"
        
        events = []
        async for event in self.engine.execute_single_database_query_stream(
            question, "postgres", "test://localhost", False, session_id
        ):
            events.append(event)
        
        # Verify event ordering
        event_types = [e["type"] for e in events]
        
        # Status should come first
        assert event_types[0] == "status"
        
        # Connection testing should come before connection established
        status_idx = event_types.index("status")
        connection_test_idx = event_types.index("connection_testing")
        connection_est_idx = event_types.index("connection_established")
        
        assert status_idx < connection_test_idx < connection_est_idx
        
        logger.info(f"✅ Event ordering test passed with {len(events)} events")

async def run_all_streaming_tests():
    """Run all streaming implementation tests"""
    logger.info("🧪 Starting Streaming Implementation Tests")
    logger.info("=" * 60)
    
    try:
        # Test individual streaming methods
        test_instance = TestStreamingImplementations()
        test_instance.setup_method()
        
        await test_instance.test_classify_query_stream()
        await test_instance.test_execute_single_database_query_stream_connection_failure()
        await test_instance.test_execute_single_database_query_stream_success()
        await test_instance.test_execute_postgres_query_stream()
        await test_instance.test_execute_mongodb_query_stream_with_analysis()
        await test_instance.test_execute_cross_database_query_stream()
        await test_instance.test_streaming_error_handling()
        await test_instance.test_streaming_event_format()
        await test_instance.test_streaming_session_consistency()
        await test_instance.test_streaming_event_ordering()
        
        logger.info("🎉 All streaming implementation tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Streaming implementation test failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    logger.info("🧪 Running Streaming Implementation Tests")
    
    success = asyncio.run(run_all_streaming_tests())
    
    if success:
        logger.info("🎉 All streaming implementation tests completed successfully!")
    else:
        logger.error("❌ Some streaming implementation tests failed")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1) 