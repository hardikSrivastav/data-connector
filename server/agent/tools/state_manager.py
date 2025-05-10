import logging
import json
import os
import uuid
import time
from typing import Dict, Any, List, Optional
import asyncio
from ..config.settings import Settings
from .tools import _convert_to_serializable

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalysisState:
    """State container for a single analysis session"""
    
    def __init__(self, session_id: str, user_question: str):
        """
        Initialize a new analysis state
        
        Args:
            session_id: Unique identifier for this analysis session
            user_question: The original natural language question from the user
        """
        self.session_id = session_id
        self.user_question = user_question
        self.start_time = time.time()
        self.last_update_time = self.start_time
        
        # Core state tracking
        self.generated_queries: List[Dict[str, Any]] = []
        self.executed_tools: List[Dict[str, Any]] = []
        self.insights: List[Dict[str, Any]] = []
        
        # Final results
        self.final_sql: Optional[str] = None
        self.final_result: Optional[Dict[str, Any]] = None
        self.final_analysis: Optional[str] = None
        
        # Tracking large result handling
        self.is_large_result = False
        self.row_count = 0
        self.sample_used = False
        self.summary_used = False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a dictionary for serialization"""
        state_dict = {
            "session_id": self.session_id,
            "user_question": self.user_question,
            "start_time": self.start_time,
            "last_update_time": self.last_update_time,
            "duration_seconds": time.time() - self.start_time,
            "generated_queries": self.generated_queries,
            "executed_tools": self.executed_tools,
            "insights": self.insights,
            "final_sql": self.final_sql,
            "final_analysis": self.final_analysis,
            "is_large_result": self.is_large_result,
            "row_count": self.row_count,
            "sample_used": self.sample_used,
            "summary_used": self.summary_used
        }
        
        # Convert to serializable form
        return _convert_to_serializable(state_dict)
        
    def from_dict(self, data: Dict[str, Any]) -> 'AnalysisState':
        """Restore state from a dictionary"""
        self.session_id = data.get("session_id", self.session_id)
        self.user_question = data.get("user_question", self.user_question)
        self.start_time = data.get("start_time", self.start_time)
        self.last_update_time = data.get("last_update_time", self.last_update_time)
        
        self.generated_queries = data.get("generated_queries", [])
        self.executed_tools = data.get("executed_tools", [])
        self.insights = data.get("insights", [])
        
        self.final_sql = data.get("final_sql")
        self.final_result = data.get("final_result")
        self.final_analysis = data.get("final_analysis")
        
        self.is_large_result = data.get("is_large_result", False)
        self.row_count = data.get("row_count", 0)
        self.sample_used = data.get("sample_used", False)
        self.summary_used = data.get("summary_used", False)
        
        return self
    
    def add_executed_tool(self, tool_name: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Record a tool execution
        
        Args:
            tool_name: Name of the tool executed
            params: Parameters passed to the tool
            result: Result returned by the tool
        """
        # Make the result serializable before storing
        serializable_result = _convert_to_serializable(result)
        
        self.executed_tools.append({
            "timestamp": time.time(),
            "tool_name": tool_name,
            "params": _convert_to_serializable(params),
            "result_summary": self._summarize_result(serializable_result)
        })
        self.last_update_time = time.time()
    
    def add_generated_query(self, sql: str, description: str, is_final: bool = False) -> None:
        """
        Record a generated SQL query
        
        Args:
            sql: SQL query string
            description: Brief description of what the query does
            is_final: Whether this is the final query for the session
        """
        self.generated_queries.append({
            "timestamp": time.time(),
            "sql": sql,
            "description": description,
            "is_final": is_final
        })
        
        if is_final:
            self.final_sql = sql
            
        self.last_update_time = time.time()
    
    def add_insight(self, insight_type: str, description: str, data: Dict[str, Any]) -> None:
        """
        Record an insight generated during analysis
        
        Args:
            insight_type: Type of insight
            description: Description of the insight
            data: Supporting data for the insight
        """
        self.insights.append({
            "timestamp": time.time(),
            "type": insight_type,
            "description": description,
            "data": _convert_to_serializable(data)
        })
        self.last_update_time = time.time()
    
    def set_final_result(self, result: Dict[str, Any], analysis: str) -> None:
        """
        Set the final result and analysis
        
        Args:
            result: Final result data
            analysis: Final analysis text
        """
        self.final_result = _convert_to_serializable(result)
        self.final_analysis = analysis
        self.last_update_time = time.time()
    
    def _summarize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summarized version of a result for storage
        Removes large data arrays to keep state size manageable
        
        Args:
            result: Full result dictionary
            
        Returns:
            Summarized version of the result
        """
        # Create a shallow copy to avoid modifying the original
        summary = result.copy()
        
        # Handle common result structures
        if "rows" in summary and isinstance(summary["rows"], list):
            rows = summary["rows"]
            row_count = len(rows)
            
            # Keep only a small number of rows in the summary
            if row_count > 5:
                summary["rows"] = rows[:3]
                summary["row_count"] = row_count
                summary["rows_truncated"] = True
                
        return summary

class StateManager:
    """Manages analysis session states on-premises"""
    
    def __init__(self):
        """Initialize the state manager"""
        self.settings = Settings()
        self.states: Dict[str, AnalysisState] = {}
        self.state_dir = self._get_state_dir()
        self._ensure_state_dir_exists()
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def _get_state_dir(self) -> str:
        """Get the directory to store state files"""
        # Use cache path from settings if available
        if self.settings.CACHE_PATH:
            return os.path.join(self.settings.CACHE_PATH, "states")
        
        # Otherwise use a default location in the project
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "states")
    
    def _ensure_state_dir_exists(self) -> None:
        """Ensure the state directory exists"""
        os.makedirs(self.state_dir, exist_ok=True)
    
    def _get_state_file_path(self, session_id: str) -> str:
        """Get the file path for a state file"""
        return os.path.join(self.state_dir, f"{session_id}.json")
    
    async def create_session(self, user_question: str) -> str:
        """
        Create a new analysis session
        
        Args:
            user_question: The original natural language question
            
        Returns:
            Session ID for the new session
        """
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Create new state
        state = AnalysisState(session_id, user_question)
        
        # Store in memory and on disk
        async with self._lock:
            self.states[session_id] = state
            await self._save_state(state)
        
        logger.info(f"Created new analysis session {session_id} for question: {user_question}")
        return session_id
    
    async def get_state(self, session_id: str) -> Optional[AnalysisState]:
        """
        Get the state for a session
        
        Args:
            session_id: The session ID
            
        Returns:
            AnalysisState if found, None otherwise
        """
        # Check memory first
        if session_id in self.states:
            return self.states[session_id]
        
        # Otherwise try to load from disk
        state_path = self._get_state_file_path(session_id)
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    data = json.load(f)
                
                state = AnalysisState(session_id, "")
                state.from_dict(data)
                
                # Cache in memory
                self.states[session_id] = state
                
                return state
            except Exception as e:
                logger.error(f"Error loading state for session {session_id}: {str(e)}")
        
        return None
    
    async def update_state(self, state: AnalysisState) -> None:
        """
        Update a session state
        
        Args:
            state: The updated state
        """
        async with self._lock:
            # Update in memory
            self.states[state.session_id] = state
            
            # Persist to disk
            await self._save_state(state)
    
    async def _save_state(self, state: AnalysisState) -> None:
        """
        Save a state to disk
        
        Args:
            state: The state to save
        """
        state_path = self._get_state_file_path(state.session_id)
        try:
            # Get serializable state dict
            state_dict = state.to_dict()
            
            # Save to file
            with open(state_path, 'w') as f:
                json.dump(state_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving state for session {state.session_id}: {str(e)}")
    
    async def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List recent analysis sessions
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session summary dictionaries
        """
        # First get all state files
        try:
            state_files = [f for f in os.listdir(self.state_dir) if f.endswith('.json')]
        except Exception:
            state_files = []
        
        # Load basic info for each
        sessions = []
        for state_file in state_files[:limit]:
            try:
                session_id = state_file.replace('.json', '')
                state = await self.get_state(session_id)
                if state:
                    sessions.append({
                        "session_id": state.session_id,
                        "user_question": state.user_question,
                        "start_time": state.start_time,
                        "last_update_time": state.last_update_time,
                        "duration_seconds": time.time() - state.start_time,
                        "has_final_result": state.final_result is not None
                    })
            except Exception as e:
                logger.error(f"Error loading session info from {state_file}: {str(e)}")
        
        # Sort by most recent first
        sessions.sort(key=lambda s: s.get('last_update_time', 0), reverse=True)
        
        return sessions[:limit]
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session
        
        Args:
            session_id: The session ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        async with self._lock:
            # Remove from memory
            if session_id in self.states:
                del self.states[session_id]
            
            # Remove from disk
            state_path = self._get_state_file_path(session_id)
            if os.path.exists(state_path):
                try:
                    os.remove(state_path)
                    return True
                except Exception as e:
                    logger.error(f"Error deleting state file for session {session_id}: {str(e)}")
        
        return False
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old session files
        
        Args:
            max_age_hours: Maximum age in hours for sessions to keep
            
        Returns:
            Number of sessions cleaned up
        """
        max_age_seconds = max_age_hours * 3600
        now = time.time()
        
        cleaned_count = 0
        try:
            state_files = [f for f in os.listdir(self.state_dir) if f.endswith('.json')]
            
            for state_file in state_files:
                try:
                    state_path = os.path.join(self.state_dir, state_file)
                    file_mod_time = os.path.getmtime(state_path)
                    
                    if now - file_mod_time > max_age_seconds:
                        session_id = state_file.replace('.json', '')
                        if await self.delete_session(session_id):
                            cleaned_count += 1
                except Exception as e:
                    logger.error(f"Error cleaning up session file {state_file}: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing state files for cleanup: {str(e)}")
        
        return cleaned_count 