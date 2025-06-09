"""
Session management for Ceneca Agent Server

Provides secure session storage and management with httpOnly cookies and Redis/in-memory backend.
All sessions are stored server-side for maximum security.
"""

import json
import time
import uuid
import logging
import os
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class SessionData:
    """User session data"""
    session_id: str
    user_id: str
    email: str
    name: str
    groups: List[str]
    roles: List[str]
    created_at: float
    last_accessed: float
    expires_at: float
    provider: str = "okta"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        """Create from dictionary"""
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return time.time() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if session is valid (not expired)"""
        return not self.is_expired()
    
    def update_last_accessed(self) -> None:
        """Update last accessed timestamp"""
        self.last_accessed = time.time()

class SessionManager:
    """
    Manages user sessions with support for Redis or in-memory storage
    """
    
    def __init__(self, session_timeout: int = 3600, use_redis: bool = False, redis_url: str = ""):
        """
        Initialize session manager
        
        Args:
            session_timeout: Session timeout in seconds (default 1 hour)
            use_redis: Whether to use Redis for session storage
            redis_url: Redis connection URL (if using Redis)
        """
        self.session_timeout = session_timeout
        self.use_redis = use_redis
        self.redis_url = redis_url
        self._sessions: Dict[str, SessionData] = {}  # In-memory fallback
        self._redis_client = None
        
        if use_redis:
            self._init_redis()
        else:
            logger.info("Using in-memory session storage (not recommended for production)")
    
    def _init_redis(self) -> None:
        """Initialize Redis connection"""
        try:
            import redis.asyncio as redis
            
            if not self.redis_url:
                # Default Redis configuration
                self.redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Initialized Redis session storage: {self.redis_url}")
            
        except ImportError:
            logger.warning("Redis not available, falling back to in-memory session storage")
            self.use_redis = False
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            logger.warning("Falling back to in-memory session storage")
            self.use_redis = False
    
    async def create_session(
        self,
        user_id: str,
        email: str,
        name: str,
        groups: List[str],
        roles: List[str],
        provider: str = "okta"
    ) -> str:
        """
        Create a new user session
        
        Args:
            user_id: Unique user identifier
            email: User email
            name: User display name
            groups: User groups from IdP
            roles: Mapped Ceneca roles
            provider: Authentication provider
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            email=email,
            name=name,
            groups=groups,
            roles=roles,
            created_at=current_time,
            last_accessed=current_time,
            expires_at=current_time + self.session_timeout,
            provider=provider
        )
        
        await self._store_session(session_id, session_data)
        
        logger.info(f"Created session for user {email} (ID: {session_id[:8]}...)")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Get session data by session ID
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionData if valid session exists, None otherwise
        """
        if not session_id:
            return None
            
        session_data = await self._get_session(session_id)
        
        if not session_data:
            return None
            
        if session_data.is_expired():
            await self.delete_session(session_id)
            logger.info(f"Expired session removed: {session_id[:8]}...")
            return None
        
        # Update last accessed time
        session_data.update_last_accessed()
        await self._store_session(session_id, session_data)
        
        return session_data
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        if self.use_redis and self._redis_client:
            try:
                result = await self._redis_client.delete(f"session:{session_id}")
                success = result > 0
            except Exception as e:
                logger.error(f"Failed to delete session from Redis: {e}")
                success = False
        else:
            success = session_id in self._sessions
            if success:
                del self._sessions[session_id]
        
        if success:
            logger.info(f"Deleted session: {session_id[:8]}...")
        
        return success
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        cleaned_count = 0
        
        if self.use_redis and self._redis_client:
            # For Redis, we rely on TTL for cleanup
            # But we can scan for any expired sessions that might exist
            try:
                pattern = "session:*"
                async for key in self._redis_client.scan_iter(match=pattern):
                    session_data_str = await self._redis_client.get(key)
                    if session_data_str:
                        try:
                            session_data = SessionData.from_dict(json.loads(session_data_str))
                            if session_data.is_expired():
                                await self._redis_client.delete(key)
                                cleaned_count += 1
                        except Exception:
                            # Invalid session data, delete it
                            await self._redis_client.delete(key)
                            cleaned_count += 1
            except Exception as e:
                logger.error(f"Error during Redis session cleanup: {e}")
        else:
            # In-memory cleanup
            expired_sessions = [
                session_id for session_id, session_data in self._sessions.items()
                if session_data.is_expired()
            ]
            
            for session_id in expired_sessions:
                del self._sessions[session_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
        
        return cleaned_count
    
    async def extend_session(self, session_id: str, additional_time: int = None) -> bool:
        """
        Extend session expiration time
        
        Args:
            session_id: Session identifier
            additional_time: Additional time in seconds (defaults to session_timeout)
            
        Returns:
            True if session was extended, False if not found
        """
        session_data = await self._get_session(session_id)
        
        if not session_data or session_data.is_expired():
            return False
        
        if additional_time is None:
            additional_time = self.session_timeout
        
        session_data.expires_at = time.time() + additional_time
        session_data.update_last_accessed()
        
        await self._store_session(session_id, session_data)
        
        logger.debug(f"Extended session: {session_id[:8]}...")
        return True
    
    async def get_active_sessions_count(self) -> int:
        """
        Get count of active (non-expired) sessions
        
        Returns:
            Number of active sessions
        """
        if self.use_redis and self._redis_client:
            try:
                pattern = "session:*"
                count = 0
                async for key in self._redis_client.scan_iter(match=pattern):
                    session_data_str = await self._redis_client.get(key)
                    if session_data_str:
                        try:
                            session_data = SessionData.from_dict(json.loads(session_data_str))
                            if not session_data.is_expired():
                                count += 1
                        except Exception:
                            pass
                return count
            except Exception as e:
                logger.error(f"Error counting Redis sessions: {e}")
                return 0
        else:
            return len([
                s for s in self._sessions.values()
                if not s.is_expired()
            ])
    
    async def _store_session(self, session_id: str, session_data: SessionData) -> None:
        """Store session data"""
        if self.use_redis and self._redis_client:
            try:
                key = f"session:{session_id}"
                value = json.dumps(session_data.to_dict())
                # Set TTL slightly longer than session timeout for cleanup
                ttl = int(session_data.expires_at - time.time()) + 60
                
                await self._redis_client.setex(key, ttl, value)
            except Exception as e:
                logger.error(f"Failed to store session in Redis: {e}")
                # Fallback to in-memory
                self._sessions[session_id] = session_data
        else:
            self._sessions[session_id] = session_data
    
    async def _get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data from storage"""
        if self.use_redis and self._redis_client:
            try:
                key = f"session:{session_id}"
                session_data_str = await self._redis_client.get(key)
                
                if session_data_str:
                    return SessionData.from_dict(json.loads(session_data_str))
                return None
            except Exception as e:
                logger.error(f"Failed to get session from Redis: {e}")
                # Fallback to in-memory
                return self._sessions.get(session_id)
        else:
            return self._sessions.get(session_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for session manager
        
        Returns:
            Health status information
        """
        status = {
            "storage_type": "redis" if self.use_redis else "memory",
            "session_timeout": self.session_timeout,
            "active_sessions": await self.get_active_sessions_count()
        }
        
        if self.use_redis and self._redis_client:
            try:
                await self._redis_client.ping()
                status["redis_status"] = "connected"
            except Exception as e:
                status["redis_status"] = f"error: {e}"
                status["redis_error"] = str(e)
        
        return status 