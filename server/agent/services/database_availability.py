import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from threading import Lock

from ..config.settings import Settings
from ..db.adapters import ADAPTER_REGISTRY

logger = logging.getLogger(__name__)

@dataclass
class DatabaseStatus:
    name: str
    type: str
    status: str  # 'online', 'offline', 'checking', 'error'
    last_checked: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    user_accessible: bool = True  # Will be determined by user permissions
    connection_details: Optional[Dict[str, Any]] = None

class DatabaseAvailabilityService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._status_cache: Dict[str, DatabaseStatus] = {}
        self._cache_lock = Lock()
        self._last_full_check = None
        self._check_interval = 60  # seconds
        self._running = False
        
    async def start_monitoring(self):
        """Start the background monitoring service"""
        self._running = True
        logger.info("Starting database availability monitoring")
        
        # Initial check
        await self.check_all_databases()
        
        # Start background polling
        asyncio.create_task(self._background_monitoring())
        
    async def stop_monitoring(self):
        """Stop the background monitoring service"""
        self._running = False
        logger.info("Stopping database availability monitoring")
        
    async def _background_monitoring(self):
        """Background task that periodically checks database availability"""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                if self._running:
                    await self.check_all_databases()
            except Exception as e:
                logger.error(f"Error in background database monitoring: {e}")
                
    async def check_all_databases(self) -> Dict[str, DatabaseStatus]:
        """Check all configured databases and update cache"""
        logger.info("Checking availability of all databases")
        
        # Get all configured databases
        databases = self._get_configured_databases()
        
        # Test each database concurrently
        tasks = []
        for db_config in databases:
            task = asyncio.create_task(
                self._check_single_database(db_config['name'], db_config)
            )
            tasks.append(task)
            
        # Wait for all checks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update cache
        with self._cache_lock:
            for i, result in enumerate(results):
                if isinstance(result, DatabaseStatus):
                    self._status_cache[databases[i]['name']] = result
                else:
                    # Handle exceptions
                    db_name = databases[i]['name']
                    self._status_cache[db_name] = DatabaseStatus(
                        name=db_name,
                        type=databases[i].get('type', 'unknown'),
                        status='error',
                        last_checked=datetime.now(),
                        error_message=str(result)
                    )
                    
        self._last_full_check = datetime.now()
        logger.info(f"Database availability check completed for {len(databases)} databases")
        
        return self.get_all_statuses()
        
    async def _check_single_database(self, db_name: str, db_config: Dict[str, Any]) -> DatabaseStatus:
        """Check a single database's availability"""
        start_time = time.time()
        
        try:
            logger.info(f"🔍 Checking database: {db_name} ({db_config.get('type', 'unknown')})")
            
            # Get the connection URI for this database
            connection_uri = self._get_database_uri(db_config)
            if not connection_uri:
                raise ValueError(f"No connection URI found for database {db_name}")
            
            # Get database adapter - normalize type names
            db_type = db_config['type'].lower()
            
            # Map database types to adapter registry keys
            type_mapping = {
                'postgres': 'postgresql',
                'postgresql': 'postgresql', 
                'mongo': 'mongodb',
                'mongodb': 'mongodb',
                'qdrant': 'qdrant',
                'slack': 'slack',
                'shopify': 'shopify',
                'ga4': 'ga4'
            }
            
            adapter_type = type_mapping.get(db_type, db_type)
            adapter_class = ADAPTER_REGISTRY.get(adapter_type)
            
            if not adapter_class:
                raise ValueError(f"No adapter found for database type: {db_type} (mapped to {adapter_type})")
            
            logger.info(f"🔧 Creating {adapter_type} adapter with URI: {self._mask_uri(connection_uri)}")
            
            # Create adapter instance
            adapter = adapter_class(connection_uri)
            
            # Test connection - handle both exception-based and return-value-based error reporting
            logger.info(f"⚡ Testing connection for {db_name}...")
            connection_result = await adapter.test_connection()
            logger.info(f"🔍 Connection test result for {db_name}: {connection_result} (type: {type(connection_result)})")
            
            # Some adapters return boolean, others raise exceptions
            if connection_result is False:
                raise ValueError("Connection test returned False")
            elif connection_result is not None and connection_result is not True:
                # If it's not None, True, or False, it might be an error message
                raise ValueError(f"Connection test failed: {connection_result}")
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Get connection details (sanitized)
            connection_details = self._get_connection_details(db_config)
            
            logger.info(f"✅ Database {db_name} is ONLINE (response time: {response_time:.0f}ms)")
            
            return DatabaseStatus(
                name=db_name,
                type=db_config['type'],
                status='online',
                last_checked=datetime.now(),
                response_time_ms=response_time,
                connection_details=connection_details
            )
            
        except Exception as e:
            logger.warning(f"❌ Database {db_name} check failed: {e}")
            
            return DatabaseStatus(
                name=db_name,
                type=db_config.get('type', 'unknown'),
                status='offline',
                last_checked=datetime.now(),
                error_message=str(e),
                connection_details=self._get_connection_details(db_config)
            )
            
    def _get_configured_databases(self) -> List[Dict[str, Any]]:
        """Get all configured databases from config.yaml"""
        databases = []
        
        try:
            # Load the actual config.yaml file
            from ..config.config_loader import load_config
            config = load_config()
            
            logger.info(f"Loaded config with databases: {list(config.keys())}")
            
            # Skip non-database keys
            skip_keys = {'default_database', 'vector_db', 'additional_settings', 'trivial_llm', 'okta'}
            
            # Iterate through all configured databases in config.yaml
            for db_name, db_config in config.items():
                if db_name in skip_keys or not isinstance(db_config, dict):
                    continue
                    
                # Check if this database section has connection information
                if 'uri' in db_config or any(key in db_config for key in ['host', 'url', 'mcp_url', 'key_file', 'app_url']):
                    database_entry = {
                        'name': db_name,
                        'type': db_name,  # Use the section name as the type
                        **db_config
                    }
                    databases.append(database_entry)
                    logger.info(f"Added database from config: {db_name}")
                else:
                    logger.debug(f"Skipping {db_name} - no connection information found")
                    
        except Exception as e:
            logger.error(f"Failed to load databases from config.yaml: {e}")
            # Fallback to current database only if config loading fails
            try:
                current_db = {
                    'name': self.settings.DB_TYPE.lower(),
                    'type': self.settings.DB_TYPE.lower(),
                    'uri': self.settings.connection_uri
                }
                databases.append(current_db)
                logger.info(f"Fallback: added current database {self.settings.DB_TYPE}")
            except Exception as fallback_error:
                logger.error(f"Fallback failed: {fallback_error}")
                
        logger.info(f"Total databases configured: {len(databases)}")
        return databases
        
    def _get_connection_details(self, db_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get sanitized connection details for display"""
        details = {}
        
        # Add safe details (no passwords/secrets)
        safe_keys = ['host', 'port', 'database', 'collection', 'property_id', 'api_version', 'app_url']
        
        for key in safe_keys:
            if key in db_config:
                details[key] = db_config[key]
                
        # Add database type
        if 'type' in db_config:
            details['type'] = db_config['type']
            
        # For URIs, mask credentials
        uri = db_config.get('uri') or self._get_database_uri(db_config)
        if uri:
            details['connection_uri'] = self._mask_uri(uri)
            
        # Add specific details for different database types
        db_type = db_config.get('type', '').lower()
        
        if db_type == 'qdrant':
            details['collection'] = db_config.get('collection', 'unknown')
            details['grpc_port'] = db_config.get('grpc_port')
            details['prefer_grpc'] = db_config.get('prefer_grpc', False)
            
        elif db_type == 'ga4':
            details['scopes'] = len(db_config.get('scopes', []))
            
        elif db_type == 'slack':
            details['history_days'] = db_config.get('history_days')
            details['update_frequency'] = db_config.get('update_frequency')
            
        elif db_type == 'shopify':
            details['api_version'] = db_config.get('api_version')
            
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
                
        return details
        
    def _get_database_uri(self, db_config: Dict[str, Any]) -> str:
        """Get the connection URI for a database configuration"""
        # Direct URI is preferred
        if 'uri' in db_config and db_config['uri']:
            return db_config['uri']
            
        db_type = db_config.get('type', '').lower()
        
        # Handle different database types
        if db_type in ['postgres', 'postgresql']:
            if all(key in db_config for key in ['host', 'port', 'database', 'user', 'password']):
                ssl_mode = db_config.get('ssl_mode', 'disable')
                return f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?sslmode={ssl_mode}"
                
        elif db_type in ['mongodb', 'mongo']:
            if all(key in db_config for key in ['host', 'port', 'database', 'user', 'password']):
                auth_source = db_config.get('auth_source', 'admin')
                return f"mongodb://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?authSource={auth_source}"
                
        elif db_type == 'qdrant':
            if 'host' in db_config and 'port' in db_config:
                return f"http://{db_config['host']}:{db_config['port']}"
                
        elif db_type == 'slack':
            if 'mcp_url' in db_config:
                return db_config['mcp_url']
            elif 'url' in db_config:
                return db_config['url']
                
        elif db_type == 'shopify':
            if 'app_url' in db_config:
                return db_config['app_url']
            elif 'url' in db_config:
                return db_config['url']
                
        elif db_type == 'ga4':
            if 'property_id' in db_config:
                return f"ga4://{db_config['property_id']}"
                
        # Fallback: look for any URL-like field
        for key in ['url', 'endpoint', 'connection_string']:
            if key in db_config and db_config[key]:
                return db_config[key]
                
        return ""
        
    def _mask_uri(self, uri: str) -> str:
        """Mask sensitive information in URI for logging"""
        if not uri:
            return uri
            
        # For URIs with usernames/passwords, mask them
        if '@' in uri and '://' in uri:
            try:
                protocol, rest = uri.split('://', 1)
                if '@' in rest:
                    creds, host_part = rest.split('@', 1)
                    return f"{protocol}://***:***@{host_part}"
            except:
                pass
                
        return uri
        
    def get_all_statuses(self) -> Dict[str, DatabaseStatus]:
        """Get all cached database statuses"""
        with self._cache_lock:
            return self._status_cache.copy()
            
    def get_status(self, db_name: str) -> Optional[DatabaseStatus]:
        """Get status for a specific database"""
        with self._cache_lock:
            return self._status_cache.get(db_name)
            
    def get_available_databases(self, user_id: Optional[str] = None) -> List[DatabaseStatus]:
        """Get databases available to a specific user"""
        all_statuses = self.get_all_statuses()
        
        # Filter by user permissions (implement user-specific logic here)
        available = []
        for status in all_statuses.values():
            if self._user_has_access(user_id, status.name):
                available.append(status)
                
        return available
        
    def _user_has_access(self, user_id: Optional[str], db_name: str) -> bool:
        """Check if user has access to specific database"""
        # Implement user permission logic here
        # For now, return True for all users
        # In production, this would check user roles, enterprise settings, etc.
        return True
        
    async def force_check(self, db_name: Optional[str] = None) -> Dict[str, DatabaseStatus]:
        """Force immediate check of specific database or all databases"""
        if db_name:
            # Check specific database
            databases = self._get_configured_databases()
            db_config = next((db for db in databases if db['name'] == db_name), None)
            
            if not db_config:
                raise ValueError(f"Database {db_name} not found in configuration")
                
            status = await self._check_single_database(db_name, db_config)
            
            with self._cache_lock:
                self._status_cache[db_name] = status
                
            return {db_name: status}
        else:
            # Check all databases
            return await self.check_all_databases()
            
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        all_statuses = self.get_all_statuses()
        
        total = len(all_statuses)
        online = sum(1 for s in all_statuses.values() if s.status == 'online')
        offline = sum(1 for s in all_statuses.values() if s.status == 'offline')
        errors = sum(1 for s in all_statuses.values() if s.status == 'error')
        
        return {
            'total_databases': total,
            'online': online,
            'offline': offline,
            'errors': errors,
            'last_check': self._last_full_check.isoformat() if self._last_full_check else None,
            'uptime_percentage': (online / total * 100) if total > 0 else 0
        }

# Global instance
_availability_service: Optional[DatabaseAvailabilityService] = None

def get_availability_service() -> DatabaseAvailabilityService:
    """Get the global database availability service instance"""
    global _availability_service
    if _availability_service is None:
        from ..config.settings import Settings
        settings = Settings()
        _availability_service = DatabaseAvailabilityService(settings)
    return _availability_service

async def initialize_availability_service():
    """Initialize and start the availability service"""
    service = get_availability_service()
    await service.start_monitoring()
    return service 