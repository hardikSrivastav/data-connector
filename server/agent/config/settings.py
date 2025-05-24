from pydantic import validator, BaseSettings
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv
from pathlib import Path
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Import the config loader
try:
    from .config_loader import load_config, get_database_uri, get_default_database_type, load_auth_config
except ImportError:
    # If we can't import directly, try the absolute import
    try:
        from agent.config.config_loader import load_config, get_database_uri, get_default_database_type, load_auth_config
    except ImportError:
        # Define stubs for when the module can't be imported
        def load_config(): return {}
        def get_database_uri(db_type): return None
        def get_default_database_type(): return "postgres"
        def load_auth_config(): return {}

# Load environment variables from .env file if present
load_dotenv()

# Load YAML configuration
yaml_config = load_config()
logger.info(f"Loaded YAML config: {yaml_config}")

# Load auth configuration
auth_config = load_auth_config()
logger.info(f"Loaded auth config: {auth_config}")

# Set default database type
default_db = get_default_database_type()
logger.info(f"Default database type: {default_db}")

class Settings(BaseSettings):
    # Database Settings
    DB_HOST: str = yaml_config.get('postgres', {}).get('host', os.getenv('DB_HOST', 'localhost'))
    DB_PORT: int = yaml_config.get('postgres', {}).get('port', int(os.getenv('DB_PORT', 5432)))
    DB_NAME: str = yaml_config.get('postgres', {}).get('database', os.getenv('DB_NAME', 'dataconnector'))
    DB_USER: str = yaml_config.get('postgres', {}).get('user', os.getenv('DB_USER', 'dataconnector'))
    DB_PASS: str = yaml_config.get('postgres', {}).get('password', os.getenv('DB_PASS', 'dataconnector'))
    SSL_MODE: Optional[str] = yaml_config.get('postgres', {}).get('ssl_mode', os.getenv('SSL_MODE'))
    
    # Multi-Database Support
    DB_URI: Optional[str] = None  # Don't set a default here, override in connection_uri
    DB_TYPE: str = default_db
    
    # MongoDB Settings
    MONGO_INITDB_ROOT_USERNAME: Optional[str] = yaml_config.get('mongodb', {}).get('user', os.getenv('MONGO_ROOT_USERNAME', 'dataconnector'))
    MONGO_INITDB_ROOT_PASSWORD: Optional[str] = yaml_config.get('mongodb', {}).get('password', os.getenv('MONGO_ROOT_PASSWORD', 'dataconnector'))
    MONGO_HOST: Optional[str] = yaml_config.get('mongodb', {}).get('host', os.getenv('MONGO_HOST', 'localhost'))
    MONGO_PORT: Optional[int] = yaml_config.get('mongodb', {}).get('port', int(os.getenv('MONGO_PORT', 27000)))
    MONGODB_DB_NAME: Optional[str] = yaml_config.get('mongodb', {}).get('database', os.getenv('MONGODB_DB_NAME', 'dataconnector_mongo'))
    MONGODB_URI: Optional[str] = yaml_config.get('mongodb', {}).get('uri', os.getenv('MONGODB_URI'))
    
    # If MongoDB URI is not set, construct it from parts
    if not MONGODB_URI:
        MONGODB_URI = f"mongodb://{MONGO_INITDB_ROOT_USERNAME}:{MONGO_INITDB_ROOT_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGODB_DB_NAME}?authSource=admin"
    
    # Qdrant Vector Database Settings
    QDRANT_HOST: Optional[str] = yaml_config.get('qdrant', {}).get('host', os.getenv('QDRANT_HOST', 'localhost'))
    QDRANT_PORT: Optional[int] = yaml_config.get('qdrant', {}).get('port', int(os.getenv('QDRANT_PORT', 7500)))
    QDRANT_GRPC_PORT: Optional[int] = yaml_config.get('qdrant', {}).get('grpc_port', int(os.getenv('QDRANT_GRPC_PORT', 7501)))
    QDRANT_API_KEY: Optional[str] = yaml_config.get('qdrant', {}).get('api_key', os.getenv('QDRANT_API_KEY'))
    QDRANT_COLLECTION: Optional[str] = yaml_config.get('qdrant', {}).get('collection', os.getenv('QDRANT_COLLECTION', 'corporate_knowledge'))
    QDRANT_URI: Optional[str] = yaml_config.get('qdrant', {}).get('uri', os.getenv('QDRANT_URI'))
    QDRANT_PREFER_GRPC: bool = yaml_config.get('qdrant', {}).get('prefer_grpc', os.getenv('QDRANT_PREFER_GRPC', 'false').lower() == 'true')
    
    # If Qdrant URI is not set, construct it from parts
    if not QDRANT_URI:
        QDRANT_URI = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
    
    # Slack Integration Settings
    SLACK_MCP_URL: Optional[str] = yaml_config.get('slack', {}).get('mcp_url', os.getenv('SLACK_MCP_URL', 'http://localhost:8500'))
    SLACK_HISTORY_DAYS: int = yaml_config.get('slack', {}).get('history_days', int(os.getenv('SLACK_HISTORY_DAYS', 30)))
    SLACK_UPDATE_FREQUENCY: int = yaml_config.get('slack', {}).get('update_frequency', int(os.getenv('SLACK_UPDATE_FREQUENCY', 6)))
    SLACK_URI: Optional[str] = yaml_config.get('slack', {}).get('uri', os.getenv('SLACK_URI', SLACK_MCP_URL))
    
    # Shopify Integration Settings
    SHOPIFY_APP_URL: Optional[str] = yaml_config.get('shopify', {}).get('app_url', os.getenv('SHOPIFY_APP_URL', 'https://ceneca.ai'))
    SHOPIFY_API_VERSION: Optional[str] = yaml_config.get('shopify', {}).get('api_version', os.getenv('SHOPIFY_API_VERSION', '2025-04'))
    SHOPIFY_APP_CLIENT_ID: Optional[str] = yaml_config.get('shopify', {}).get('client_id', os.getenv('SHOPIFY_APP_CLIENT_ID'))
    SHOPIFY_APP_CLIENT_SECRET: Optional[str] = yaml_config.get('shopify', {}).get('client_secret', os.getenv('SHOPIFY_APP_CLIENT_SECRET'))
    SHOPIFY_WEBHOOK_SECRET: Optional[str] = yaml_config.get('shopify', {}).get('webhook_secret', os.getenv('SHOPIFY_WEBHOOK_SECRET'))
    SHOPIFY_URI: Optional[str] = yaml_config.get('shopify', {}).get('uri', os.getenv('SHOPIFY_URI', SHOPIFY_APP_URL))
    
    # Vector Embedding Settings
    VECTOR_EMBEDDING_PROVIDER: str = yaml_config.get('vector_db', {}).get('embedding', {}).get('provider', os.getenv('VECTOR_EMBEDDING_PROVIDER', 'openai'))
    VECTOR_EMBEDDING_MODEL: Optional[str] = yaml_config.get('vector_db', {}).get('embedding', {}).get('model', os.getenv('VECTOR_EMBEDDING_MODEL', 'text-embedding-ada-002'))
    VECTOR_EMBEDDING_DIMENSIONS: int = yaml_config.get('vector_db', {}).get('embedding', {}).get('dimensions', int(os.getenv('VECTOR_EMBEDDING_DIMENSIONS', 1536)))
    VECTOR_EMBEDDING_API_KEY: Optional[str] = yaml_config.get('vector_db', {}).get('embedding', {}).get('api_key', os.getenv('VECTOR_EMBEDDING_API_KEY', os.getenv('LLM_API_KEY')))
    VECTOR_EMBEDDING_ENDPOINT: Optional[str] = yaml_config.get('vector_db', {}).get('embedding', {}).get('endpoint', os.getenv('VECTOR_EMBEDDING_ENDPOINT'))
    VECTOR_EMBEDDING_RESPONSE_FIELD: Optional[str] = yaml_config.get('vector_db', {}).get('embedding', {}).get('response_field', os.getenv('VECTOR_EMBEDDING_RESPONSE_FIELD', 'embedding'))
    
    # Debug/Override Settings
    DB_DSN_OVERRIDE: Optional[str] = os.getenv('DB_DSN_OVERRIDE')
    
    # Authentication Settings (from auth-config.yaml)
    AUTH_ENABLED: bool = auth_config.get('sso', {}).get('enabled', False)
    AUTH_PROTOCOL: Optional[str] = auth_config.get('sso', {}).get('default_protocol', 'oidc')
    
    # OIDC Settings (from auth-config.yaml)
    OIDC_PROVIDER: Optional[str] = auth_config.get('sso', {}).get('oidc', {}).get('provider')
    OIDC_CLIENT_ID: Optional[str] = auth_config.get('sso', {}).get('oidc', {}).get('client_id')
    OIDC_CLIENT_SECRET: Optional[str] = auth_config.get('sso', {}).get('oidc', {}).get('client_secret')
    OIDC_ISSUER: Optional[str] = auth_config.get('sso', {}).get('oidc', {}).get('issuer')
    OIDC_DISCOVERY_URL: Optional[str] = auth_config.get('sso', {}).get('oidc', {}).get('discovery_url')
    OIDC_REDIRECT_URI: Optional[str] = auth_config.get('sso', {}).get('oidc', {}).get('redirect_uri')
    OIDC_SCOPES: List[str] = auth_config.get('sso', {}).get('oidc', {}).get('scopes', ["openid", "email", "profile"])
    OIDC_CLAIMS_MAPPING: Dict[str, str] = auth_config.get('sso', {}).get('oidc', {}).get('claims_mapping', {})
    
    # Role mappings (from auth-config.yaml)
    ROLE_MAPPINGS: Dict[str, str] = auth_config.get('role_mappings', {})
    
    # Network Security (for future VPN integration)
    ALLOWED_CIDR_BLOCKS: Optional[str] = None  # Comma-separated list of allowed IP ranges
    
    # LLM Configuration - Local
    MODEL_PATH: Optional[str] = None
    MODEL_TYPE: Optional[str] = None  # "llama2" or "gpt4all"
    DEVICE: Optional[str] = "cpu"  # "cpu" or "gpu"
    
    # LLM Configuration - Cloud
    LLM_API_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = None
    
    # Anthropic Configuration
    ANTHROPIC_API_URL: Optional[str] = "https://api.anthropic.com"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL_NAME: Optional[str] = "claude-3-opus-20240229"
    
    # Agent Settings
    AGENT_PORT: int = 8080
    LOG_LEVEL: str = "info"  # "info", "debug", or "error"
    CACHE_PATH: Optional[str] = None
    WIPE_ON_EXIT: bool = False
    
    # Redis Cache Settings
    REDIS_HOST: Optional[str] = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = True  # Set to False to disable Redis and use file-based caching
    REDIS_TTL: int = 3600  # Default cache TTL in seconds (1 hour)
    
    # Analysis Settings
    MAX_ANALYSIS_STEPS: int = 10
    MAX_ROWS_DIRECT: int = 100000  # Max rows for direct query without sampling
    DEFAULT_SAMPLE_SIZE: int = 1000  # Default sample size for large datasets
    MAX_QUERY_TIMEOUT: int = 60  # Maximum query timeout in seconds
    
    # Application data directory
    APP_DATA_DIR: Optional[str] = None
    
    # Google Analytics 4 Settings
    GA4_KEY_FILE: Optional[Path] = yaml_config.get('ga4', {}).get('key_file', os.getenv('GA4_KEY_FILE'))
    GA4_PROPERTY_ID: int = yaml_config.get('ga4', {}).get('property_id', int(os.getenv('GA4_PROPERTY_ID', 0)))
    GA4_SCOPES: List[str] = yaml_config.get('ga4', {}).get('scopes', os.getenv('GA4_SCOPES', 'https://www.googleapis.com/auth/analytics.readonly').split(','))
    GA4_TOKEN_CACHE_DB: Optional[Path] = yaml_config.get('ga4', {}).get('token_cache_db', os.getenv('GA4_TOKEN_CACHE_DB'))
    
    def get_app_dir(self) -> str:
        """
        Returns the directory where application data should be stored.
        
        If APP_DATA_DIR is set, uses that directory.
        Otherwise, creates a directory in the user's home directory.
        """
        if self.APP_DATA_DIR:
            app_dir = Path(self.APP_DATA_DIR)
        else:
            # Use a directory in the user's home folder
            app_dir = Path.home() / ".data-connector"
            
        # Ensure the directory exists
        app_dir.mkdir(parents=True, exist_ok=True)
        
        return str(app_dir)
    
    @property
    def is_auth_enabled(self) -> bool:
        """Check if authentication is properly configured and enabled"""
        if not self.AUTH_ENABLED:
            return False
            
        if self.AUTH_PROTOCOL == 'oidc':
            # Check if required OIDC settings are present
            return bool(self.OIDC_PROVIDER and self.OIDC_CLIENT_ID and self.OIDC_CLIENT_SECRET and 
                        self.OIDC_ISSUER and self.OIDC_REDIRECT_URI)
        
        # Default to disabled if protocol not recognized
        return False
    
    @property
    def db_dsn(self) -> str:
        """
        Constructs the PostgreSQL connection string from settings
        """ 
        base_dsn = f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        
        if self.SSL_MODE:
            return f"{base_dsn}?sslmode={self.SSL_MODE}"
        
        return base_dsn
    
    @property
    def connection_uri(self) -> str:
        """
        Returns the appropriate database connection URI based on configured settings.
        Used by the orchestrator to determine which adapter to use.
        
        Priority:
        1. Direct DB_URI override (any database type)
        2. DB-specific URIs (MongoDB, etc.) from YAML config
        3. DB-specific URIs from environment
        4. PostgreSQL DSN constructed from individual settings
        """
        # Direct URI override takes highest precedence
        if self.DB_URI:
            logger.info(f"Using DB_URI override: {self.DB_URI}")
            return self.DB_URI
        
        # Load fresh config to ensure we have latest settings
        config = load_config()
        logger.info(f"Current DB_TYPE: {self.DB_TYPE}")
        logger.info(f"Loaded config for DB_TYPE: {config.get(self.DB_TYPE.lower(), {})}")
        
        # Get URI for the current database type from YAML config
        if self.DB_TYPE.lower() in config and 'uri' in config[self.DB_TYPE.lower()]:
            uri = config[self.DB_TYPE.lower()]['uri']
            logger.info(f"Using {self.DB_TYPE} URI from YAML: {uri}")
            return uri
            
        # DB type-specific URIs from environment variables or class properties
        if self.DB_TYPE.lower() == "mongodb" and self.MONGODB_URI:
            logger.info(f"Using MONGODB_URI: {self.MONGODB_URI}")
            return self.MONGODB_URI
        elif self.DB_TYPE.lower() == "postgres" and self.db_dsn:
            logger.info(f"Using db_dsn: {self.db_dsn}")
            return self.db_dsn
        elif self.DB_TYPE.lower() == "qdrant" and self.QDRANT_URI:
            logger.info(f"Using QDRANT_URI: {self.QDRANT_URI}")
            return self.QDRANT_URI
        elif self.DB_TYPE.lower() == "slack" and self.SLACK_URI:
            logger.info(f"Using SLACK_URI: {self.SLACK_URI}")
            return self.SLACK_URI
        elif self.DB_TYPE.lower() == "shopify" and self.SHOPIFY_URI:
            logger.info(f"Using SHOPIFY_URI: {self.SHOPIFY_URI}")
            return self.SHOPIFY_URI
        elif self.DB_TYPE.lower() == "ga4" and self.GA4_KEY_FILE:
            ga4_uri = f"ga4://{self.GA4_PROPERTY_ID}"
            logger.info(f"Using GA4 URI: {ga4_uri}")
            return ga4_uri
            
        # Check for DB_DSN_OVERRIDE only if db_type is 'postgres' to avoid overriding other db types
        if self.DB_TYPE.lower() == "postgres" and self.DB_DSN_OVERRIDE:
            logger.info(f"Using DB_DSN_OVERRIDE: {self.DB_DSN_OVERRIDE}")
            return self.DB_DSN_OVERRIDE
        
        # Fall back to PostgreSQL DSN only for postgres db type
        if self.DB_TYPE.lower() == "postgres":
            logger.info(f"Falling back to PostgreSQL DSN: {self.db_dsn}")    
            return self.db_dsn
        
        # If we get here, we couldn't determine a URI - log an error
        logger.error(f"No connection URI available for DB_TYPE: {self.DB_TYPE}")
        return ""
    
    @validator("LLM_API_KEY")
    def validate_api_key_if_url_provided(cls, v, values):
        """Validate that API key is provided if API URL is set"""
        if values.get("LLM_API_URL") and not v:
            # Check if OPENAI_API_KEY is set in environment
            openai_key = os.environ.get("OPENAI_API_KEY")
            if openai_key:
                return openai_key
            raise ValueError("LLM_API_KEY must be provided when LLM_API_URL is set")
        return v
    
    @validator("MODEL_TYPE")
    def validate_model_type_if_path_provided(cls, v, values):
        """Validate that model type is provided if model path is set"""
        if values.get("MODEL_PATH") and not v:
            raise ValueError("MODEL_TYPE must be provided when MODEL_PATH is set")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
