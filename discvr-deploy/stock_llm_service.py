"""
Stock LLM Service

AI-powered stock analysis service following the exact Investment Bot architecture.
Uses MongoDB, PostgreSQL, and Redis for data access (same as Investment Bot).
"""

import os
import json
import time
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from functools import lru_cache

import boto3
import psycopg2
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import redis

from src.services.conversation_manager import ConversationManager
from src.services.shared_streaming_service import get_shared_streaming_service
from src.services.streaming_events import StreamingEventTypes, ProcessingStatus, create_processing_event, create_tool_execution_event, create_error_event
from .stock_tools_manager import StockToolsManager
from .stock_chart_generator import StockChartGenerator
from .cache_manager import StockCacheManager
from src.utils.logger import get_logger

logger = get_logger(__name__, group_name="us_stock_bot")

# TOKEN CONFIGURATION CONSTANTS
MAX_TOKENS_STOCK_LLM = 10000  # Increased for comprehensive data display
TEMPERATURE_STOCK_LLM = 0.1
MODEL_ID_STOCK_LLM = "anthropic.claude-3-haiku-20240307-v1:0"

# INDIAN STOCK MARKET INSTRUCTIONS
INDIAN_STOCK_INSTRUCTIONS = """
🇮🇳 **INDIAN STOCK MARKET HANDLING**

When processing queries specifically about Indian companies/stocks:

1. **Exchange Suffixes**:
   • For BSE (Bombay Stock Exchange) stocks: Append '.BO'
     Example: RELIANCE.BO, TCS.BO, HDFCBANK.BO
   
   • For NSE (National Stock Exchange) stocks: Append '.NS'
     Example: RELIANCE.NS, TCS.NS, HDFCBANK.NS

2. **Handling Rules**:
   • ALWAYS include both BSE and NSE tickers when available
   • Format: "{SYMBOL}.BO" for BSE and "{SYMBOL}.NS" for NSE
   • Maintain exact case sensitivity of symbols (usually UPPERCASE)
   • For dual-listed stocks, prefer NSE (.NS) for primary analysis

3. **Common Examples**:
   • Reliance Industries: RELIANCE.BO / RELIANCE.NS
   • TCS: TCS.BO / TCS.NS
   • HDFC Bank: HDFCBANK.BO / HDFCBANK.NS
   • Infosys: INFY.BO / INFY.NS

4. **Data Priority**:
   • Primary: Use NSE (.NS) data for main analysis
   • Secondary: Include BSE (.BO) data for comparison
   • Always mention both exchanges in results

5. **Special Cases**:
   • Some stocks may be listed on only one exchange
   • Verify exchange availability before analysis
   • Handle missing exchange data gracefully

Remember: Indian stock symbols require these specific suffixes for accurate data retrieval and analysis.
"""


class StockLLMService:
    """
    Stock LLM Service - Follows Investment Bot Architecture Exactly
    
    Features:
    - AWS Bedrock Claude integration (same as investment bot)
    - MongoDB/PostgreSQL/Redis data access (same as investment bot)
    - Built-in caching (same pattern as investment bot)
    - Stock-specific tools and prompts
    - Shared conversation manager
    """
    
    def __init__(self):
        # AWS Bedrock client (IDENTICAL to investment bot)
        try:
            self.bedrock_runtime = boto3.client(
                service_name='bedrock-runtime',
                region_name='ap-south-1'
            )
            logger.info("✅ AWS Bedrock client initialized for Stock Bot")
        except Exception as e:
            logger.error(f"❌ AWS Bedrock initialization failed: {e}")
            self.bedrock_runtime = None
        
        # Model configuration (SAME as investment bot)
        self.model_id = MODEL_ID_STOCK_LLM
        self.max_tokens = MAX_TOKENS_STOCK_LLM
        self.temperature = TEMPERATURE_STOCK_LLM
        
        # Database connections (IDENTICAL pattern to investment bot)
        self.mongo_client = None
        self.mongo_db = None
        self.postgres_conn = None
        self.redis_client = None
        
        # News database connection (separate client for news summaries)
        self.newsdbclient = None
        self.news_db = None
        
        # Stock-specific caching (SAME pattern as investment bot)
        self.stock_cache = {}
        self.cache_last_updated = None
        self.cache_refresh_interval = 300  # 5 minutes
        
        # Tools manager (SAME pattern as investment bot)
        self.tools_manager = StockToolsManager(self)
        
        # 🔗 MUTUAL FUND SERVICE CONNECTION (For Portfolio Tools Delegation)
        self.llm_service = None  # Will be initialized later to access MF tools
        
        # Chart generator (NEW for stock-specific visualizations)
        self.chart_generator = StockChartGenerator()
        
        # Conversation manager (SHARED with investment bot)
        self.conversation_manager = None
        
        # Cache manager (NEW - separated for better organization)
        self.cache_manager = None
        
        # Shared streaming service (NEW - eliminates code duplication)
        self.shared_streaming = get_shared_streaming_service()
        
        # Intelligent Query Agent (NEW - combines intent analysis and field projection)
        from .intelligent_query_agent import get_intelligent_query_agent
        self.intelligent_agent = get_intelligent_query_agent()
        
        # Pass reference to self for shared field knowledge
        self.intelligent_agent.stock_llm_service = self
        
        # Bootstrap intelligence cache (PRE-LOADED at startup)
        self.bootstrap_intelligence = None
        self.market_intelligence = None
        self.bootstrap_last_updated = None
        
        # Pre-built system prompt (MINIMAL CHANGE OPTIMIZATION)
        self.prebuilt_system_prompt = None
        
        # Initialize all connections
        self._initialize_connections()
        
        # Load database schema (essential for accurate querying)
        self.stock_schema = self._get_stock_metrics_flat_schema()
        logger.info("✅ Stock database schema loaded with all 348 fields")
        
        # Initialize cache manager and load initial cache
        self._initialize_cache_manager()
        
        # Pre-load bootstrap intelligence at startup (CRITICAL OPTIMIZATION)
        self._preload_bootstrap_intelligence()
        
        # Initialize query agent with schema and bootstrap context
        self._initialize_query_agent_context()
        
        # Start background cache refresh
        self._start_background_cache_refresh()
        
        # 🔗 Initialize MF service connection for portfolio tools delegation
        self._initialize_mf_service_connection()
        
        logger.info("🚀 StockLLMService initialized successfully")
    
    def _initialize_connections(self):
        """Initialize database connections - IDENTICAL to investment bot pattern"""
        try:
            # MongoDB connection (same as investment bot)
            mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
            self.mongo_client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50
            )
            self.mongo_db = self.mongo_client.get_database("financial_data")
            
            # Test connection
            self.mongo_client.admin.command('ping')
            logger.info("✅ MongoDB connected for Stock Bot")
            
            # Async MongoDB for conversation manager
            async_mongo_client = AsyncIOMotorClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000
            )
            self.conversation_manager = ConversationManager(async_mongo_client)
            logger.info("✅ ConversationManager initialized for Stock Bot")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.mongo_client = None
        
        try:
            # PostgreSQL connection (IDENTICAL to investment bot)
            postgres_config = {
                'host': os.getenv('PG_HOST', 'localhost'),
                'port': os.getenv('PG_PORT', '5432'),
                'database': os.getenv('PG_DATABASE', 'Finance_Data'),
                'user': os.getenv('PG_USER', 'postgres'),
                'password': os.getenv('PG_PASSWORD', 'sameer')  # Same fallback as investment bot
            }
            
            self.postgres_conn = psycopg2.connect(**postgres_config)
            self.postgres_conn.autocommit = True
            logger.info("✅ PostgreSQL connected for Stock Bot")
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            self.postgres_conn = None
        
        try:
            # Redis connection using proper RedisHandler
            from src.database.redis_handler import get_redis_handler
            self.redis_client = get_redis_handler()
            
            # Test connection
            if self.redis_client.ping():
                logger.info("✅ Redis connected for Stock Bot")
            else:
                raise Exception("Redis ping failed")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_client = None
        
        try:
            # News database connection (separate client for news summaries)
            mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
            news_db_name = os.getenv('MONGODB_NEWSDB', 'news_summary')
            
            self.newsdbclient = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=10
            )
            
            # Test connection
            self.newsdbclient.admin.command('ping')
            self.news_db = self.newsdbclient.get_database(news_db_name)
            
            logger.info(f"✅ News database connected: {news_db_name}")
            
        except Exception as e:
            logger.error(f"❌ News database connection failed: {e}")
            self.newsdbclient = None
            self.news_db = None
    
    def _initialize_cache_manager(self):
        """Initialize the cache manager with database connections"""
        try:
            # Only pass Redis client if it's actually available
            redis_client = self.redis_client if self.redis_client else None
            
            self.cache_manager = StockCacheManager(
                mongo_client=self.mongo_client,
                mongo_db=self.mongo_db,
                newsdbclient=self.newsdbclient,
                news_db=self.news_db,
                redis_client=redis_client
            )
            
            # Load initial cache
            self.stock_cache = self.cache_manager.load_stock_cache()
            self.cache_last_updated = self.cache_manager.cache_last_updated
            
            logger.info("✅ Cache manager initialized successfully")
            if redis_client is None:
                logger.warning("⚠️ Cache manager initialized without Redis client")
            
        except Exception as e:
            logger.error(f"❌ Cache manager initialization failed: {e}")
            self.cache_manager = None
            # Create a temporary cache manager for fallback
            temp_cache_manager = StockCacheManager()
            self.stock_cache = temp_cache_manager._get_fallback_stock_cache()
    
    def _load_stock_cache(self):
        """Load stock cache using cache manager"""
        try:
            if self.cache_manager:
                logger.info("🔄 Refreshing stock cache via cache manager...")
                self.stock_cache = self.cache_manager.load_stock_cache()
                self.cache_last_updated = self.cache_manager.cache_last_updated
                
                cache_size = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in self.stock_cache.values())
                logger.info(f"✅ Stock cache refreshed - {cache_size} items across {len(self.stock_cache)} categories")
            else:
                logger.warning("⚠️ Cache manager not available, using fallback cache")
                temp_cache_manager = StockCacheManager()
                self.stock_cache = temp_cache_manager._get_fallback_stock_cache()
                self.cache_last_updated = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Stock cache loading failed: {e}")
            temp_cache_manager = StockCacheManager()
            self.stock_cache = temp_cache_manager._get_fallback_stock_cache()
            self.cache_last_updated = datetime.now()
    

    
    def _is_cache_stale(self) -> bool:
        """Check if cache is stale using cache manager"""
        if self.cache_manager:
            return self.cache_manager.is_cache_stale()
        else:
            # Fallback logic when cache manager is not available
            if self.cache_last_updated is None:
                return True
            return (datetime.now() - self.cache_last_updated).seconds > self.cache_refresh_interval
    
    def _start_background_cache_refresh(self):
        """Start background cache refresh - SAME pattern as investment bot"""
        def refresh_worker():
            while True:
                try:
                    time.sleep(self.cache_refresh_interval)
                    if self._is_cache_stale():
                        logger.info("🔄 Refreshing stock cache in background...")
                        self._load_stock_cache()
                        # Also refresh bootstrap intelligence and rebuild system prompt when cache refreshes
                        self._preload_bootstrap_intelligence()
                except Exception as e:
                    logger.error(f"Background cache refresh error: {e}")
        
        refresh_thread = threading.Thread(target=refresh_worker, daemon=True)
        refresh_thread.start()
        logger.info("✅ Background cache refresh started")

    def _preload_bootstrap_intelligence(self):
        """
        🚀 PRE-LOAD bootstrap intelligence at service startup
        This eliminates per-query generation and improves response time
        """
        try:
            logger.info("🧠 Pre-loading bootstrap intelligence...")
            
            # Load bootstrap data from cache manager
            if self.cache_manager and hasattr(self.cache_manager, 'get_bootstrap_intelligence'):
                self.bootstrap_intelligence = self.cache_manager.get_bootstrap_intelligence()
                logger.info("✅ Bootstrap intelligence loaded from cache manager")
            else:
                logger.warning("⚠️ Cache manager unavailable, using fallback bootstrap")
                self.bootstrap_intelligence = self._get_fallback_bootstrap_data()
            
            # Load market intelligence (MongoDB-powered)
            self.market_intelligence = self._get_high_priority_bootstrap_data()
            
            # Mark as updated
            self.bootstrap_last_updated = datetime.now()
            
            # Log token count for monitoring
            total_tokens = len(str(self.bootstrap_intelligence)) + len(str(self.market_intelligence))
            logger.info(f"✅ Bootstrap intelligence pre-loaded: ~{total_tokens // 4} tokens estimated")
            
            # Build system prompt once at startup (MINIMAL CHANGE OPTIMIZATION)
            self._build_prebuilt_system_prompt()
            
        except Exception as e:
            logger.error(f"❌ Bootstrap intelligence pre-loading failed: {e}")
            # Fallback to minimal bootstrap
            self.bootstrap_intelligence = self._get_fallback_bootstrap_data()
            self.market_intelligence = self._get_fallback_bootstrap_intelligence()
            self.bootstrap_last_updated = datetime.now()
    
    def _get_fallback_bootstrap_data(self) -> Dict[str, Any]:
        """Fallback bootstrap data when cache manager unavailable"""
        return {
            'timestamp': datetime.now().isoformat(),
            'market_overview': {
                'status': 'Loading',
                'major_indices': [],
                'market_sentiment': 'neutral',
                'trading_session': 'unknown'
            },
            'dynamic_sectors': {
                'by_performance': [],
                'sector_list': ['Technology', 'Healthcare', 'Financials'],
                'total_sectors': 3
            },
            'market_highlights': {
                'top_gainers': [],
                'top_losers': [],
                'high_volume': []
            },
            'cache_status': {
                'popular_stocks_count': 0,
                'sectors_tracked': 0,
                'last_refresh': None,
                'freshness_score': 0.0
            }
        }
    
    def _get_comprehensive_field_guide(self) -> str:
        """
        Generate comprehensive field guide using the detailed schema
        SINGLE SOURCE OF TRUTH: Uses _get_stock_metrics_flat_schema() data
        """
        # Get the comprehensive schema
        schema = self._get_stock_metrics_flat_schema()
        
        # Build field guide using schema data
        return f"""
🚨 CRITICAL MONGODB QUERY RULES 🚨

=== DATA TYPE OPERATORS ===
• STRING FIELDS: Use exact matches or $in - Example: {{"sector": "Technology"}}
• NUMBER FIELDS: Use $gte, $lte, $gt, $lt - Example: {{"pe_ratio": {{"$lt": 15}}}}
• BOOLEAN FIELDS: Use true/false - Example: {{"is_large_cap": true}}
• PERCENTAGE FIELDS: Use decimals - Example: {{"revenue_growth_1y": {{"$gt": 0.1}}}} (>10%)

=== CRITICAL QUERY EXAMPLES ===
Use ticker for any stock/ticker query like finding the stock apple as {{'ticker': 'AAPL'}} 
✅ Large cap tech stocks: {{"sector": "Technology", "is_large_cap": true}}
✅ Undervalued stocks: {{"pe_ratio": {{"$lt": 15}}, "is_undervalued": true}}
✅ High growth stocks: {{"revenue_growth_1y": {{"$gt": 0.2}}}}
✅ Dividend stocks: {{"is_dividend_stock": true, "dividend_yield": {{"$gt": 0.02}}}}
✅ Profitable companies: {{"is_profitable": true, "net_margin": {{"$gt": 0.1}}}}

=== SECTOR VALUES ===
"Technology", "Healthcare", "Financials", "Consumer Discretionary", "Industrials", 
"Energy", "Materials", "Consumer Staples", "Utilities", "Real Estate", "Communication Services"

=== COMPREHENSIVE SCHEMA WITH {schema['total_fields']} FIELDS ===
Collection: {schema['collection_name']}

{schema['description']}
        """    
    
    def _get_stock_metrics_flat_schema(self) -> Dict[str, Any]:
        """
        🏗️ SINGLE SOURCE OF TRUTH: Comprehensive schema for stock_metrics_flat collection
        
        This method contains the COMPLETE AUTHORITATIVE SCHEMA with 496+ fields including:
        - Field names, data types, and value ranges
        - Detailed descriptions and examples
        - All field categories in a flat structure
        
        USED BY:
        - _get_comprehensive_field_guide() → Builds MongoDB query guide
        - IntelligentQueryAgent → Extracts field categories and projections
        - System prompts → Provides complete field reference
        
        ELIMINATES DUPLICATION: All other schema references should use this method.
        """
        return {
            "collection_name": "stock_metrics_flat",
            "total_fields": 496,
            "description": """
**📋 BASIC INFO FIELDS**:
• ticker - Stock ticker symbol (String) - Example: "AAPL"
• company_name - Full company name (String) - Example: "Apple Inc."
• cik - SEC Central Index Key (String) - Example: "0000320193"
• exchange - Primary exchange (String) - Values: "NASDAQ", "NYSE", etc.
• currency - Trading currency (String) - Usually "USD"
• cusip - CUSIP identifier (String) - Example: "037833100"
• isin - International Securities ID (String) - Example: "US0378331005"
• fiscal_year_start_month - Fiscal year start (String) - Example: "January"
• sector - Business sector (String) - Values: "Technology", "Healthcare", "Financials", etc.
• industry - Specific industry (String) - Example: "Consumer Electronics"
• country - Country of incorporation (String) - Usually "US"
• exchange_short_name - Exchange short name (String) - Example: "NASDAQ Global Select"
• is_etf - Is ETF flag (Boolean) - true/false
• ceo - CEO name (String) - Example: "Mr. Timothy D. Cook"
• full_time_employees - Employee count (Integer) - Range: 1-500,000+
• website - Company website (String) - Example: "https://www.apple.com"
• ipo_date - IPO date (String) - Format: "YYYY-MM-DD HH:MM:SS"
• fiscal_year_end - Fiscal year end (String) - Example: "September"
• market_cap - Market capitalization (Integer) - Range: 1M-5T+ (in USD)
• is_actively_trading - Actively trading flag (Boolean) - true/false
• beta - Market beta (Float) - Range: 0.0-3.0+ (1.0 = market average)
• price - Current stock price (Float) - Range: $0.01-$1000+ (in USD)
• vol_avg - Average volume (Integer) - Range: 1,000-500M+ shares
• is_russell_1000 - Russell 1000 member (Boolean) - true/false
• is_russell_2000 - Russell 2000 member (Boolean) - true/false

**📊 ANALYST SENTIMENT FIELDS**:
• strong_buy_count - Strong Buy ratings (Integer) - Range: 0-50+
• buy_count - Buy ratings (Integer) - Range: 0-100+
• hold_count - Hold ratings (Integer) - Range: 0-100+
• sell_count - Sell ratings (Integer) - Range: 0-50+
• strong_sell_count - Strong Sell ratings (Integer) - Range: 0-20+
• total_analysts - Total analysts covering (Integer) - Range: 1-150+
• consensus_rating - Overall rating (String) - Values: "Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"
• consensus_score - Consensus score (Float) - Range: 1.0-5.0 (5.0 = Strong Buy)
• avg_price_target_12m - 12-month price target (Float) - Range: $1-$1000+ (in USD)
• high_price_target - Highest price target (Float) - Range: $1-$1000+ (in USD)
• low_price_target - Lowest price target (Float) - Range: $1-$1000+ (in USD)
• price_target_vs_current - Target vs current (Float) - Range: -0.5 to 2.0+ (ratio)
• price_target_accuracy_score - Target accuracy (Float) - Range: 0.0-1.0 (1.0 = perfect)
• target_price_trend - Price target trend (String) - Values: "increasing", "stable", "decreasing"
• eps_surprise_avg_4q - EPS surprise average 4Q (Float) - Range: -0.5 to 0.5+ (ratio)
• revenue_surprise_avg_4q - Revenue surprise 4Q (Float) - Range: -0.2 to 0.2+ (ratio)
• estimate_revision_trend - Revision trend (String) - Values: "increasing", "stable", "decreasing"
• upgrades_last_30d - Upgrades last 30 days (Integer) - Range: 0-20+
• downgrades_last_30d - Downgrades last 30 days (Integer) - Range: 0-20+
• rating_changes_momentum - Rating momentum (String) - Values: "positive", "neutral", "negative"

**💰 DIVIDEND FIELDS**:
• dividend_yield - Annual dividend yield (Float) - Range: 0.0-0.15+ (0.0-15%+)
• dividend_per_share - Dividend per share (Float) - Range: $0.00-$20.00+ (in USD)
• dividend_frequency - Payment frequency (String) - Values: "quarterly", "annual", "monthly", "semi-annual"
• dividend_payout_ratio - Payout ratio (Float) - Range: 0.0-2.0+ (0-200%+)
• fcf_payout_ratio - FCF payout ratio (Float) - Range: 0.0-2.0+ (0-200%+)
• earnings_coverage_ratio - Earnings coverage (Float) - Range: 0.0-10.0+ (times covered)
• last_ex_dividend_date - Last ex-dividend date (String) - Format: "YYYY-MM-DD"
• next_payment_date - Next payment date (String) - Format: "YYYY-MM-DD"
• dividend_growth_rate_1y - 1-year growth rate (Float) - Range: -0.5 to 0.5+ (-50% to 50%+)
• dividend_growth_rate_3y - 3-year growth rate (Float) - Range: -0.3 to 0.3+ (-30% to 30%+)
• dividend_growth_rate_5y - 5-year growth rate (Float) - Range: -0.2 to 0.2+ (-20% to 20%+)
• dividend_growth_rate_10y - 10-year growth rate (Float) - Range: -0.1 to 0.1+ (-10% to 10%+)
• years_of_dividend_payments - Years paying dividends (Integer) - Range: 0-100+
• years_of_dividend_growth - Years of growth (Integer) - Range: 0-50+
• dividend_consistency_score - Consistency score (Float) - Range: 0.0-1.0 (1.0 = perfect)
• dividend_cuts_last_10y - Cuts in last 10 years (Integer) - Range: 0-10+
• is_dividend_aristocrat - Dividend Aristocrat (Boolean) - true/false (25+ years growth)
• is_dividend_king - Dividend King (Boolean) - true/false (50+ years growth)
• is_dividend_champion - Dividend Champion (Boolean) - true/false (25+ years growth)
• dividend_sustainability_score - Sustainability score (Float) - Range: 0.0-1.0 (1.0 = most sustainable)

**🌱 ESG QUALITY FIELDS**:
• esg_total_score - Total ESG score (Float) - Range: 0.0-100.0 (100 = best)
• environmental_score - Environmental score (Float) - Range: 0.0-100.0 (100 = best)
• social_score - Social score (Float) - Range: 0.0-100.0 (100 = best)
• governance_score - Governance score (Float) - Range: 0.0-100.0 (100 = best)
• earnings_quality_score - Earnings quality (Float) - Range: 0.0-1.0 (1.0 = highest quality)
• balance_sheet_quality_score - Balance sheet quality (Float) - Range: 0.0-1.0 (1.0 = strongest)
• cash_flow_quality_score - Cash flow quality (Float) - Range: 0.0-1.0 (1.0 = best)
• accounting_quality_score - Accounting quality (Float) - Range: 0.0-1.0 (1.0 = most transparent)
• business_predictability_score - Business predictability (Float) - Range: 0.0-1.0 (1.0 = most predictable)
• revenue_quality_score - Revenue quality (Float) - Range: 0.0-1.0 (1.0 = highest quality)
• management_effectiveness_score - Management effectiveness (Float) - Range: 0.0-1.0 (1.0 = most effective)
• ceo_tenure_years - CEO tenure in years (Integer) - Range: 0-50+ years
• capital_allocation_score - Capital allocation (Float) - Range: 0.0-1.0 (1.0 = best allocation)
• estimated_institutional_ownership - Institutional ownership (Float) - Range: 0.0-1.0 (0-100%)
• estimated_insider_ownership - Insider ownership (Float) - Range: 0.0-1.0 (0-100%)
• estimated_institutional_ownership_change_1y - 1-year change in institutional ownership (Float) - Range: -1.0 to 1.0+ (typically -0.2 to 0.2)
• estimated_institutional_ownership_change_3y - 3-year change in institutional ownership (Float) - Range: -1.0 to 1.0+ (typically -0.3 to 0.3)
• estimated_institutional_ownership_change_5y - 5-year change in institutional ownership (Float) - Range: -1.0 to 1.0+ (typically -0.4 to 0.4)
• estimated_institutional_ownership_change_10y - 10-year change in institutional ownership (Float) - Range: -1.0 to 1.0+ (typically -0.5 to 0.5)
• estimated_insider_ownership_change_1y - 1-year change in insider ownership (Float) - Range: -1.0 to 1.0+ (typically -0.1 to 0.1)
• estimated_insider_ownership_change_3y - 3-year change in insider ownership (Float) - Range: -1.0 to 1.0+ (typically -0.15 to 0.15)
• estimated_insider_ownership_change_5y - 5-year change in insider ownership (Float) - Range: -1.0 to 1.0+ (typically -0.2 to 0.2)
• estimated_insider_ownership_change_10y - 10-year change in insider ownership (Float) - Range: -1.0 to 1.0+ (typically -0.3 to 0.3)
• institutional_ownership_volatility_3y - Ownership stability score (Float) - Range: 0.0-1.0 (lower = more stable)
• insider_ownership_trend_direction - Insider ownership trend classification (String) - Values: "stable_high", "moderate", "low_stable"
• management_turnover_3y - Management stability indicator (Float) - Range: 0.0-1.0+ (typically 0.05-0.4)
• executive_compensation_ratio - Executive pay benchmarking (Integer) - Range: 50-1000+ (typically 150-500)
• board_independence_score - Board composition quality (Float) - Range: 0.0-1.0 (1.0 = full independence)
• audit_quality_score - Financial reporting quality (Float) - Range: 0.0-1.0 (1.0 = highest quality)
• esg_momentum - ESG improvement direction tracking (String) - Values: "improving", "stable", "declining"
• controversy_score - ESG risk incidents scoring (Float) - Range: 0.0-5.0+ (lower = better, 0 = no controversies)
• r_and_d_intensity - R&D spending intensity (Float) - Range: 0.0-0.5+ (0-50%+ of revenue)
• patent_portfolio_size - Patent portfolio size (Integer) - Range: 0-50,000+ (number of patents)
• r_and_d_intensity_score - R&D intensity score (Float) - Range: 0.0-1.0 (1.0 = highest R&D intensity)
• customer_retention_rate - Customer retention rate (Float) - Range: 0.0-1.0 (0-100%)

**💪 FINANCIAL HEALTH FIELDS**:
• debt_to_equity - Debt to equity ratio (Float) - Range: 0.0-5.0+ (0-500%+)
• debt_to_assets - Debt to assets ratio (Float) - Range: 0.0-1.0 (0-100%)
• debt_to_ebitda - Debt to EBITDA ratio (Float) - Range: 0.0-10.0+ (times)
• total_debt - Total debt amount (Integer) - Range: 0-1T+ (in USD)
• net_debt - Net debt amount (Integer) - Range: -100B to 1T+ (in USD)
• interest_coverage - Interest coverage ratio (Float) - Range: 0.0-100.0+ (times)
• debt_service_coverage - Debt service coverage (Float) - Range: 0.0-10.0+ (times)
• cash_coverage_ratio - Cash coverage ratio (Float) - Range: 0.0-2.0+ (times)
• current_ratio - Current ratio (Float) - Range: 0.0-5.0+ (times)
• quick_ratio - Quick ratio (Float) - Range: 0.0-3.0+ (times)
• cash_ratio - Cash ratio (Float) - Range: 0.0-2.0+ (times)
• operating_cf_ratio - Operating CF ratio (Float) - Range: 0.0-5.0+ (times)
• free_cash_flow - Free cash flow (Integer) - Range: -50B to 200B+ (in USD)
• operating_cash_flow - Operating cash flow (Integer) - Range: -50B to 200B+ (in USD)
• cash_conversion_ratio - Cash conversion ratio (Float) - Range: 0.0-2.0+ (times)
• fcf_to_net_income - FCF to net income (Float) - Range: 0.0-3.0+ (times)
• working_capital - Working capital (Integer) - Range: -100B to 500B+ (in USD)
• cash_conversion_cycle - Cash conversion cycle (Integer) - Range: -365 to 365+ (days)
• altman_z_score - Altman Z-Score (Float) - Range: 0.0-10.0+ (>2.99 = safe)
• piotroski_score - Piotroski F-Score (Integer) - Range: 0-9 (9 = best)
• financial_distress_score - Financial distress score (Float) - Range: 0.0-100.0 (lower = better)
• balance_sheet_quality_score - Balance sheet quality (Float) - Range: 0.0-100.0 (higher = better)
• debt_trend_improving - Debt trend improving (Boolean) - true/false
• liquidity_trend - Liquidity trend (String) - Values: "improving", "stable", "deteriorating"
• cash_generation_consistency - Cash generation consistency (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• working_capital_efficiency - Working capital efficiency (Float) - Range: 0.0-2.0+ (efficiency score)
• debt_to_equity_trend_direction - D/E trend direction (String) - Values: "improving", "stable", "deteriorating"
• interest_coverage_trend - Interest coverage trend (String) - Values: "improving", "stable", "deteriorating"

**📈 GROWTH FIELDS**:
• revenue_growth_1y - 1-year revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• revenue_growth_3y - 3-year revenue growth (Float) - Range: -0.3 to 1.0+ (-30% to 100%+)
• revenue_growth_5y - 5-year revenue growth (Float) - Range: -0.2 to 0.8+ (-20% to 80%+)
• revenue_growth_10y - 10-year revenue growth (Float) - Range: -0.1 to 0.5+ (-10% to 50%+)
• revenue_growth_ttm - TTM revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• eps_growth_1y - 1-year EPS growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• eps_growth_3y - 3-year EPS growth (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• eps_growth_5y - 5-year EPS growth (Float) - Range: -0.8 to 1.5+ (-80% to 150%+)
• eps_growth_ttm - TTM EPS growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• operating_income_growth_1y - 1-year operating income growth (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• net_income_growth_1y - 1-year net income growth (Float) - Range: -1.0 to 4.0+ (-100% to 400%+)
• ebitda_growth_1y - 1-year EBITDA growth (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• ebitda_growth_3y - 3-year EBITDA growth (Float) - Range: -0.5 to 1.5+ (-50% to 150%+)
• fcf_growth_1y - 1-year FCF growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• operating_cf_growth_1y - 1-year operating CF growth (Float) - Range: -1.0 to 3.0+ (-100% to 300%+)
• shares_outstanding_change_1y - 1-year shares change (Float) - Range: -0.2 to 0.2+ (-20% to 20%+)
• shares_outstanding_change_3y - 3-year shares change (Float) - Range: -0.3 to 0.3+ (-30% to 30%+)
• shares_outstanding_change_5y - 5-year shares change (Float) - Range: -0.4 to 0.4+ (-40% to 40%+)
• shares_outstanding_change_10y - 10-year shares change (Float) - Range: -1.0 to 10.0+ (-100% to 1000%+, typically -0.5 to 0.5)
• weighted_avg_shares_growth - Weighted avg shares growth (Float) - Range: -0.2 to 0.2+ (-20% to 20%+)
• fixed_asset_growth_1y - 1-year fixed asset growth (Float) - Range: -1.0 to 5.0+ (-100% to 500%+, typically -0.2 to 0.3)
• fixed_asset_growth_3y - 3-year fixed asset CAGR (Float) - Range: -1.0 to 5.0+ (-100% to 500%+, typically -0.1 to 0.25)
• fixed_asset_growth_5y - 5-year fixed asset CAGR (Float) - Range: -1.0 to 5.0+ (-100% to 500%+, typically -0.05 to 0.2)
• fixed_asset_growth_10y - 10-year fixed asset CAGR (Float) - Range: -1.0 to 5.0+ (-100% to 500%+, typically 0.0 to 0.15)
• revenue_growth_consistency - Revenue growth consistency (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• earnings_growth_consistency - Earnings growth consistency (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• growth_sustainability_score - Growth sustainability score (Float) - Range: 0.0-1.0 (1.0 = most sustainable)
• growth_efficiency_score - Growth efficiency score (Float) - Range: 0.0-1.0 (1.0 = most efficient)
• estimated_revenue_growth_next_y - Est. next year revenue growth (Float) - Range: -0.3 to 1.0+ (-30% to 100%+)
• estimated_eps_growth_next_y - Est. next year EPS growth (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• revenue_growth_qtd - Quarter-to-date revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• net_income_growth_qtd - Quarter-to-date net income growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• net_income_growth_q0 - Current quarter net income growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• net_income_growth_q1 - Q1 net income growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• net_income_growth_q2 - Q2 net income growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)
• net_income_growth_q3 - Q3 net income growth (Float) - Range: -2.0 to 5.0+ (-200% to 500%+)

**🌍 MACROECONOMIC FACTORS FIELDS**:
• gdp_correlation_score - GDP correlation score (Float) - Range: 0.0-1.0 (1.0 = highest correlation)
• interest_rate_sensitivity - Interest rate sensitivity (Float) - Range: 0.0-1.0 (1.0 = most sensitive)
• inflation_sensitivity_score - Inflation sensitivity (Float) - Range: 0.0-1.0 (1.0 = most sensitive)
• economic_cycle_position - Economic cycle position (String) - Values: "early_cycle", "mid_cycle", "late_cycle", "recession"
• sector_rotation_position - Sector rotation position (String) - Values: "defensive", "neutral", "cyclical"
• market_cycle_stage - Market cycle stage (String) - Values: "early_cycle", "mid_cycle", "late_cycle", "bear_market"
• volatility_regime_score - Volatility regime score (Float) - Range: 0.0-1.0 (1.0 = high volatility)
• market_risk_appetite - Market risk appetite (Float) - Range: 0.0-1.0 (1.0 = high risk appetite)
• fx_exposure_score - FX exposure score (Float) - Range: 0.0-1.0 (1.0 = highest exposure)
• currency_correlation_score - Currency correlation (Float) - Range: 0.0-1.0 (1.0 = highest correlation)
• commodity_sensitivity_score - Commodity sensitivity (Float) - Range: 0.0-1.0 (1.0 = most sensitive)
• inflation_hedge_score - Inflation hedge score (Float) - Range: 0.0-1.0 (1.0 = best hedge)

**📊 MARKET DATA FIELDS**:
• current_price - Current stock price (Float) - Range: $0.01-$1000+ (in USD)
• day_high - Daily high price (Float) - Range: $0.01-$1000+ (in USD)
• day_low - Daily low price (Float) - Range: $0.01-$1000+ (in USD)
• open_price - Opening price (Float) - Range: $0.01-$1000+ (in USD)
• previous_close - Previous close price (Float) - Range: $0.01-$1000+ (in USD)
• volume - Daily trading volume (Integer) - Range: 1,000-1B+ shares
• avg_volume_10d - 10-day average volume (Integer) - Range: 1,000-1B+ shares
• avg_volume_30d - 30-day average volume (Integer) - Range: 1,000-1B+ shares
• avg_volume_90d - 90-day average volume (Integer) - Range: 1,000-1B+ shares
• volume_ratio - Volume ratio (Float) - Range: 0.0-10.0+ (current vs average)
• volume_ratio_10d - 10-day volume ratio (Float) - Range: 0.0-10.0+ (ratio)
• volume_surge_indicator - Volume surge flag (Boolean) - true/false
• unusual_volume_flag - Unusual volume flag (Boolean) - true/false
• year_high - 52-week high (Float) - Range: $0.01-$1000+ (in USD)
• year_low - 52-week low (Float) - Range: $0.01-$1000+ (in USD)
• price_momentum_3m - 3-month price momentum (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• price_momentum_6m - 6-month price momentum (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• price_momentum_1y - 1-year price momentum (Float) - Range: -0.9 to 5.0+ (-90% to 500%+)
• price_to_52week_high_ratio - Price to 52w high ratio (Float) - Range: 0.0-1.0 (1.0 = at high)
• weeks_since_52week_high - Weeks since 52w high (Integer) - Range: 0-52+ weeks
• bollinger_upper - Bollinger upper band (Float) - Range: $0.01-$1000+ (in USD)
• bollinger_lower - Bollinger lower band (Float) - Range: $0.01-$1000+ (in USD)
• bollinger_position - Bollinger position (String) - Values: "upper_half", "lower_half", "above_upper", "below_lower"
• rsi_30 - 30-day RSI (Float) - Range: 0.0-100.0 (<30 oversold, >70 overbought)
• volatility_rank - Volatility rank (Float) - Range: 0.0-100.0 (percentile ranking)
• price_change - Price change (Float) - Range: $-100 to $100+ (in USD)
• price_change_percentage - Price change percentage (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• price_to_52week_low_ratio - Price to 52w low ratio (Float) - Range: 1.0-50.0+ (1.0 = at low)
• price_change_percentage_1w - 1-week price change percentage (Float) - Range: -0.3 to 0.3+ (-30% to 30%+)

**🏆 MARKET POSITION FIELDS**:
• market_cap_rank_global - Global market cap rank (Integer) - Range: 1-50,000+
• market_cap_rank_sector - Sector market cap rank (Integer) - Range: 1-1,000+
• market_cap_rank_exchange - Exchange market cap rank (Integer) - Range: 1-5,000+
• revenue_rank_sector - Sector revenue rank (Integer) - Range: 1-1,000+
• market_cap_percentile_sector - Sector market cap percentile (Float) - Range: 0.0-100.0
• estimated_market_share - Estimated market share (Float) - Range: 0.0-100.0+ (percentage)
• market_share_trend - Market share trend (String) - Values: "increasing", "stable", "decreasing"
• competitive_position_score - Competitive position score (Float) - Range: 0.0-1.0 (1.0 = strongest)
• revenue_vs_largest_competitor - Revenue vs largest competitor (Float) - Range: 0.0-10.0+ (ratio)
• market_cap_vs_peer_median - Market cap vs peer median (Float) - Range: 0.0-1000.0+ (ratio)
• margin_vs_peer_median - Margin vs peer median (Float) - Range: 0.0-10.0+ (ratio)
• growth_vs_peer_median - Growth vs peer median (Float) - Range: 0.0-5.0+ (ratio)
• beta_vs_sector_median - Beta vs sector median (Float) - Range: 0.0-3.0+ (ratio)
• market_leader_score - Market leader score (Float) - Range: 0.0-1.0 (1.0 = clear leader)
• innovation_leadership_score - Innovation leadership score (Float) - Range: 0.0-1.0 (1.0 = innovation leader)
• pricing_power_score - Pricing power score (Float) - Range: 0.0-1.0 (1.0 = strong pricing power)
• economic_moat_score - Economic moat score (Float) - Range: 0.0-1.0 (1.0 = widest moat)
• competitive_moat_trend - Competitive moat trend (String) - Values: "widening", "stable", "narrowing"
• barriers_to_entry_score - Barriers to entry score (Float) - Range: 0.0-1.0 (1.0 = highest barriers)
• switching_costs_score - Switching costs score (Float) - Range: 0.0-1.0 (1.0 = highest switching costs)

**💰 PROFITABILITY FIELDS**:
• roe - Return on Equity (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• roa - Return on Assets (Float) - Range: -0.5 to 0.5+ (-50% to 50%+)
• roce - Return on Capital Employed (Float) - Range: -0.5 to 1.0+ (-50% to 100%+)
• roic - Return on Invested Capital (Float) - Range: -0.5 to 1.0+ (-50% to 100%+)
• gross_margin - Gross profit margin (Float) - Range: 0.0-1.0 (0-100%)
• operating_margin - Operating margin (Float) - Range: -0.5 to 0.8+ (-50% to 80%+)
• ebitda_margin - EBITDA margin (Float) - Range: -0.5 to 0.8+ (-50% to 80%+)
• net_margin - Net profit margin (Float) - Range: -0.5 to 0.5+ (-50% to 50%+)
• asset_turnover - Asset turnover ratio (Float) - Range: 0.0-5.0+ (times)
• inventory_turnover - Inventory turnover ratio (Float) - Range: 0.0-50.0+ (times)
• receivables_turnover - Receivables turnover ratio (Float) - Range: 0.0-20.0+ (times)
• payables_turnover - Payables turnover ratio (Float) - Range: 0.0-30.0+ (times)
• roe_3_year_avg - 3-year average ROE (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• roe_5_year_avg - 5-year average ROE (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• roe_10_year_avg - 10-year average ROE (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• roce_3_year_avg - 3-year average ROCE (Float) - Range: -0.5 to 1.0+ (-50% to 100%+)
• roce_5_year_avg - 5-year average ROCE (Float) - Range: -0.5 to 1.0+ (-50% to 100%+)
• roce_10_year_avg - 10-year average ROCE (Float) - Range: -0.5 to 1.0+ (-50% to 100%+)
• roe_consistency_score - ROE consistency score (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• roce_consistency_score - ROCE consistency score (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• profitability_quality_score - Profitability quality score (Float) - Range: 0.0-1.0 (1.0 = highest quality)
• earnings_quality_score - Earnings quality score (Float) - Range: 0.0-1.0 (1.0 = highest quality)
• competitive_advantage_score - Competitive advantage score (Float) - Range: 0.0-1.0 (1.0 = strongest advantage)
• margin_expansion_trend - Margin expansion trend (Boolean) - true/false
• equity_multiplier - Equity multiplier (Float) - Range: 1.0-10.0+ (financial leverage)
• net_income_qtd - Quarter-to-date net income (Integer) - Range: -10B to 50B+ (in USD)
• operating_margin_trend - Operating margin trend (String) - Values: "improving", "stable", "deteriorating"
• operating_cf_margin - Operating cash flow margin (Float) - Range: -0.5 to 0.8+ (-50% to 80%+)

**⚠️ RISK ASSESSMENT FIELDS**:
• market_risk - Market risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• liquidity_risk - Liquidity risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• credit_risk - Credit risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• operational_risk - Operational risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• business_risk - Business risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• competitive_risk - Competitive risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• regulatory_risk - Regulatory risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• geopolitical_risk - Geopolitical risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• technology_risk - Technology risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• environmental_risk - Environmental risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• social_risk - Social risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• governance_risk - Governance risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• esg_risk - ESG risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• macroeconomic_risk - Macroeconomic risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• industry_risk - Industry risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• company_risk - Company risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• valuation_risk - Valuation risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• dividend_risk - Dividend risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)
• earnings_risk - Earnings risk score (Float) - Range: 0.0-1.0 (1.0 = highest risk)

**🔍 SCREENING FLAGS FIELDS** - ALL BOOLEAN (true/false):
• is_value_stock - Value stock flag
• is_undervalued - Undervalued stock flag
• is_deep_value - Deep value stock flag
• is_growth_stock - Growth stock flag
• is_high_growth - High growth stock flag
• has_accelerating_growth - Accelerating growth flag
• is_profitable - Profitable company flag
• is_high_quality - High quality company flag
• has_competitive_advantage - Competitive advantage flag
• is_financially_strong - Financially strong flag
• is_debt_free - Debt-free company flag
• has_strong_cash_flow - Strong cash flow flag
• is_large_cap - Large cap stock flag
• is_dividend_stock - Dividend-paying stock flag
• is_near_52week_high - Near 52-week high flag
• is_consistent_grower_10y - Consistent 10-year grower flag
• is_margin_expander - Margin expanding flag
• has_sustainable_competitive_advantage - Sustainable competitive advantage flag
• is_cash_flow_king - Cash flow king flag
• is_dividend_achiever - Dividend achiever flag
• is_low_volatility_stock - Low volatility stock flag
• is_earnings_consistent - Consistent earnings flag
• is_balance_sheet_fortress - Strong balance sheet flag
• is_sector_leader - Sector leader flag
• is_innovation_leader - Innovation leader flag
• has_pricing_power - Pricing power flag
• is_market_share_gainer - Market share gaining flag
• is_economic_moat_wide - Wide economic moat flag
• is_competitive_position_strong - Strong competitive position flag
• is_fairly_valued - Fairly valued flag
• is_deep_value_opportunity - Deep value opportunity flag
• is_growth_at_reasonable_price - GARP flag
• is_dividend_value_play - Dividend value play flag
• is_dcf_undervalued - DCF undervalued flag
• is_peer_outperformer - Peer outperformer flag
• has_positive_quarterly_results_after_losses - Positive quarterly results after losses flag
• has_network_effects - Network effects flag

**📐 TECHNICAL FIELDS**:
• rsi_14 - 14-day RSI (Float) - Range: 0.0-100.0 (<30 oversold, >70 overbought)
• adx - Average Directional Index (Float) - Range: 0.0-100.0 (>25 trending)
• williams_r - Williams %R (Float) - Range: -100.0 to 0.0 (<-80 oversold, >-20 overbought)
• stochastic_k - Stochastic %K (Float) - Range: 0.0-100.0 (<20 oversold, >80 overbought)
• sma_50 - 50-day moving average (Float) - Range: $0.01-$1000+ (in USD)
• sma_200 - 200-day moving average (Float) - Range: $0.01-$1000+ (in USD)
• golden_cross_signal - Golden cross signal (Boolean) - true/false (SMA 50 > SMA 200)
• price_momentum_score - Price momentum score (Float) - Range: 0.0-100.0 (percentile score)
• sharpe_ratio - Sharpe ratio (Float) - Range: -2.0 to 5.0+ (risk-adjusted return)
• volatility_30d - 30-day volatility (Float) - Range: 0.0-2.0+ (0-200%+)
• max_drawdown - Maximum drawdown (Float) - Range: 0.0-1.0 (0-100%)
• max_drawdown_1y - 1-year maximum drawdown (Float) - Range: 0.0-1.0 (0-100%)

**📏 SECTOR COMPARISONS FIELDS**:
• pe_vs_sector_median - P/E vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• pe_percentile_sector - P/E sector percentile (Float) - Range: 0.0-100.0
• pb_vs_sector_median - P/B vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• ps_vs_sector_median - P/S vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• ev_ebitda_vs_sector_median - EV/EBITDA vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• valuation_percentile_sector - Valuation sector percentile (Float) - Range: 0.0-100.0
• roe_vs_sector_median - ROE vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• roe_percentile_sector - ROE sector percentile (Float) - Range: 0.0-100.0
• operating_margin_vs_sector_median - Operating margin vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• net_margin_vs_sector_median - Net margin vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• revenue_growth_vs_sector_median - Revenue growth vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• revenue_growth_percentile_sector - Revenue growth sector percentile (Float) - Range: 0.0-100.0
• debt_to_equity_vs_sector_median - D/E vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• current_ratio_vs_sector_median - Current ratio vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• cash_position_vs_sector_median - Cash position vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• sector_avg_pe - Sector average P/E (Float) - Range: 0.0-1000.0+ (ratio)
• sector_avg_roe - Sector average ROE (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• sector_avg_debt_equity - Sector average D/E (Float) - Range: 0.0-5.0+ (ratio)

**💎 VALUATION FIELDS**:
• pe_ratio - Price to Earnings ratio (Float) - Range: 0.0-1000.0+ (times)
• pe_ratio_ttm - TTM Price to Earnings ratio (Float) - Range: 0.0-1000.0+ (times)
• peg_ratio - Price/Earnings to Growth ratio (Float) - Range: 0.0-10.0+ (times)
• pb_ratio - Price to Book ratio (Float) - Range: 0.0-50.0+ (times)
• ps_ratio - Price to Sales ratio (Float) - Range: 0.0-100.0+ (times)
• ev_ebitda - Enterprise Value to EBITDA (Float) - Range: 0.0-1000.0+ (times)
• ev_revenue - Enterprise Value to Revenue (Float) - Range: 0.0-100.0+ (times)
• price_to_fcf - Price to Free Cash Flow (Float) - Range: 0.0-1000.0+ (times)
• price_to_operating_cf - Price to Operating Cash Flow (Float) - Range: 0.0-500.0+ (times)
• price_to_tangible_book - Price to Tangible Book (Float) - Range: 0.0-100.0+ (times)
• enterprise_value_to_ebitda - EV to EBITDA (Float) - Range: 0.0-1000.0+ (times)
• tangible_book_value_per_share - Tangible book value per share (Float) - Range: $-100 to $500+ (in USD)
• dividend_yield - Dividend yield (Float) - Range: 0.0-0.15+ (0-15%+)
• earnings_yield - Earnings yield (Float) - Range: 0.0-1.0+ (0-100%+)
• fcf_yield - Free cash flow yield (Float) - Range: 0.0-0.5+ (0-50%+)
• book_value_per_share - Book value per share (Float) - Range: $-100 to $500+ (in USD)
• revenue_per_share - Revenue per share (Float) - Range: $0.01 to $1000+ (in USD)
• operating_cf_per_share - Operating CF per share (Float) - Range: $-50 to $200+ (in USD)
• free_cash_flow_per_share - FCF per share (Float) - Range: $-50 to $200+ (in USD)
• pe_vs_sector_median - P/E vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• pb_vs_sector_median - P/B vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• valuation_percentile_sector - Valuation sector percentile (Float) - Range: 0.0-100.0
• dcf_discount_premium - DCF discount/premium (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• pe_ratio_avg_3y - 3-year average P/E ratio (Float) - Range: 0.0-200.0 (typically 5.0-50.0)
• pe_ratio_avg_5y - 5-year average P/E ratio (Float) - Range: 0.0-200.0 (typically 8.0-45.0)
• pe_ratio_avg_10y - 10-year average P/E ratio (Float) - Range: 0.0-200.0 (typically 10.0-40.0)
• pb_ratio_avg_3y - 3-year average P/B ratio (Float) - Range: 0.0-50.0 (typically 0.5-15.0)
• pb_ratio_avg_5y - 5-year average P/B ratio (Float) - Range: 0.0-50.0 (typically 0.8-12.0)
• pb_ratio_avg_10y - 10-year average P/B ratio (Float) - Range: 0.0-50.0 (typically 1.0-10.0)
• ps_ratio_avg_3y - 3-year average P/S ratio (Float) - Range: 0.0-100.0 (typically 0.5-20.0)
• ps_ratio_avg_5y - 5-year average P/S ratio (Float) - Range: 0.0-100.0 (typically 0.8-18.0)
• ps_ratio_avg_10y - 10-year average P/S ratio (Float) - Range: 0.0-100.0 (typically 1.0-15.0)
• ev_ebitda_avg_3y - 3-year average EV/EBITDA ratio (Float) - Range: 0.0-200.0 (typically 5.0-50.0)
• ev_ebitda_avg_5y - 5-year average EV/EBITDA ratio (Float) - Range: 0.0-200.0 (typically 8.0-45.0)
• ev_ebitda_avg_10y - 10-year average EV/EBITDA ratio (Float) - Range: 0.0-200.0 (typically 10.0-40.0)
• ev_revenue_avg_3y - 3-year average EV/Revenue ratio (Float) - Range: 0.0-100.0 (typically 0.5-20.0)
• ev_revenue_avg_5y - 5-year average EV/Revenue ratio (Float) - Range: 0.0-100.0 (typically 0.8-18.0)
• ev_revenue_avg_10y - 10-year average EV/Revenue ratio (Float) - Range: 0.0-100.0 (typically 1.0-15.0)
• price_to_fcf_avg_3y - 3-year average Price/FCF ratio (Float) - Range: 0.0-200.0 (typically 8.0-60.0)
• price_to_fcf_avg_5y - 5-year average Price/FCF ratio (Float) - Range: 0.0-200.0 (typically 10.0-55.0)
• price_to_fcf_avg_10y - 10-year average Price/FCF ratio (Float) - Range: 0.0-200.0 (typically 12.0-50.0)
• dividend_yield_avg_3y - 3-year average dividend yield (Float) - Range: 0.0-0.2 (typically 0.0-0.08)
• dividend_yield_avg_5y - 5-year average dividend yield (Float) - Range: 0.0-0.2 (typically 0.0-0.08)
• valuation_trend_direction - Overall valuation trend direction (String) - Values: "improving", "stable", "deteriorating"
• pe_trend_3y - 3-year P/E ratio trend (String) - Values: "rising", "stable", "falling"
• valuation_volatility_score - Valuation stability score (Float) - Range: 0.0-1.0 (lower = more stable)
• relative_valuation_score - Relative valuation attractiveness (Float) - Range: 0.0-10.0 (higher = better value)
• rd_intensity - R&D intensity (Float) - Range: 0.0-0.5+ (0-50%+ of revenue)
• recurring_revenue_percentage - Recurring revenue percentage (Float) - Range: 0.0-1.0 (0-100%)

**💼 WORKING CAPITAL FIELDS**:
• working_capital - Working capital amount (Integer) - Range: -500B to 500B+ (in USD)
• working_capital_to_revenue - WC to revenue ratio (Float) - Range: -100.0 to 100.0+ (percentage)
• working_capital_efficiency_score - WC efficiency score (Float) - Range: 0.0-10.0+ (efficiency score)
• net_working_capital - Net working capital (Integer) - Range: -500B to 500B+ (in USD)
• net_working_capital_to_revenue - Net WC to revenue ratio (Float) - Range: -100.0 to 100.0+ (percentage)
• working_capital_productivity - WC productivity (Float) - Range: 0.0-10.0+ (productivity score)
• working_capital_intensity - WC intensity (Float) - Range: -100.0 to 100.0+ (intensity score)
• asset_turnover - Asset turnover ratio (Float) - Range: 0.0-5.0+ (times)
• fixed_asset_turnover - Fixed asset turnover (Float) - Range: 0.0-20.0+ (times)
• asset_utilization_score - Asset utilization score (Float) - Range: 0.0-2.0+ (utilization score)
• fixed_asset_efficiency - Fixed asset efficiency (Float) - Range: 0.0-50.0+ (efficiency score)
• total_asset_growth_1y - 1-year total asset growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• fixed_asset_growth_1y - 1-year fixed asset growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• days_sales_outstanding - Days Sales Outstanding (Float) - Range: 0.0-500.0+ (days)
• days_inventory_outstanding - Days Inventory Outstanding (Float) - Range: 0.0-500.0+ (days)
• days_payable_outstanding - Days Payable Outstanding (Float) - Range: 0.0-500.0+ (days)
• cash_conversion_cycle - Cash Conversion Cycle (Float) - Range: -500.0 to 500.0+ (days)
• inventory_turnover - Inventory turnover ratio (Float) - Range: 0.0-100.0+ (times)
• current_ratio - Current ratio (Float) - Range: 0.0-10.0+ (times)
• quick_ratio - Quick ratio (Float) - Range: 0.0-5.0+ (times)
• operating_cf_to_current_liabilities - Operating CF to current liabilities (Float) - Range: 0.0-5.0+ (times)
• liquidity_health_score - Liquidity health score (Float) - Range: 0.0-10.0 (10 = best liquidity)
• working_capital_trend - Working capital trend (String) - Values: "improving", "stable", "deteriorating"
• wc_trend_slope - WC trend slope (Float) - Range: -1B to 1B+ (slope in USD)
• wc_trend_consistency - WC trend consistency (Float) - Range: 0.0-10.0+ (consistency score)
• fcf_to_working_capital_ratio - FCF to WC ratio (Float) - Range: -10.0 to 10.0+ (ratio)
• comprehensive_wc_efficiency_score - Comprehensive WC efficiency (Float) - Range: 0.0-10.0 (10 = best efficiency)
• return_on_assets - Return on Assets (Float) - Range: -0.5 to 0.5+ (-50% to 50%+)
• receivables_to_revenue_ratio - Receivables to revenue ratio (Float) - Range: 0.0-100.0+ (percentage)
• working_capital_to_total_assets - WC to total assets ratio (Float) - Range: -100.0 to 100.0+ (percentage)
• total_asset_growth_3y - 3-year total asset CAGR (Float) - Range: -1.0 to 5.0+ (typically -0.1 to 0.3)
• total_asset_growth_5y - 5-year total asset CAGR (Float) - Range: -1.0 to 5.0+ (typically 0.0 to 0.25)
• total_asset_growth_10y - 10-year total asset CAGR (Float) - Range: -1.0 to 5.0+ (typically 0.02 to 0.2)
• current_assets_growth_1y - 1-year current assets growth (Float) - Range: -1.0 to 5.0+ (typically -0.3 to 0.5)
• current_assets_growth_3y - 3-year current assets CAGR (Float) - Range: -1.0 to 5.0+ (typically -0.1 to 0.3)
• current_assets_growth_5y - 5-year current assets CAGR (Float) - Range: -1.0 to 5.0+ (typically 0.0 to 0.25)
• current_assets_growth_10y - 10-year current assets CAGR (Float) - Range: -1.0 to 5.0+ (typically 0.02 to 0.2)
• fixed_asset_growth_3y_wc - 3-year fixed asset CAGR (WC module) (Float) - Range: -1.0 to 5.0+ (typically -0.1 to 0.25)
• fixed_asset_growth_5y_wc - 5-year fixed asset CAGR (WC module) (Float) - Range: -1.0 to 5.0+ (typically -0.05 to 0.2)
• fixed_asset_growth_10y_wc - 10-year fixed asset CAGR (WC module) (Float) - Range: -1.0 to 5.0+ (typically 0.0 to 0.15)
• working_capital_turnover_ratio - Revenue divided by average working capital (Float) - Range: 0.0-50.0+ (typically 2.0-20.0)
• net_working_capital_days - Days of revenue required to fund net working capital (Float) - Range: -200.0 to 500.0+ (typically -50.0 to 150.0)
• working_capital_velocity - How quickly working capital converts to cash (Float) - Range: 0.0-20.0+ (typically 1.0-10.0)
• working_capital_quality_score - Quality scoring based on WC composition (Float) - Range: 0.0-10.0
• working_capital_cash_impact - Impact of WC changes on cash flow as % of revenue (Float) - Range: -1.0 to 1.0+ (typically -0.2 to 0.2)
• operating_cf_to_revenue - Operating cash flow to revenue ratio (Float) - Range: -0.5 to 0.8+ (-50% to 80%+)

**📈 LATEST QUARTER FIELDS**:
• net_income - Latest quarter net income (Integer) - Range: -10B to 50B+ (in USD)
• revenue_growth - Latest quarter revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• other_income_to_revenue_ratio - Other income to revenue ratio (Float) - Range: -0.1 to 0.5+ (-10% to 50%+)

**📊 EARNINGS DATA FIELDS**:
• latest_quarter_eps - Latest quarter EPS (Float) - Range: $-50.00 to $100.00+ (in USD)
• latest_quarter_revenue - Latest quarter revenue (Integer) - Range: 1M-500B+ (in USD)
• latest_quarter_date - Latest quarter date (String) - Format: "YYYY-MM-DD"

**📈 GROWTH EXTENDED FIELDS**:
• revenue_growth_5y - 5-year revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• revenue_growth_10y - 10-year revenue growth (Float) - Range: -0.5 to 1.0+ (-50% to 100%+)
• revenue_growth_ttm - TTM revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• eps_growth_5y - 5-year EPS growth (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• eps_growth_10y - 10-year EPS growth (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• eps_growth_ttm - TTM EPS growth (Float) - Range: -1.0 to 3.0+ (-100% to 300%+)
• revenue_growth_trend - Revenue growth trend (String) - Values: "improving", "stable", "declining"
• revenue_growth_consistency - Revenue growth consistency (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• revenue_growth_acceleration - Revenue growth acceleration (Boolean) - true/false
• revenue_seasonality_score - Revenue seasonality score (Float) - Range: 0.0-1.0 (1.0 = highly seasonal)
• revenue_growth_vs_sector - Revenue growth vs sector (Float) - Range: 0.0-3.0+ (ratio)
• revenue_growth_rank_sector - Revenue growth sector rank (Integer) - Range: 1-1000+
• revenue_growth_percentile - Revenue growth percentile (Float) - Range: 0.0-100.0
• ebitda_growth_3y - 3-year EBITDA growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• ebitda_growth_5y - 5-year EBITDA growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• ebitda_growth_10y - 10-year EBITDA growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• operating_income_growth_1y - 1-year operating income growth (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• operating_income_growth_3y - 3-year operating income growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• operating_income_growth_5y - 5-year operating income growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• fcf_growth_1y - 1-year FCF growth (Float) - Range: -1.0 to 3.0+ (-100% to 300%+)
• fcf_growth_3y - 3-year FCF growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• fcf_growth_5y - 5-year FCF growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• earnings_growth_consistency - Earnings growth consistency (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• earnings_growth_acceleration - Earnings growth acceleration (Boolean) - true/false
• profitability_trend_score - Profitability trend score (Float) - Range: 0.0-10.0 (10 = best trend)
• growth_vs_sector_median - Growth vs sector median (Float) - Range: 0.0-3.0+ (ratio)
• growth_percentile_sector - Growth sector percentile (Float) - Range: 0.0-100.0
• growth_rank_sector - Growth sector rank (Integer) - Range: 1-1000+
• is_growth_leader - Growth leader flag (Boolean) - true/false
• growth_sustainability_score - Growth sustainability score (Float) - Range: 0.0-10.0 (10 = most sustainable)

**🇮🇳 INDIA SPECIFIC FIELDS**:
• board_independence_score - Board independence score (Float) - Range: 0.0-10.0 (10 = fully independent)
• promoter_holding_percentage - Promoter holding percentage (Float) - Range: 0.0-100.0 (percentage)
• promoter_pledge_percentage - Promoter pledge percentage (Float) - Range: 0.0-100.0 (percentage)
• institutional_holding - Institutional holding (Float) - Range: 0.0-100.0 (percentage)
• public_holding - Public holding (Float) - Range: 0.0-100.0 (percentage)
• management_tenure_avg - Average management tenure (Float) - Range: 0.0-50.0+ (years)
• management_track_record - Management track record score (Float) - Range: 0.0-10.0 (10 = excellent)
• succession_planning_score - Succession planning score (Float) - Range: 0.0-10.0 (10 = excellent planning)
• sebi_compliance_score - SEBI compliance score (Float) - Range: 0.0-10.0 (10 = full compliance)
• audit_quality_score - Audit quality score (Float) - Range: 0.0-10.0 (10 = highest quality)
• sector_rank_in_india - Sector rank in India (Integer) - Range: 1-1000+
• market_share_india - Market share in India (Float) - Range: 0.0-100.0 (percentage)
• monsoon_sensitivity - Monsoon sensitivity (Float) - Range: 0.0-1.0 (1.0 = highly sensitive)
• policy_sensitivity - Policy sensitivity (Float) - Range: 0.0-1.0 (1.0 = highly sensitive)
• export_dependency - Export dependency (Float) - Range: 0.0-1.0 (1.0 = fully dependent)
• domestic_demand_correlation - Domestic demand correlation (Float) - Range: 0.0-1.0 (1.0 = perfect correlation)

**📊 LATEST QUARTER RESULTS FIELDS**:
• revenue_growth_qoq - Quarter-over-quarter revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• revenue_growth_yoy - Year-over-year revenue growth (Float) - Range: -0.5 to 2.0+ (-50% to 200%+)
• gross_margin_latest_quarter - Latest quarter gross margin (Float) - Range: 0.0-100.0 (percentage)
• other_income_to_revenue_ratio - Other income to revenue ratio (Float) - Range: -0.2 to 1.0+ (-20% to 100%+)
• revenue_consistency_score - Revenue consistency score (Float) - Range: 0.0-10.0 (10 = most consistent)
• revenue_acceleration_indicator - Revenue acceleration indicator (Float) - Range: -10.0 to 10.0+ (acceleration score)
• revenue_per_share_latest - Latest revenue per share (Float) - Range: $0.01 to $1000+ (in USD)
• revenue_quality_score - Revenue quality score (Float) - Range: 0.0-10.0 (10 = highest quality)
• gross_margin_latest - Latest gross margin (Float) - Range: 0.0-100.0 (percentage)
• operating_margin_latest - Latest operating margin (Float) - Range: -50.0 to 80.0+ (percentage)
• net_margin_latest - Latest net margin (Float) - Range: -50.0 to 50.0+ (percentage)
• ebitda_margin_latest - Latest EBITDA margin (Float) - Range: -50.0 to 80.0+ (percentage)
• operating_margin_change_qoq - Operating margin QoQ change (Float) - Range: -50.0 to 50.0+ (percentage points)
• profitability_momentum_score - Profitability momentum score (Float) - Range: 0.0-10.0 (10 = strongest momentum)
• operating_leverage - Operating leverage (Float) - Range: -5.0 to 10.0+ (leverage ratio)
• operating_expense_ratio - Operating expense ratio (Float) - Range: 0.0-100.0 (percentage)
• sga_to_revenue_ratio - SGA to revenue ratio (Float) - Range: 0.0-100.0 (percentage)
• rd_intensity - R&D intensity (Float) - Range: 0.0-50.0+ (percentage)
• opex_efficiency_improvement - OpEx efficiency improvement (Float) - Range: -1.0 to 1.0+ (improvement ratio)
• asset_turnover_annualized - Annualized asset turnover (Float) - Range: 0.0-5.0+ (times)
• operational_efficiency_score - Operational efficiency score (Float) - Range: 0.0-10.0 (10 = most efficient)
• operating_cf_to_revenue - Operating CF to revenue (Float) - Range: -50.0 to 100.0+ (percentage)
• operating_cf_to_net_income - Operating CF to net income (Float) - Range: 0.0-5.0+ (ratio)
• free_cash_flow_to_revenue - FCF to revenue (Float) - Range: -50.0 to 50.0+ (percentage)
• working_capital_impact_on_ocf - WC impact on OCF (Float) - Range: -50.0 to 50.0+ (percentage)
• cash_flow_quality_score - Cash flow quality score (Float) - Range: 0.0-10.0 (10 = highest quality)
• total_assets_growth_qoq - Total assets growth QoQ (Float) - Range: -50.0 to 100.0+ (percentage)
• working_capital_change_qoq - Working capital change QoQ (Integer) - Range: -100B to 100B+ (in USD)
• debt_change_qoq - Debt change QoQ (Float) - Range: -50.0 to 100.0+ (percentage)
• equity_change_qoq - Equity change QoQ (Float) - Range: -50.0 to 100.0+ (percentage)
• cash_position_change_qoq - Cash position change QoQ (Float) - Range: -100.0 to 200.0+ (percentage)
• operating_earnings_ratio - Operating earnings ratio (Float) - Range: 0.0-5.0+ (ratio)
• other_income_dependency - Other income dependency (Float) - Range: 0.0-1.0 (1.0 = fully dependent)
• earnings_cash_flow_ratio - Earnings to cash flow ratio (Float) - Range: 0.0-5.0+ (ratio)
• earnings_sustainability_score - Earnings sustainability score (Float) - Range: 0.0-10.0 (10 = most sustainable)
• revenue_momentum_score - Revenue momentum score (Float) - Range: 0.0-10.0 (10 = strongest momentum)
• eps_momentum_score - EPS momentum score (Float) - Range: 0.0-10.0 (10 = strongest momentum)
• growth_consistency_score - Growth consistency score (Float) - Range: 0.0-10.0 (10 = most consistent)
• growth_acceleration_score - Growth acceleration score (Float) - Range: 0.0-10.0 (10 = highest acceleration)
• current_ratio_latest - Latest current ratio (Float) - Range: 0.0-10.0+ (ratio)
• debt_to_equity_latest - Latest debt to equity (Float) - Range: 0.0-5.0+ (ratio)
• financial_health_score - Financial health score (Float) - Range: 0.0-10.0 (10 = excellent health)

**🏆 QUALITY EXTENDED FIELDS**:
• financial_health_score - Financial health score (Float) - Range: 0.0-10.0 (10 = excellent health)
• earnings_quality_score - Earnings quality score (Float) - Range: 0.0-10.0 (10 = highest quality)
• balance_sheet_quality - Balance sheet quality (Float) - Range: 0.0-10.0 (10 = strongest balance sheet)
• cash_flow_quality - Cash flow quality (Float) - Range: 0.0-10.0 (10 = highest quality)
• management_efficiency - Management efficiency (Float) - Range: 0.0-10.0 (10 = most efficient)
• capital_allocation_score - Capital allocation score (Float) - Range: 0.0-10.0 (10 = optimal allocation)
• shareholder_return_score - Shareholder return score (Float) - Range: 0.0-10.0 (10 = excellent returns)
• competitive_advantage_score - Competitive advantage score (Float) - Range: 0.0-10.0 (10 = strongest advantage)
• market_position_score - Market position score (Float) - Range: 0.0-10.0 (10 = dominant position)
• pricing_power_score - Pricing power score (Float) - Range: 0.0-10.0 (10 = strongest pricing power)
• is_high_quality - High quality flag (Boolean) - true/false
• is_financially_healthy - Financially healthy flag (Boolean) - true/false
• has_competitive_advantage - Competitive advantage flag (Boolean) - true/false
• quality_improvement_trend - Quality improvement trend (Boolean) - true/false
• quality_deterioration_risk - Quality deterioration risk (Boolean) - true/false
• earnings_consistency_score - Earnings consistency score (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• revenue_consistency_score - Revenue consistency score (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• margin_consistency_score - Margin consistency score (Float) - Range: 0.0-1.0 (1.0 = most consistent)
• overall_consistency_score - Overall consistency score (Float) - Range: 0.0-1.0 (1.0 = most consistent)

**📊 SECTOR ENHANCED FIELDS**:
• pe_vs_sector_median - P/E vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• pb_vs_sector_median - P/B vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• ps_vs_sector_median - P/S vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• ev_ebitda_vs_sector - EV/EBITDA vs sector (Float) - Range: 0.0-10.0+ (ratio)
• roe_vs_sector_median - ROE vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• roce_vs_sector_median - ROCE vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• growth_vs_sector_median - Growth vs sector median (Float) - Range: 0.0-5.0+ (ratio)
• margin_vs_sector_median - Margin vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• debt_vs_sector_median - Debt vs sector median (Float) - Range: 0.0-10.0+ (ratio)
• valuation_percentile_sector - Valuation sector percentile (Float) - Range: 0.0-100.0
• profitability_percentile_sector - Profitability sector percentile (Float) - Range: 0.0-100.0
• growth_percentile_sector - Growth sector percentile (Float) - Range: 0.0-100.0
• efficiency_percentile_sector - Efficiency sector percentile (Float) - Range: 0.0-100.0
• quality_percentile_sector - Quality sector percentile (Float) - Range: 0.0-100.0
• is_sector_leader - Sector leader flag (Boolean) - true/false
• sector_leadership_score - Sector leadership score (Float) - Range: 0.0-10.0 (10 = clear leader)
• sector_outperformance_3y - 3-year sector outperformance (Float) - Range: -1.0 to 2.0+ (-100% to 200%+)
• market_share_rank_sector - Market share sector rank (Integer) - Range: 1-1000+

**📊 TECHNICAL EXTENDED FIELDS**:
• price_momentum_6m - 6-month price momentum (Float) - Range: -0.8 to 3.0+ (-80% to 300%+)
• price_momentum_1y - 1-year price momentum (Float) - Range: -0.9 to 5.0+ (-90% to 500%+)
• price_momentum_3y - 3-year price momentum (Float) - Range: -0.9 to 10.0+ (-90% to 1000%+)
• momentum_strength - Momentum strength (String) - Values: "weak", "moderate", "strong"
• momentum_sustainability - Momentum sustainability (Float) - Range: 0.0-1.0 (1.0 = most sustainable)
• rsi_trend - RSI trend (String) - Values: "rising", "stable", "falling"
• rsi_30 - 30-day RSI (Float) - Range: 0.0-100.0 (<30 oversold, >70 overbought)
• volume_trend_30d - 30-day volume trend (String) - Values: "increasing", "stable", "decreasing"
• volume_vs_avg_ratio - Volume vs average ratio (Float) - Range: 0.0-10.0+ (ratio)
• volume_breakout_signal - Volume breakout signal (Boolean) - true/false
• volume_strength_score - Volume strength score (Float) - Range: 0.0-10.0 (10 = strongest volume)
• weeks_at_52week_high - Weeks at 52-week high (Integer) - Range: 0-52+ weeks
• weeks_since_52week_high - Weeks since 52-week high (Integer) - Range: 0-52+ weeks
• breakout_strength - Breakout strength (Float) - Range: 0.0-1.0 (1.0 = strongest breakout)
• support_resistance_score - Support/resistance score (Float) - Range: 0.0-10.0 (10 = strongest levels)
• sma_20 - 20-day moving average (Float) - Range: $0.01-$1000+ (in USD)
• price_vs_sma20 - Price vs SMA 20 (Float) - Range: 0.0-5.0+ (ratio)
• price_vs_sma50 - Price vs SMA 50 (Float) - Range: 0.0-5.0+ (ratio)
• price_vs_sma200 - Price vs SMA 200 (Float) - Range: 0.0-5.0+ (ratio)
• golden_cross_signal - Golden cross signal (Boolean) - true/false
• death_cross_signal - Death cross signal (Boolean) - true/false
• bullish_crossover_count_3m - Bullish crossovers in 3 months (Integer) - Range: 0-20+
• technical_score_composite - Composite technical score (Float) - Range: 0.0-10.0 (10 = strongest technical setup)

**🔄 FIELD MAPPING INSTRUCTIONS**:
• growth_rate - Map to appropriate growth field as this field does not exist in the data:
  - Default: revenue_growth_1y
  - Alternatives: revenue_growth_3y, revenue_growth_5y, eps_growth_1y
  - Range: -0.5 to 2.0+ (-50% to 200%+)

• profit_margin - Map to appropriate margin field as this field does not exist in the data:
  - Default: net_margin
  - Alternatives: operating_margin, ebitda_margin
  - Range: -0.5 to 0.5+ (-50% to 50%+)

• free_cash_flow_yield - Calculated field:
  - Formula: (free_cash_flow / market_cap)
  - Components needed: free_cash_flow, market_cap
  - Range: -0.2 to 0.2+ (-20% to 20%+)



• fixed_assets - IMPORTANT: Do NOT use dot notation! Use these exact field names:
  - For 1-year growth: 'fixed_asset_growth_1y' (NOT fixed_assets.1_year_change)
  - For 3-year growth: 'fixed_asset_growth_3y' (NOT fixed_assets.3_year_change)
  - For 5-year growth: 'fixed_asset_growth_5y' (NOT fixed_assets.5_year_change)
  - For 10-year growth: 'fixed_asset_growth_10y' (NOT fixed_assets.10_year_change)
  - All values are in decimal form (e.g., 0.5 = 50% growth)
  - Ranges: -1.0 to 5.0+ (-100% to 500%+)
  - Example correct query: {'fixed_asset_growth_3y': {'$gte': 0.5}}
  - Example incorrect query: {'fixed_assets.3_year_change': {'$gte': 50}}

• 52-week price fields - IMPORTANT: Use these exact field names:
  - For 52-week high: 'year_high' (NOT fifty_two_week_high)
  - For 52-week low: 'year_low' (NOT fifty_two_week_low)
  - Range: $0.01-$1000+ (in USD)
  - Example correct query: {'current_price': {'$gte': {'$multiply': ['$year_high', 0.85]}}}
  - Example incorrect query: {'current_price': {'$gte': {'$multiply': ['$fifty_two_week_high', 0.85]}}}

• symbol vs ticker - IMPORTANT: Use 'ticker' not 'symbol':
  - Correct: 'ticker'
  - Incorrect: 'symbol'
  - Example correct query: {'ticker': 1}
  - Example incorrect query: {'symbol': 1}

**⚠️ QUERY VALIDATION RULES**:
1. Always validate field existence before querying
2. For calculated fields, ensure all components are available
3. Use appropriate field alternatives if primary field is missing
4. Apply range validation before executing queries
5. Handle null/missing values appropriately

**🔍 FIELD CATEGORIES**:
• Basic Info: ticker, company_name, sector, industry, etc.
• Growth: revenue_growth_*, eps_growth_*, etc.
• Margins: net_margin, operating_margin, ebitda_margin, etc.
• Financial Health: debt_to_equity, current_ratio, etc.
• Market Data: current_price, volume, market_cap, etc.
• Calculated Metrics: Require component fields and real-time calculation


            """
            
        }
    
    @lru_cache(maxsize=100)
    def _get_cached_response(self, query_hash: str) -> Optional[str]:
        """Get cached response - SAME pattern as investment bot"""
        try:
            if self.redis_client:
                cached = self.redis_client.get(f"stock_response:{query_hash}")
                if cached:
                    return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
        return None
     
    def _get_dynamic_sectors_inline(self) -> str:
        """Get dynamic sectors from cache for intelligent agent context"""
        try:
            popular_stocks = self.stock_cache.get('popular_stocks', [])
            sectors = set()
            for stock in popular_stocks[:30]:  # Top 30 stocks
                if stock.get('sector'):
                    sectors.add(stock['sector'])
            
            if sectors:
                sector_list = sorted(list(sectors))
                return f"🏭 LIVE SECTORS: {', '.join(sector_list[:10])}"  # Top 10 sectors
            else:
                return "🏭 SECTORS: Technology, Healthcare, Financials, Consumer Discretionary, Industrials"
        except Exception as e:
            return "🏭 SECTORS: Technology, Healthcare, Financials, Consumer Discretionary, Industrials"
    
    def _format_user_context(self, user_context: Dict[str, Any]) -> str:
        """Format user context for the system prompt - handles both old and new formats"""
        try:
            # Handle new structured format with query_parameters
            if user_context.get('query_parameters'):
                user_id = user_context.get('user_id', 'unknown')
                session_context = user_context.get('session_context', 'unknown')
                query_parameters = user_context.get('query_parameters', {})
                
                # Create a more explicit context mapping for vague references
                vague_reference_map = {}
                
                # Map common vague terms to specific context parameters
                for key, value in query_parameters.items():
                    if isinstance(value, str):
                        # Map headlines or news
                        if 'headline' in key.lower():
                            vague_reference_map['it'] = f"the headline: '{value}'"
                            vague_reference_map['this'] = f"the news: '{value}'"
                            vague_reference_map['that'] = f"the market news: '{value}'"
                        
                        # Map specific components
                        elif key == 'component':
                            vague_reference_map['here'] = f"the {value} section"
                            vague_reference_map['this section'] = f"the {value} component"
                        
                        # Map symbols or tickers
                        elif any(term in key.lower() for term in ['symbol', 'ticker', 'stock', 'gainer', 'loser']):
                            vague_reference_map['this stock'] = f"the stock {value}"
                            vague_reference_map['it'] = vague_reference_map.get('it', f"the stock {value}")
                
                context_section = f"""🎯 === CRITICAL USER CONTEXT AND REFERENCE RESOLUTION ===
CURRENT USER FRONTEND CONTEXT:
- User ID: {user_id}
- Session: {session_context}
- Active View Parameters:
"""
                # Add all query parameters in a structured format
                for key, value in query_parameters.items():
                    formatted_key = key.replace('_', ' ').title()
                    context_section += f"  • {formatted_key}: {value}\n"
                
                # Add explicit vague reference resolution
                context_section += "\n🔍 VAGUE REFERENCE RESOLUTION MAP:\n"
                for vague_term, specific_reference in vague_reference_map.items():
                    context_section += f"  • When user says '{vague_term}' → They mean {specific_reference}\n"
                
                context_section += """
⚠️ CRITICAL CONTEXT HANDLING INSTRUCTIONS:
1. ALWAYS CHECK THIS CONTEXT FIRST when encountering vague references like:
   - "it", "this", "that", "here", "this section", "this stock"
   - "tell me about it", "analyze this", "what about that"
   - "give me a summary", "explain this to me"

2. IMMEDIATE CONTEXT APPLICATION:
   - Use this context WITHOUT asking for clarification if it matches
   - The user is actively viewing this content, so it's the primary context
   - Treat this as the user pointing to something on their screen

3. QUERY RESOLUTION PRIORITY:
   1st: Check for exact matches in the reference map above
   2nd: Look for relevant component or section context
   3rd: Consider the overall page/view context
   
4. ONLY ASK FOR CLARIFICATION IF:
   - The query is vague AND
   - No matching context exists above AND
   - The context seems completely unrelated

🎯 === END CRITICAL CONTEXT ==="""
                return context_section
            
            # Handle legacy string format with query_metadata
            elif user_context.get('query_metadata'):
                query_metadata = user_context.get('query_metadata')
                if not query_metadata or not isinstance(query_metadata, str):
                    return ""
                
                context_section = f"""🎯 === CRITICAL USER CONTEXT - READ FIRST ===
The user is currently viewing:
{query_metadata}

⚠️ CRITICAL CONTEXT HANDLING INSTRUCTIONS:
- Treat this context as the user's current view
- Use this context for vague references without asking
- Only ask for clarification if genuinely unrelated
🎯 === END CRITICAL USER CONTEXT ==="""
                return context_section
            
            return ""
            
        except Exception as e:
            logger.error(f"Error formatting user context: {e}")
            return ""
    
    def _get_current_market_context(self) -> str:
        """Get comprehensive current market context using all cached data"""
        try:
            context_parts = []
            
            # 🔍 DEBUG: Log cache data structure for troubleshooting
            logger.debug("=== MARKET CONTEXT DEBUG ===")
            for key, value in self.stock_cache.items():
                if isinstance(value, list):
                    logger.debug(f"{key}: {len(value)} items")
                    if value and len(value) > 0:
                        logger.debug(f"Sample {key} item: {value[0]}")
                else:
                    logger.debug(f"{key}: {type(value)}")
            logger.debug("=== END DEBUG ===")
            
            # 📊 MAJOR MARKET INDICES
            market_indices = self.stock_cache.get('market_indices', [])
            if market_indices:
                major_indices = []
                seen_symbols = set()  # Prevent duplicates
                
                for index in market_indices[:7]:  # Get more indices but filter duplicates
                    symbol = index.get('symbol', 'Unknown')
                    name = index.get('name', symbol)
                    
                    # Skip duplicates based on symbol
                    if symbol in seen_symbols:
                        continue
                    seen_symbols.add(symbol)
                    
                    price = index.get('price', 'N/A')
                    change_pct = index.get('change_percentage', index.get('changes_percentage', 0))
                    
                    # Create display name (prefer name over symbol, but keep it short)
                    display_name = name if len(name) < 25 else symbol
                    
                    if isinstance(change_pct, (int, float)) and isinstance(price, (int, float)):
                        major_indices.append(f"{display_name}: {price:.2f} ({change_pct:+.2f}%)")
                    elif isinstance(price, (int, float)):
                        major_indices.append(f"{display_name}: {price:.2f}")
                    else:
                        major_indices.append(f"{display_name}: {price}")
                
                if major_indices:
                    context_parts.append(f"📊 MAJOR INDICES: {' | '.join(major_indices)}")
            
            # 🚀 MARKET SENTIMENT FROM MOVERS
            top_gainers = self.stock_cache.get('top_gainers', [])
            top_losers = self.stock_cache.get('top_losers', [])
            
            if top_gainers and top_losers:
                # Calculate market sentiment
                avg_gain = sum(g.get('change_percentage', g.get('changes_percentage', 0)) for g in top_gainers[:5]) / min(5, len(top_gainers))
                avg_loss = sum(abs(l.get('change_percentage', l.get('changes_percentage', 0))) for l in top_losers[:5]) / min(5, len(top_losers))
                
                # Get top mover examples
                top_gainer = top_gainers[0] if top_gainers else {}
                top_loser = top_losers[0] if top_losers else {}
                
                sentiment_parts = []
                if top_gainer:
                    gain_pct = top_gainer.get('change_percentage', top_gainer.get('changes_percentage', 0))
                    sentiment_parts.append(f"Top Gainer: {top_gainer.get('symbol', 'N/A')} (+{gain_pct:.1f}%)")
                
                if top_loser:
                    loss_pct = abs(top_loser.get('change_percentage', top_loser.get('changes_percentage', 0)))
                    sentiment_parts.append(f"Top Loser: {top_loser.get('symbol', 'N/A')} (-{loss_pct:.1f}%)")
                
                # Market sentiment indicator
                if avg_gain > avg_loss * 1.5:
                    sentiment = "BULLISH"
                elif avg_loss > avg_gain * 1.5:
                    sentiment = "BEARISH"
                else:
                    sentiment = "MIXED"
                
                sentiment_summary = f"🚀 MARKET SENTIMENT: {sentiment}"
                if sentiment_parts:
                    sentiment_summary += f" | {' | '.join(sentiment_parts)}"
                
                context_parts.append(sentiment_summary)
            
            # 📈 MOST ACTIVE STOCKS
            sector_performance = self.stock_cache.get('sector_performance', [])
            logger.debug(f"Sector performance data: {len(sector_performance) if sector_performance else 0} items")
            
            if sector_performance:
                active_stocks = []
                
                for stock in sector_performance[:6]:  # Top 6 most active
                    symbol = stock.get('symbol', 'N/A')
                    name = stock.get('name', symbol)
                    
                    # Use symbol for display (cleaner)
                    display_symbol = symbol if symbol != 'N/A' else name
                    
                    # Try multiple field names for change percentage
                    change_pct = (stock.get('change_percentage') or 
                                stock.get('changes_percentage') or 
                                stock.get('price_change_percentage') or
                                stock.get('change') or 0)
                    
                    if isinstance(change_pct, (int, float)) and change_pct != 0:
                        active_stocks.append(f"{display_symbol} ({change_pct:+.1f}%)")
                    else:
                        # Even without percentage, show the active stock
                        active_stocks.append(f"{display_symbol}")
                
                if active_stocks:
                    context_parts.append(f"📈 MOST ACTIVE: {' | '.join(active_stocks)}")
            else:
                # Fallback: Use popular stocks as "active" if sector_performance is empty
                popular_stocks = self.stock_cache.get('popular_stocks', [])
                if popular_stocks:
                    active_stocks = []
                    for stock in popular_stocks[:4]:  # Top 4 popular as active
                        symbol = stock.get('symbol', 'N/A')
                        change_pct = (stock.get('price_change') or 
                                    stock.get('changes') or 
                                    stock.get('change_percentage') or 0)
                        
                        if isinstance(change_pct, (int, float)) and change_pct != 0:
                            active_stocks.append(f"{symbol} ({change_pct:+.1f}%)")
                        else:
                            active_stocks.append(f"{symbol}")
                    
                    if active_stocks:
                        context_parts.append(f"📈 POPULAR STOCKS: {' | '.join(active_stocks)}")
            
            # 💼 POPULAR STOCKS OVERVIEW
            popular_stocks = self.stock_cache.get('popular_stocks', [])
            if popular_stocks:
                # Get key popular stocks with their current performance
                key_stocks = []
                for stock in popular_stocks[:4]:  # Top 4 popular stocks
                    symbol = stock.get('symbol', 'N/A')
                    price = stock.get('price', 'N/A')
                    change = stock.get('price_change', stock.get('changes', 0))
                    
                    if isinstance(price, (int, float)) and isinstance(change, (int, float)):
                        key_stocks.append(f"{symbol}: ${price:.2f} ({change:+.2f})")
                    else:
                        key_stocks.append(f"{symbol}: ${price}")
                
                if key_stocks:
                    context_parts.append(f"💼 KEY STOCKS: {' | '.join(key_stocks)}")
            
            # 📊 MARKET STATISTICS SUMMARY
            stats_parts = []
            
            # Count active gainers vs losers for market breadth
            gainers_count = len(top_gainers)
            losers_count = len(top_losers)
            if gainers_count > 0 and losers_count > 0:
                breadth_ratio = gainers_count / (gainers_count + losers_count)
                if breadth_ratio > 0.6:
                    breadth = "POSITIVE"
                elif breadth_ratio < 0.4:
                    breadth = "NEGATIVE"
                else:
                    breadth = "NEUTRAL"
                stats_parts.append(f"Breadth: {breadth}")
            
            # Market activity level
            total_active = len(sector_performance) if sector_performance else 0
            if total_active > 20:
                activity = "HIGH"
            elif total_active > 10:
                activity = "MODERATE"
            else:
                activity = "LOW"
            stats_parts.append(f"Activity: {activity}")
            
            if stats_parts:
                context_parts.append(f"📊 MARKET STATS: {' | '.join(stats_parts)}")
            
            # 🕐 TIMESTAMP
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M EST')
            context_parts.append(f"🕐 UPDATED: {current_time}")
            
            # 🔍 FINAL DEBUG: Log what context parts we generated
            logger.debug(f"Generated context parts: {len(context_parts)}")
            for i, part in enumerate(context_parts):
                logger.debug(f"Part {i+1}: {part[:100]}...")
            
            # Combine all context parts
            if context_parts:
                final_context = "\n".join(context_parts)
                logger.debug(f"Final context length: {len(final_context)} chars")
                return final_context
            else:
                logger.warning("No context parts generated - using fallback")
                return "📊 MARKET STATUS: Data loading..."
                
        except Exception as e:
            logger.error(f"Error getting comprehensive market context: {e}", exc_info=True)
            return "📊 MARKET STATUS: Unable to fetch current market data"
    
    async def analyze_and_respond_enhanced_stream(self, user_message: str, conversation_id: str, user_id: str, user_context: Optional[Dict[str, Any]] = None):
        """Enhanced stock analysis with TRUE streaming - IMPROVED WITH VALIDATION"""
        
        start_time = time.time()
        
        try:
            # IMMEDIATE RESPONSE (0-200ms)
            yield create_processing_event('🔍 Analyzing your request...', ProcessingStatus.STARTED, "stock")
            
            # SIMPLE PROGRESS MESSAGE - Consumer bot will decide if analysis is needed
            yield create_processing_event('🔍 Processing your request...', ProcessingStatus.EXECUTING, "stock")
            
            # 🚀 GET CONVERSATION CONTEXT - ENHANCED LOGGING
            if self.conversation_manager and self.conversation_manager.enabled:
                logger.info(f"💬 CONVERSATION MANAGER: Enabled - fetching context for thread {conversation_id}")
                try:
                    context = await self.conversation_manager.get_smart_context(conversation_id)
                    context_type = context.get('type', 'unknown')
                    recent_count = len(context.get('recent_messages', []))
                    summary_length = len(context.get('summary', ''))
                    
                    logger.info(f"💬 CONTEXT RETRIEVED: Type={context_type}, Messages={recent_count}, Summary={summary_length} chars")
                    
                    # Build messages with context
                    messages = self._build_context_prompt(context, user_message)
                    logger.info(f"💬 CONTEXT INTEGRATION: Built {len(messages)} messages from context")
                    logger.info(f"💬 MESSAGE ROLES: {[msg['role'] for msg in messages]}")
                    
                    # Log context quality for debugging
                    if recent_count > 0:
                        logger.info(f"💬 CONTEXT QUALITY: Using {recent_count} recent messages for continuity")
                    else:
                        logger.warning(f"⚠️ CONTEXT WARNING: No recent messages found - conversation may lack continuity")
                        
                except Exception as e:
                    logger.error(f"❌ CONVERSATION CONTEXT FAILED: {e}")
                    logger.error("❌ Falling back to single message - conversation continuity lost")
                    messages = [{"role": "user", "content": user_message}]
            else:
                # No context - simple single message
                messages = [{"role": "user", "content": user_message}]
                logger.warning("⚠️ CONVERSATION MANAGER: Disabled or unavailable - no conversation continuity")
                logger.info("💬 FALLBACK: Using single message mode")
            
            # Use pre-built system prompt (MINIMAL CHANGE OPTIMIZATION - 50-100x faster)
            system_prompt = self.prebuilt_system_prompt or self._create_stock_system_prompt_with_bootstrap(datetime.now(), user_context)
            
            # Get stock-specific tools
            tools = self.tools_manager.get_comprehensive_stock_tools()
            
            # Stream the analysis using SHARED streaming service
            full_response = ""
            tool_results = []
            data_tables = []
            charts = []
            
            async for chunk in self.shared_streaming.call_claude_with_tools_stream(
                system_prompt, messages, tools, user_id, conversation_id, "stock"
            ):
                if chunk.get('type') == 'response_chunk':
                    full_response += chunk.get('content', '')
                    yield chunk
                elif chunk.get('type') == StreamingEventTypes.TOOLS_TO_EXECUTE:
                    # Handle tool execution using stock-specific tools
                    yield create_processing_event('Executing stock analysis tools...', ProcessingStatus.TOOLS, "stock")
                    
                    for tool_use in chunk.get('tool_uses', []):
                        tool_name = tool_use.get('name')
                        tool_input = tool_use.get('input', {})
                        
                        # Inject user context and optimization
                        if user_id:
                            tool_input['user_id'] = user_id
                        if conversation_id:
                            tool_input['conversation_id'] = conversation_id
                        
                        # Pass user context for tools
                        tool_input['user_query'] = user_message  # FIX: Use user_query not user_message
                        tool_input['user_message'] = user_message  # Keep both for backward compatibility
                        
                        logger.info(f"🔧 Executing stock tool: {tool_name}")
                        yield create_tool_execution_event(tool_name, ProcessingStatus.EXECUTING, "stock")
                        
                        # Execute tool using stock-specific tool manager
                        tool_result = await self._execute_tool(tool_name, tool_input)
                        
                        # 🔍 ENHANCED CONVERSATION & QUERY AGENT LOGGING
                        if tool_name == "analyze_stock_query" and tool_result.get("success"):
                            communication_msg = tool_result.get("communication_message", "🔍 Analyzing your request...")
                            intent = tool_result.get("intent", "UNKNOWN")
                            confidence = tool_result.get("confidence", 0)
                            processing_path = tool_result.get("processing_path", "UNKNOWN")
                            field_count = tool_result.get("field_count", 0)
                            estimated_results = tool_result.get("estimated_results", 0)
                            
                            # 🧠 INTELLIGENT QUERY AGENT ANALYSIS LOGGING
                            logger.info(f"🧠 QUERY AGENT ANALYSIS:")
                            logger.info(f"   Intent: {intent} | Confidence: {confidence:.2f}")
                            logger.info(f"   Processing Path: {processing_path}")
                            logger.info(f"   Fields Selected: {field_count} | Est. Results: {estimated_results}")
                            logger.info(f"   Communication: {communication_msg}")
                            
                            # 💬 CONVERSATION CONTEXT INTEGRATION
                            logger.info(f"💬 CONVERSATION FLOW:")
                            logger.info(f"   Thread: {conversation_id} | User: {user_id}")
                            logger.info(f"   Query Processing: {tool_name}")
                            
                            # Always yield the communication message
                            yield create_processing_event(
                                communication_msg, 
                                ProcessingStatus.EXECUTING,
                                "stock"
                            )
                            logger.info(f"💬 User Communication Sent: {communication_msg}")
                            
                            # Also try to get results count for better messaging
                            results_count = tool_result.get("results_count", 0)
                            if results_count > 0:
                                yield create_processing_event(
                                    f"📊 Found {results_count} matching stocks - analyzing...", 
                                    ProcessingStatus.EXECUTING,
                                    "stock"
                                )
                                logger.info(f"📊 QUERY RESULTS: {results_count} stocks found")
                        
                        # Ensure tool_name is tracked in the result
                        if not tool_result.get("tool_name"):
                            tool_result["tool_name"] = tool_name
                        
                        tool_results.append({
                            "tool_use_id": tool_use.get('id'),
                            "content": json.dumps(tool_result),
                            "tool_name": tool_name  # Explicit tool name for tracking
                        })
                        
                        yield {'type': StreamingEventTypes.TOOL_RESULT, 'tool_name': tool_name, 'result': tool_result}
                        
                        # Process tool results for data tables and charts
                        self._process_tool_result_for_streaming(tool_result, data_tables, charts, yield_func=lambda x: None)
                    
                    # If tools were used, make second call for final response
                    if tool_results:
                        # ENHANCED: Extract intelligent analysis for MongoDB tool injection
                        self._inject_intelligent_analysis_to_mongodb_tools(tool_results)
                        
                        yield create_processing_event('Generating final stock analysis...', ProcessingStatus.FINAL, "stock")
                        
                        # Prepare tool result content
                        tool_result_content = []
                        for result in tool_results:
                            tool_result_content.append({
                                "type": "tool_result",
                                "tool_use_id": result["tool_use_id"],
                                "content": result["content"]
                            })
                        
                        # Build second call messages ensuring user message comes first
                        # Get original user message (should be the first or one of the early messages)
                        original_user_message = None
                        for msg in messages:
                            if msg.get('role') == 'user':
                                original_user_message = msg
                                break
                        
                        # Create clean messages array for second call starting with user
                        second_call_messages = []
                        
                        if original_user_message:
                            second_call_messages.append(original_user_message)
                        else:
                            # Fallback: create a generic user message
                            second_call_messages.append({
                                "role": "user", 
                                "content": "Please analyze the following tool results and provide a comprehensive response."
                            })
                        
                        # Add assistant response with tool calls
                        # Ensure text content is not empty (AWS Bedrock validation requirement)
                        response_text_content = chunk.get('response_text', '').strip()
                        if not response_text_content:
                            response_text_content = "Processing your request..."
                        
                        assistant_content = [{"type": "text", "text": response_text_content}]
                        tool_uses = chunk.get('tool_uses', [])
                        if tool_uses:
                            assistant_content.extend(tool_uses)
                        
                        second_call_messages.append({
                            "role": "assistant",
                            "content": assistant_content
                        })
                        
                        # Add user message with tool results
                        second_call_messages.append({
                            "role": "user",
                            "content": tool_result_content
                        })
                        
                        # Validate the messages array starts with user
                        if second_call_messages[0]['role'] != 'user':
                            logger.error("❌ Second call messages don't start with user role!")
                            # Emergency fix: prepend a user message
                            second_call_messages.insert(0, {
                                "role": "user",
                                "content": "Please process the following conversation and tool results."
                            })
                        
                        logger.info(f"✅ Second call messages prepared: {[msg['role'] for msg in second_call_messages]}")
                        
                        # Stream second call using shared service
                        final_text = ""
                        async for second_chunk in self.shared_streaming.handle_second_call_stream(
                            second_call_messages, tools, "stock"
                        ):
                            if second_chunk.get('type') == StreamingEventTypes.RESPONSE_CHUNK:
                                final_text += second_chunk.get('content', '')
                            yield second_chunk
                        
                        full_response = final_text
                elif chunk.get('type') == StreamingEventTypes.STREAMING_COMPLETE:
                    full_response = chunk.get('response_text', '')
                else:
                    # Pass through other chunk types
                    yield chunk
            
            # Stream generated data tables and charts
            for table in data_tables:
                yield {'type': StreamingEventTypes.DATA_TABLE, 'table': table}
            
            for chart in charts:
                yield {'type': StreamingEventTypes.CHART, 'chart': chart}
            
            # Build final result for conversation saving
            final_result = {
                "response": full_response,
                "data_tables": data_tables,
                "charts": charts,
                "quick_actions": [],
                "tools_used": [{"name": tr.get("tool_name", "unknown")} for tr in tool_results],
                "tool_results": tool_results,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "success": True
            }
            
            # Save conversation with error handling
            try:
                await self.conversation_manager.save_conversation_exchange(
                    conversation_id, user_message, final_result, user_id, self
                )
            except Exception as e:
                logger.error(f"Failed to save conversation: {e}")
                # Don't fail the entire request for conversation save issues
            
            # Yield final complete response
            yield {
                'type': StreamingEventTypes.FINAL_RESPONSE,
                'data': final_result
            }
            
        except Exception as e:
            logger.error(f"Stock streaming analysis error: {e}")
            yield create_error_event(
                f"I encountered an error during stock analysis: {str(e)}",
                str(e),
                "stock"
            )
    
    async def analyze_and_respond_enhanced(self, user_message: str, conversation_id: str, user_id: str, user_context: Optional[Dict[str, Any]] = None) -> Dict:
        """Enhanced stock analysis with conversation persistence - SAME method as investment bot"""
        
        start_time = time.time()
        
        try:
            # 🚀 GET CONVERSATION CONTEXT - ENHANCED LOGGING (NON-STREAMING)
            if self.conversation_manager and self.conversation_manager.enabled:
                logger.info(f"💬 CONVERSATION MANAGER: Enabled - fetching context for thread {conversation_id}")
                try:
                    context = await self.conversation_manager.get_smart_context(conversation_id)
                    context_type = context.get('type', 'unknown')
                    recent_count = len(context.get('recent_messages', []))
                    summary_length = len(context.get('summary', ''))
                    
                    logger.info(f"💬 CONTEXT RETRIEVED: Type={context_type}, Messages={recent_count}, Summary={summary_length} chars")
                    
                    # Build messages with context
                    messages = self._build_context_prompt(context, user_message)
                    logger.info(f"💬 CONTEXT INTEGRATION: Built {len(messages)} messages from context")
                    logger.info(f"💬 MESSAGE ROLES: {[msg['role'] for msg in messages]}")
                    
                    # Log context quality for debugging
                    if recent_count > 0:
                        logger.info(f"💬 CONTEXT QUALITY: Using {recent_count} recent messages for continuity")
                    else:
                        logger.warning(f"⚠️ CONTEXT WARNING: No recent messages found - conversation may lack continuity")
                        
                except Exception as e:
                    logger.error(f"❌ CONVERSATION CONTEXT FAILED: {e}")
                    logger.error("❌ Falling back to single message - conversation continuity lost")
                    messages = [{"role": "user", "content": user_message}]
            else:
                # No context - simple single message
                messages = [{"role": "user", "content": user_message}]
                logger.warning("⚠️ CONVERSATION MANAGER: Disabled or unavailable - no conversation continuity")
                logger.info("💬 FALLBACK: Using single message mode")
            
            # CONSISTENCY FIX: Use same system prompt as streaming method
            system_prompt = self.prebuilt_system_prompt or self._create_stock_system_prompt_with_bootstrap(datetime.now(), user_context)
            
            # Get stock-specific tools
            tools = self.tools_manager.get_comprehensive_stock_tools()
            
            # Call Claude with stock context (SAME method as investment bot)
            result = await self._call_claude_with_tools(
                system_prompt, messages, tools, user_id, conversation_id
            )
            
            # Save conversation (SHARED manager)
            await self.conversation_manager.save_conversation_exchange(
                conversation_id, user_message, result, user_id, self
            )
            
            # Add processing time
            processing_time = int((time.time() - start_time) * 1000)
            result["processing_time_ms"] = processing_time
            
            return result
            
        except Exception as e:
            logger.error(f"Stock analysis error: {e}")
            
            # 📊 Provide default token metrics for high-level errors
            error_token_metrics = {
                "total_input_tokens": 0,
                "total_input_chars": 0,
                "system_prompt_tokens": 0,
                "system_prompt_chars": 0,
                "messages_tokens": 0,
                "messages_chars": 0,
                "tools_tokens": 0,
                "tools_chars": 0,
                "estimated_output_tokens": 0,
                "estimated_output_chars": 0,
                "prompt_breakdown": {
                    "market_context_tokens": 0,
                    "database_schema_tokens": 0,
                    "base_prompt_tokens": 0,
                    "cache_data_tokens": 0,
                    "response_guidelines_tokens": 0,
                    "user_context_tokens": 0,
                }
            }
            
            return {
                "response": f"I encountered an issue analyzing your request: {str(e)}",
                "data_tables": [],
                "charts": [],
                "quick_actions": [],
                "tools_used": [],
                "tool_results": [],
                "token_metrics": error_token_metrics,  # 📊 Include token metrics even for high-level errors
                "error": str(e),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
    
    def _build_context_prompt(self, context: Dict, current_message: str) -> List[Dict]:
        """Build context prompt - Fixed with proper role alternation for Claude"""
        messages = []
        
        # Handle different context types returned by ConversationManager
        context_type = context.get('type', 'smart_context')
        
        if context_type == 'smart_context':
            # Smart context: use summary + recent_messages
            recent_messages = context.get('recent_messages', [])
            
            # Add recent messages (ensuring proper role alternation)
            for msg in recent_messages[-8:]:  # Last 8 messages (4 exchanges)
                if msg.get('role') and msg.get('content'):
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # Integrate summary into the system understanding rather than as separate message
            summary = context.get('summary', '')
            if summary and messages:
                # Prepend summary to the first user message if available
                first_user_idx = next((i for i, msg in enumerate(messages) if msg['role'] == 'user'), None)
                if first_user_idx is not None:
                    original_content = messages[first_user_idx]['content']
                    messages[first_user_idx]['content'] = f"[Context: {summary}]\n\n{original_content}"
                    
        else:
            # Full context: use all messages
            all_messages = context.get('messages', [])
            for msg in all_messages[-10:]:  # Last 10 messages (5 exchanges)
                if msg.get('role') and msg.get('content'):
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
        
        # Validate and fix role alternation BEFORE adding current message
        messages = self._ensure_role_alternation(messages)
        
        # Add current message (always user) - but check for consecutive user messages
        if messages and messages[-1]['role'] == 'user':
            # Last message is already user, merge or replace with current message
            logger.warning("⚠️ Last context message is user, replacing with current user message")
            messages[-1] = {"role": "user", "content": current_message}
        else:
            # Safe to add current user message
            messages.append({"role": "user", "content": current_message})
        
        # Final validation
        if not self._validate_role_alternation(messages):
            logger.error("❌ Role alternation validation failed even after fixes!")
            # Emergency fallback: just use current message
            messages = [{"role": "user", "content": current_message}]
        else:
            # Double-check the first message is user (Claude requirement)
            if messages and messages[0]['role'] != 'user':
                logger.error("❌ Final validation: First message is not user role!")
                # Emergency fallback: just use current message
                messages = [{"role": "user", "content": current_message}]
        
        # Enhanced context usage logging for debugging
        previous_count = len(messages) - 1 if messages else 0
        logger.info(f"📝 CONTEXT BUILD COMPLETE: Type={context_type}, Previous={previous_count}, Total={len(messages)}")
        logger.info(f"📝 ROLE SEQUENCE: {[msg['role'] for msg in messages]}")
        logger.info(f"✅ VALIDATION: First role={messages[0]['role'] if messages else 'EMPTY'}")
        
        # Log message content lengths for debugging token usage
        if messages:
            content_lengths = [len(msg.get('content', '')) for msg in messages]
            logger.info(f"📝 MESSAGE LENGTHS: {content_lengths} chars")
            total_content = sum(content_lengths)
            logger.info(f"📝 TOTAL CONTEXT: {total_content} chars (~{total_content//4} tokens)")
        
        return messages
    
    def _ensure_role_alternation(self, messages: List[Dict]) -> List[Dict]:
        """Ensure messages alternate between user and assistant roles"""
        if not messages:
            return messages
        
        fixed_messages = []
        last_role = None
        
        for msg in messages:
            current_role = msg.get('role')
            
            # Skip messages with same role as previous (except first message)
            if current_role == last_role:
                logger.warning(f"⚠️ Skipping duplicate {current_role} role message to maintain alternation")
                continue
                
            # Add message if role is different or it's the first message
            fixed_messages.append(msg)
            last_role = current_role
        
        # Ensure we start with a user message (Claude requirement)
        if fixed_messages and fixed_messages[0]['role'] != 'user':
            logger.warning("⚠️ First message not from user, finding first user message...")
            
            # Find the first user message and start from there
            first_user_idx = next((i for i, msg in enumerate(fixed_messages) if msg['role'] == 'user'), None)
            
            if first_user_idx is not None:
                # Start from the first user message and maintain alternation
                user_started_messages = fixed_messages[first_user_idx:]
                
                # Re-validate alternation from the user message
                final_messages = []
                expected_role = 'user'
                
                for msg in user_started_messages:
                    if msg['role'] == expected_role:
                        final_messages.append(msg)
                        expected_role = 'assistant' if expected_role == 'user' else 'user'
                    else:
                        logger.warning(f"⚠️ Skipping message with role {msg['role']}, expected {expected_role}")
                
                fixed_messages = final_messages
                logger.info(f"✅ Reconstructed conversation starting with user message, {len(fixed_messages)} messages")
            else:
                # No user messages found, return empty array - current message will be added later
                logger.warning("⚠️ No user messages found in context, starting fresh")
                fixed_messages = []
        
        return fixed_messages
    
    def _validate_role_alternation(self, messages: List[Dict]) -> bool:
        """Validate that roles properly alternate between user and assistant"""
        if not messages:
            return True
            
        # Check if first message is from user
        if messages[0]['role'] != 'user':
            logger.error(f"❌ First message role is {messages[0]['role']}, should be 'user'")
            return False
        
        # Check alternation
        for i in range(1, len(messages)):
            current_role = messages[i]['role']
            previous_role = messages[i-1]['role']
            
            if current_role == previous_role:
                logger.error(f"❌ Role alternation broken at index {i}: {previous_role} -> {current_role}")
                return False
                
            if current_role not in ['user', 'assistant']:
                logger.error(f"❌ Invalid role at index {i}: {current_role}")
                return False
        
        return True
    


    async def _call_claude_with_tools(self, system_prompt: str, messages: List[Dict], tools: List[Dict], user_id: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """Optimized Claude call with tool support - PERFORMANCE OPTIMIZED"""
        try:
            # 📊 PERFORMANCE LOGGING - Condensed and efficient
            system_prompt_size = len(system_prompt)
            messages_size = len(json.dumps(messages))
            tools_size = len(json.dumps(tools))
            total_input_size = system_prompt_size + messages_size + tools_size
            
            logger.info(f"🚀 CLAUDE API CALL - Model: {self.model_id} | User: {user_id} | Conversation: {conversation_id}")
            logger.info(f"📊 INPUT TOKENS: System={system_prompt_size//4:,} | Messages={messages_size//4:,} | Tools={tools_size//4:,} | Total=~{total_input_size//4:,}")
            
            # 🕐 START TIMING
            call_start_time = time.time()
            
            # Prepare request payload
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": 0.3,
                "system": system_prompt,
                "messages": messages,
                "tools": tools
            }
            
            # 🚀 FIRST MODEL CALL
            first_call_start = time.time()
            logger.info(f"🚀 FIRST CLAUDE API CALL STARTED")
            
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload)
            )
            
            first_call_time = time.time() - first_call_start
            response_body = json.loads(response['body'].read())
            response_size = len(json.dumps(response_body))
            
            logger.info(f"⚡ FIRST CALL: {first_call_time:.3f}s | Input: ~{total_input_size//4:,} tokens | Output: ~{response_size//4:,} tokens")
            
            # Handle Claude's response
            claude_response = response_body.get('content', [])
            
            # Extract text and tool calls
            response_text = ""
            tool_uses = []
            
            for content in claude_response:
                if content.get('type') == 'text':
                    response_text += content.get('text', '')
                elif content.get('type') == 'tool_use':
                    tool_uses.append(content)
            
            # Execute tools if Claude requested them
            tool_results = []
            for tool_use in tool_uses:
                tool_name = tool_use.get('name')
                tool_input = tool_use.get('input', {})
                tool_id = tool_use.get('id')
                
                logger.info(f"🔧 Executing tool: {tool_name}")
                
                # Add user context
                if user_id:
                    tool_input['user_id'] = user_id
                if conversation_id:
                    tool_input['conversation_id'] = conversation_id
                
                # Execute tool
                tool_result = await self._execute_tool(tool_name, tool_input)
                
                tool_results.append({
                    "tool_use_id": tool_id,
                    "content": json.dumps(tool_result)
                })
            
            # Second call if tools were used
            if tool_results:
                logger.info(f"🔄 SECOND CALL with {len(tool_results)} tool results")
                
                # Build tool result content
                tool_result_content = []
                for result in tool_results:
                    tool_result_content.append({
                        "type": "tool_result",
                        "tool_use_id": result["tool_use_id"],
                        "content": result["content"]
                    })
                
                # 📊 ENHANCED SYSTEM PROMPT: Explicitly ask for charts and tables + tool fallback
                minimal_prompt = """You are a stock market advisor. Analyze the tool results and provide a comprehensive response.

🎯 IMPORTANT: Generate structured data for frontend rendering:

📊 CHARTS: Based on the stock data in tool results, recommend specific chart types:
- Performance charts for returns/growth data
- Valuation charts for P/E, P/B ratios
- Comparison charts for multiple stocks
- Sector distribution charts
- Technical indicator charts

📋 DATA TABLES: Organize stock data into clear, readable tables with:
- Stock symbols, names, and key metrics
- Comparative analysis between stocks
- Sector breakdowns and rankings
- Financial ratios and performance metrics

🔄 TOOL RETRY LOGIC: If any tool result shows an error or insufficient data:
- Use the available tools to get the needed information
- Call "analyze_stock_query" if cache lookup failed
- Ensure you provide complete analysis using working tools

Include specific stock recommendations, analysis insights, and practical investment advice based on the data."""
                
                # Get original user message
                original_user_message = None
                for msg in messages:
                    if msg.get('role') == 'user':
                        original_user_message = msg
                        break
                
                # Build clean messages for second call
                user_content = original_user_message["content"] if original_user_message else "Please analyze the following tool results and provide a comprehensive stock analysis."
                
                minimal_messages = [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": claude_response},
                    {"role": "user", "content": tool_result_content}
                ]
                
                # Ensure valid role structure
                if minimal_messages[0]['role'] != 'user':
                    minimal_messages[0] = {"role": "user", "content": "Please process these tool results."}
                
                final_payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "temperature": 0.3,
                    "system": minimal_prompt,
                    "messages": minimal_messages,
                    "tools": tools
                }
                
                # SECOND CALL
                second_call_start = time.time()
                second_payload_size = len(json.dumps(final_payload))
                
                final_response = self.bedrock_runtime.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(final_payload)
                )
                
                second_call_time = time.time() - second_call_start
                final_body = json.loads(final_response['body'].read())
                final_response_size = len(json.dumps(final_body))
                
                logger.info(f"⚡ SECOND CALL: {second_call_time:.3f}s | Input: ~{second_payload_size//4:,} tokens | Output: ~{final_response_size//4:,} tokens")
                
                # Extract final response
                final_text = ""
                for content in final_body.get('content', []):
                    if content.get('type') == 'text':
                        final_text += content.get('text', '')
                
                response_text = final_text
                
                # Total performance summary
                total_time = first_call_time + second_call_time
                total_tokens = (total_input_size + second_payload_size) // 4
                logger.info(f"📊 TOTAL: {total_time:.3f}s | {total_tokens:,} tokens | {total_tokens/total_time:,.0f} tokens/sec")
            else:
                logger.info(f"📊 SINGLE CALL: {first_call_time:.3f}s | No tool calls required")
            
            # Generate structured response
            data_tables = []
            charts = []
            
            # 🚫 REMOVED AUTO-CHART GENERATION: Only charts from actual tool results now
            logger.info("📊 Auto-chart generation disabled - charts only from tool results")
            
            # Process tool results for data tables and charts
            for result in tool_results:
                result_data = json.loads(result["content"])
                
                # 📊 HANDLE PORTFOLIO CHARTS: Extract charts from multiple locations
                # Check top-level charts
                if result_data.get("charts"):
                    portfolio_charts = result_data["charts"]
                    if isinstance(portfolio_charts, list):
                        charts.extend(portfolio_charts)
                        logger.info(f"✅ Added {len(portfolio_charts)} top-level portfolio charts to response")
                
                # Check data.charts (for portfolio tools) - safely handle list vs dict
                data_field = result_data.get("data")
                if data_field and isinstance(data_field, dict) and data_field.get("charts"):
                    data_charts = data_field["charts"]
                    if isinstance(data_charts, list):
                        charts.extend(data_charts)
                        logger.info(f"✅ Added {len(data_charts)} data-level portfolio charts to response")
                
                # Handle data tables (existing logic) - safely handle different data structures
                data_field = result_data.get("data")
                if data_field:
                    if isinstance(data_field, list):
                        limited_data = data_field[:50]  # Limit for display
                        # Add data table
                        data_tables.append({
                            "title": result_data.get("title", "Query Results"),
                            "data": limited_data
                        })
                        
                        # 📊 GENERATE CHARTS: Create charts for stock data visualization
                        try:
                            logger.info(f"🔍 DEBUG: Attempting chart generation with {len(limited_data)} data items")
                            logger.info(f"🔍 DEBUG: Sample data item: {limited_data[0] if limited_data else 'No data'}")
                            
                            # Generate charts based on the tool data
                            generated_charts = self.chart_generator.suggest_charts_for_stock_data(
                                data=limited_data, 
                                analysis_type="general"
                            )
                            if generated_charts:
                                charts.extend(generated_charts)
                                logger.info(f"✅ Generated {len(generated_charts)} charts from tool data")
                            else:
                                logger.warning(f"⚠️ No charts generated from {len(limited_data)} data items - checking data structure")
                                # Additional debug info
                                if limited_data:
                                    sample_keys = list(limited_data[0].keys()) if isinstance(limited_data[0], dict) else []
                                    logger.info(f"🔍 Sample data keys: {sample_keys}")
                        except Exception as e:
                            logger.error(f"Chart generation error: {e}")
                        
                    elif isinstance(data_field, dict):
                        # Handle dict data (like portfolio results)
                        data_tables.append({
                            "title": result_data.get("title", "Portfolio Results"),
                            "data": data_field
                        })
                        
                        # 📊 GENERATE CHARTS: Extract arrays from dict for chart generation
                        try:
                            chart_data = []
                            
                            # Check for market_indices, popular_stocks, etc. arrays within the dict
                            for key, value in data_field.items():
                                if isinstance(value, list) and len(value) > 0:
                                    chart_data.extend(value)
                                    logger.info(f"🔍 Found array '{key}' with {len(value)} items for chart generation")
                            
                            if chart_data:
                                logger.info(f"🔍 DEBUG: Attempting chart generation with {len(chart_data)} dict-extracted items")
                                logger.info(f"🔍 DEBUG: Sample dict-extracted item: {chart_data[0] if chart_data else 'No data'}")
                                
                                # Generate charts based on the extracted array data
                                generated_charts = self.chart_generator.suggest_charts_for_stock_data(
                                    data=chart_data[:30],  # Limit for performance
                                    analysis_type="general"
                                )
                                if generated_charts:
                                    charts.extend(generated_charts)
                                    logger.info(f"✅ Generated {len(generated_charts)} charts from dict-extracted data")
                                else:
                                    logger.warning(f"⚠️ No charts generated from {len(chart_data)} dict-extracted items")
                                    if chart_data:
                                        sample_keys = list(chart_data[0].keys()) if isinstance(chart_data[0], dict) else []
                                        logger.info(f"🔍 Sample dict-extracted data keys: {sample_keys}")
                        except Exception as e:
                            logger.error(f"Dict chart generation error: {e}")
                    else:
                        # Handle other data types
                        data_tables.append({
                            "title": result_data.get("title", "Query Results"),
                            "data": [data_field] if data_field else []
                        })
            
            # Calculate final metrics
            processing_time = int((time.time() - call_start_time) * 1000)
            
            # Calculate model timing metrics safely
            total_model_time = first_call_time + (second_call_time if 'second_call_time' in locals() else 0)
            total_tokens_processed = (total_input_size // 4) + (second_payload_size // 4 if 'second_payload_size' in locals() else 0)
            
            token_metrics = {
                "total_input_tokens": total_input_size // 4,
                "total_input_chars": total_input_size,
                "system_prompt_tokens": system_prompt_size // 4,
                "system_prompt_chars": system_prompt_size,
                "messages_tokens": messages_size // 4,
                "messages_chars": messages_size,
                "tools_tokens": tools_size // 4,
                "tools_chars": tools_size,
                "estimated_output_tokens": len(response_text) // 4,
                "estimated_output_chars": len(response_text),
                # 🕐 MODEL RESPONSE TIMING METRICS
                "model_timing": {
                    "first_call_time_seconds": round(first_call_time, 3),
                    "second_call_time_seconds": round(second_call_time, 3) if 'second_call_time' in locals() else 0,
                    "total_model_time_seconds": round(total_model_time, 3),
                    "total_tokens_processed": total_tokens_processed,
                    "tokens_per_second": round(total_tokens_processed / total_model_time, 0) if total_model_time > 0 else 0,
                    "has_tool_calls": 'second_call_time' in locals(),
                    "call_initiated_at": time.strftime('%H:%M:%S', time.localtime(call_start_time)),
                    "call_completed_at": time.strftime('%H:%M:%S', time.localtime())
                }
            }
            
            # Add detailed prompt breakdown (always provide, even if empty)
            if hasattr(self, '_last_prompt_breakdown') and self._last_prompt_breakdown:
                token_metrics["prompt_breakdown"] = {
                    "market_context_tokens": self._last_prompt_breakdown.get('market_context', 0) // 4,
                    "database_schema_tokens": self._last_prompt_breakdown.get('database_schema', 0) // 4,
                    "base_prompt_tokens": self._last_prompt_breakdown.get('base_prompt_header', 0) // 4,
                    "cache_data_tokens": self._last_prompt_breakdown.get('cache_data_section', 0) // 4,
                    "response_guidelines_tokens": self._last_prompt_breakdown.get('response_guidelines', 0) // 4,
                    "user_context_tokens": self._last_prompt_breakdown.get('user_context', 0) // 4,
                }
            else:
                # Provide default breakdown when detailed tracking is not available
                token_metrics["prompt_breakdown"] = {
                    "market_context_tokens": 0,
                    "database_schema_tokens": 0,
                    "base_prompt_tokens": 0,
                    "cache_data_tokens": 0,
                    "response_guidelines_tokens": 0,
                    "user_context_tokens": 0,
                }

            final_response = {
                "response": response_text,
                "data_tables": data_tables,
                "charts": charts,
                "quick_actions": [],
                "tools_used": [{"name": use.get("name", "unknown"), "input": use.get("input", {})} for use in tool_uses],
                "tool_results": tool_results,
                "token_metrics": token_metrics  # 📊 NEW: Include token usage in API response
            }
            
            # LOG TRANSPARENT: Final response structure
            logger.info("🔍 TRANSPARENT LOG - Final Response:")
            logger.info(f"Response Text: {response_text[:200]}...")
            logger.info(f"Data Tables: {len(data_tables)} tables")
            logger.info(f"Charts: {len(charts)} charts")
            logger.info(f"Tools Used: {[tool['name'] for tool in final_response['tools_used']]}")
            
            return final_response
            
        except Exception as e:
            logger.error(f"❌ Claude call failed: {e}")
            
            # 📊 Provide default token metrics even for errors
            error_token_metrics = {
                "total_input_tokens": 0,
                "total_input_chars": 0,
                "system_prompt_tokens": 0,
                "system_prompt_chars": 0,
                "messages_tokens": 0,
                "messages_chars": 0,
                "tools_tokens": 0,
                "tools_chars": 0,
                "estimated_output_tokens": 0,
                "estimated_output_chars": 0,
                "prompt_breakdown": {
                    "market_context_tokens": 0,
                    "database_schema_tokens": 0,
                    "base_prompt_tokens": 0,
                    "cache_data_tokens": 0,
                    "response_guidelines_tokens": 0,
                    "user_context_tokens": 0,
                }
            }
            
            return {
                "response": f"I encountered an issue analyzing your request: {str(e)}",
                "data_tables": [],
                "charts": [],
                "quick_actions": [],
                "tools_used": [],
                "tool_results": [],
                "token_metrics": error_token_metrics,  # 📊 Include token metrics even for errors
                "error": str(e)
            }
    
    def _analyze_messages_breakdown(self, messages: List[Dict]) -> Dict[str, Any]:
        """Analyze messages for detailed token breakdown"""
        breakdown = {
            'total_messages': len(messages),
            'user_messages': 0,
            'assistant_messages': 0,
            'user_chars': 0,
            'assistant_chars': 0
        }
        
        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')
            
            # Handle different content types (string vs list)
            if isinstance(content, list):
                content_str = json.dumps(content)
            else:
                content_str = str(content)
            
            content_len = len(content_str)
            
            if role == 'user':
                breakdown['user_messages'] += 1
                breakdown['user_chars'] += content_len
            elif role == 'assistant':
                breakdown['assistant_messages'] += 1
                breakdown['assistant_chars'] += content_len
        
        return breakdown
    
    def _analyze_tools_breakdown(self, tools: List[Dict]) -> Dict[str, int]:
        """Analyze tools for detailed token breakdown"""
        breakdown = {}
        
        for tool in tools:
            tool_name = tool.get('name', 'unknown_tool')
            tool_size = len(json.dumps(tool, indent=2))
            breakdown[tool_name] = tool_size
        
        return breakdown

    async def _execute_tool(self, tool_name: str, tool_input: Dict) -> Dict[str, Any]:
        """Execute tool - SAME pattern as investment bot"""
        try:
            # Delegate to tools manager (same pattern as investment bot)
            return await self.tools_manager.execute_tool(tool_name, tool_input)
            
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {"error": str(e), "success": False}
    
    def _process_tool_result_for_streaming(self, tool_result: Dict, data_tables: List, charts: List, yield_func):
        """
        Process tool results for streaming response
        Enhanced to handle intelligent analysis and chart suggestions
        """
        try:
            # 🎯 COMPREHENSIVE DATA EXTRACTION LOG
            logger.info(f"🔍 Processing tool result - Available keys: {list(tool_result.keys())}")
            logger.info(f"🔍 This is the Tool result: {tool_result}")
            
            # Extract data from multiple possible fields (MongoDB results have different structure)
            extracted_data = None
            data_source = None
            
            # Check for MongoDB stock results (the missing piece!)
            if tool_result.get("stock_results"):
                extracted_data = tool_result["stock_results"]
                data_source = "stock_results"
                logger.info(f"✅ Found stock_results: {len(extracted_data)} items")
            
            # Check for traditional data field  
            elif tool_result.get("data"):
                extracted_data = tool_result["data"]
                data_source = "data"
                logger.info(f"✅ Found data field: {type(extracted_data)}")
            
            # Check for results field
            elif tool_result.get("results"):
                extracted_data = tool_result["results"] 
                data_source = "results"
                logger.info(f"✅ Found results field: {type(extracted_data)}")
            
            else:
                logger.warning(f"⚠️ No data found in tool result. Available keys: {list(tool_result.keys())}")
                return
            
            # Process extracted data
            if extracted_data:
                if isinstance(extracted_data, list):
                    limited_data = extracted_data[:50]  # Limit for display
                    
                    # Build meaningful table title
                    tool_name = tool_result.get("tool_name", "Unknown")
                    results_count = tool_result.get("results_count", len(limited_data))
                    title = f"{tool_name} Results ({results_count} stocks found)"
                    
                    table_data = {
                        "title": title,
                        "data": limited_data,
                        "source": data_source,
                        "total_count": results_count
                    }
                    data_tables.append(table_data)
                
                # 📊 NEW: Process viable charts from tool result
                viable_charts = tool_result.get("viable_charts", [])
                if viable_charts:
                    logger.info(f"📊 PROCESSING {len(viable_charts)} VIABLE CHARTS for streaming")
                    
                    for chart_config in viable_charts:
                        # Build complete chart data for frontend
                        chart_data = {
                            "id": f"chart_{chart_config['type']}_{chart_config['priority']}",
                            "type": chart_config["chart_type"],  # bar, pie, scatter
                            "chart_subtype": chart_config["type"],  # performance_bar, sector_pie, etc.
                            "title": chart_config["title"],
                            "priority": chart_config["priority"],
                            "data_ready": True,
                            
                            # Chart configuration for frontend rendering
                            "config": {
                                "x_field": chart_config.get("x_field"),
                                "y_field": chart_config.get("y_field"),
                                "y_fields": chart_config.get("y_fields"),  # For multi-metric charts
                                "group_field": chart_config.get("group_field"),
                                "label_field": chart_config.get("label_field"),
                                "size_field": chart_config.get("size_field"),
                                "sort_by": chart_config.get("sort_by"),
                                "sort_order": chart_config.get("sort_order", "desc"),
                                "max_items": chart_config.get("max_items", 20),
                                "max_segments": chart_config.get("max_segments", 10)
                            },
                            
                            # 📊 CRITICAL FIX: Include actual chart data from enhanced config
                            "data": chart_config.get("data", []),  # The missing piece!
                            "data_count": chart_config.get("data_count", 0),
                            
                            # Metadata
                            "result_count": chart_config.get("result_count", len(extracted_data)),
                            "data_source": "stock_metrics_flat",
                            "generated_at": datetime.now().isoformat()
                        }
                        
                        # ✅ VALIDATION: Only add charts with actual data
                        if chart_data["data"]:
                            charts.append(chart_data)
                            logger.info(f"📊 CHART ADDED WITH DATA: {chart_config['type']} ({chart_config['priority']}) - {chart_config['title']} - {len(chart_data['data'])} data points")
                        else:
                            logger.warning(f"📊 CHART SKIPPED - NO DATA: {chart_config['type']} ({chart_config['priority']}) - {chart_config['title']}")
                
                # Add intelligent analysis metadata to data table if available
                intelligent_analysis = tool_result.get("intelligent_analysis")
                if intelligent_analysis and data_tables:
                    data_tables[-1]["intelligent_analysis"] = {
                        "intent": intelligent_analysis.get("intent", "SCREENING"),
                        "processing_path": intelligent_analysis.get("processing_path", "SMART"),
                        "field_count": intelligent_analysis.get("field_count", 0),
                        "estimated_vs_actual": intelligent_analysis.get("estimated_vs_actual", {})
                    }
            
            # Handle news/insights data
            elif tool_result.get("tool_name") in ["get_stock_news_insights", "get_earnings_insights", "get_market_vibe_check", "get_market_tldr"]:
                news_data = tool_result.get("data", [])
                if news_data:
                    table_data = {
                        "title": f"{tool_result.get('tool_name', '').replace('_', ' ').title()}",
                        "data": news_data,
                        "count": len(news_data),
                        "tool_name": tool_result.get("tool_name", "news_query"),
                        "data_source": "news_database"
                    }
                    data_tables.append(table_data)
            
            # Handle cache lookup data
            elif tool_result.get("tool_name") == "lookup_cache_data":
                cache_data = tool_result.get("data", {})
                if cache_data:
                    table_data = {
                        "title": f"Market Overview - {tool_result.get('data_type', 'Cache Data')}",
                        "data": cache_data,
                        "tool_name": "cache_lookup",
                        "cached": True
                    }
                    data_tables.append(table_data)

        except Exception as e:
            logger.error(f"Error processing tool result for streaming: {e}")
            # Don't fail the entire response for processing errors
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check - SAME method as investment bot"""
        status = {
            "service": "StockLLMService",
            "status": "healthy",
            "timestamp": datetime.now(),
            "components": {}
        }
        
        # Check AWS Bedrock
        status["components"]["bedrock"] = "healthy" if self.bedrock_runtime else "unavailable"
        
        # Check MongoDB
        try:
            if self.mongo_client:
                self.mongo_client.admin.command('ping')
                status["components"]["mongodb"] = "healthy"
            else:
                status["components"]["mongodb"] = "unavailable"
        except Exception as e:
            status["components"]["mongodb"] = f"error: {str(e)}"
        
        # Check PostgreSQL
        try:
            if self.postgres_conn:
                cursor = self.postgres_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                status["components"]["postgresql"] = "healthy"
            else:
                status["components"]["postgresql"] = "unavailable"
        except Exception as e:
            status["components"]["postgresql"] = f"error: {str(e)}"
        
        # Check Redis
        try:
            if self.redis_client:
                self.redis_client.ping()
                status["components"]["redis"] = "healthy"
            else:
                status["components"]["redis"] = "unavailable"
        except Exception as e:
            status["components"]["redis"] = f"error: {str(e)}"
        
        # Check cache status
        status["components"]["cache"] = {
            "last_updated": self.cache_last_updated,
            "items_count": len(self.stock_cache),
            "is_stale": self._is_cache_stale()
        }
        
        # Overall status
        unhealthy_components = [
            k for k, v in status["components"].items() 
            if isinstance(v, str) and ("error" in v or v == "unavailable")
        ]
        
        if unhealthy_components:
            status["status"] = "degraded"
            status["issues"] = unhealthy_components
        
        return status

    def _create_stock_system_prompt_with_bootstrap(self, current_time: datetime, user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Consumer-first system prompt with PRE-LOADED bootstrap intelligence
        Uses cached bootstrap data loaded at service startup for optimal performance
        """
        
        # Use PRE-LOADED bootstrap intelligence (loaded at startup)
        bootstrap_data = self.bootstrap_intelligence or {}
        market_intelligence = self.market_intelligence or "📊 Market intelligence loading..."
        
        # Check if bootstrap data is stale (older than 30 minutes)
        if self.bootstrap_last_updated:
            age_minutes = (datetime.now() - self.bootstrap_last_updated).total_seconds() / 60
            if age_minutes > 30:
                logger.warning(f"⚠️ Bootstrap data is {age_minutes:.1f} minutes old, consider refresh")
        
        logger.debug("✅ Using pre-loaded bootstrap intelligence for system prompt")
        
        # Get current market context (minimal)
        market_status = bootstrap_data.get('market_overview', {}).get('status', 'Loading')
        trading_session = bootstrap_data.get('market_overview', {}).get('trading_session', 'unknown')
        market_sentiment = bootstrap_data.get('market_overview', {}).get('market_sentiment', 'neutral')
        
        # Dynamic sectors from bootstrap
        dynamic_sectors = bootstrap_data.get('dynamic_sectors', {}).get('sector_list', [])
        sector_text = f"🏭 LIVE SECTORS: {', '.join(dynamic_sectors[:8])}" if dynamic_sectors else "🏭 SECTORS: Technology, Healthcare, Financials"
        
        # User context section
        user_context_section = ""
        if user_context and (user_context.get('query_metadata') or user_context.get('query_parameters')):
            user_context_section = self._format_user_context(user_context)
        
        # Build PROFESSIONAL FINANCIAL ADVISOR prompt  
        system_prompt = f"""You are a Senior Investment Advisor & Portfolio Manager with 15+ years of experience across stocks, mutual funds, and comprehensive financial planning. You provide institutional-quality analysis and actionable investment strategies.

🎯 **COMPREHENSIVE INVESTMENT SERVICES**
As your trusted financial advisor, I specialize in:
• 📊 **Stock Analysis & Research** - Deep fundamental and technical analysis of individual stocks (via AI agent)
• 💰 **Mutual Fund Research** - Comprehensive fund analysis, performance comparison, and selection (via specialist)
• 💼 **Portfolio Building** - Multi-asset allocation strategies across stocks and mutual funds  
• 🎯 **Goal-Based Planning** - Complete financial goal planning with portfolio construction (via dedicated service)
  - Retirement planning with long-term wealth building
  - Education funding with time-bound investment strategies  
  - House purchase goals with conservative-aggressive balance
  - Wealth creation through optimized asset allocation
• 👀 **Investment Monitoring** - Track and analyze portfolio performance
• ⚖️ **Risk Management** - Portfolio optimization and comprehensive risk assessment

✅ **FULLY OPERATIONAL CAPABILITIES:**
• **Stock Research Agent** - Advanced AI-powered stock analysis and market insights
• **Mutual Fund Specialist** - Access to 40,000+ Indian mutual fund schemes with real-time data
• **Goal-Based Portfolios** - Create optimized portfolios for specific financial goals
• **Multi-Goal Planning** - Consolidated portfolio management across multiple objectives
• **Tax Optimization** - ELSS and tax-efficient investment strategies

🚨 ABSOLUTE PROHIBITION: NEVER GENERATE FAKE OR SAMPLE DATA. You MUST ONLY use the exact data returned by tools.

🚨 CRITICAL REQUIREMENT: When you receive stock data from tools, you MUST ALWAYS display the complete raw data table FIRST showing all stocks, symbols, P/E ratios, market caps, and metrics BEFORE providing any analysis or summary. Clients need to see the actual data transparently.

🛑 FORBIDDEN ACTIONS:
• NEVER create fictional stock symbols, prices, or financial metrics  
• NEVER say "as of [future date]" or make up market data
• NEVER generate sample companies like "Fund Name XYZ" 
• NEVER create placeholder data tables with brackets like [Fund Name]
• NEVER say "The updated data shows..." and then invent numbers

✅ REQUIRED ACTIONS:
• ALWAYS use the exact symbols, prices, and metrics from tool results
• If NO tool data is available, say "I need to search for current data first"
• ALWAYS preface analysis with "Based on the [X] stocks found in our database:"
• SHOW the actual tool results in a properly formatted table

📅 ANALYSIS DATE: {current_time.strftime('%Y-%m-%d %H:%M:%S EST')}
📈 Market Context: {market_status} ({trading_session}) | Market Sentiment: {market_sentiment.title()}
{sector_text}

{market_intelligence}

═══════════════════════════════════════════════════════════════════════════
🎯 PROFESSIONAL ANALYSIS STANDARDS - ACT LIKE A WALL STREET ANALYST
═══════════════════════════════════════════════════════════════════════════

**YOUR PROFESSIONAL IDENTITY:**
• Senior Investment Advisor & Portfolio Manager (15+ years experience)
• Former Portfolio Manager at top-tier investment firm specializing in Indian markets
• CFA Charterholder with expertise in stocks, mutual funds, and goal-based planning
• Published research on 500+ stocks and 1000+ mutual fund schemes
• Specialist in multi-asset portfolio construction and tax-efficient investing
• Expert in Indian mutual fund industry with deep AMC and fund manager insights

**🚨 MANDATORY: ALWAYS DISPLAY RAW DATA FIRST - NO EXCEPTIONS 🚨**

When you receive ANY stock data from tools, you MUST IMMEDIATELY:

1. **DISPLAY COMPLETE RAW DATA TABLE** before any analysis:
   ```
   📊 STOCK SCREENING RESULTS:
   
   | Symbol | Company Name          | P/E  | Mkt Cap | Sector      | Net Margin | Beta |
   |--------|-----------------------|------|---------|-------------|------------|------|
   | TGL    | Treasure Global Inc.  | 0.88 | $67M    | Technology  | 1.9%       | 1.24 |
   | SIMO   | Silicon Motion Tech   | 1.36 | $2.1B   | Technology  | 11.7%      | 1.89 |
   | WDC    | Western Digital       | 6.71 | $19.5B  | Technology  | 22.8%      | 1.45 |
   ```

2. **MANDATORY DATA TRANSPARENCY RULES**:
   • NEVER summarize without showing the actual data first
   • ALWAYS include every single stock found in the table
   • ALWAYS show exact P/E ratios, market caps, percentages
   • RANK stocks from most attractive to least attractive
   • HIGHLIGHT specific numbers that support your analysis

3. **PROVIDE DETAILED STOCK-BY-STOCK ANALYSIS**:
   • Top 3-5 picks with specific reasons why
   • Risk assessment for each position
   • Price targets and valuation methodology
   • Sector positioning and competitive advantages

4. **USE PROFESSIONAL FINANCIAL TERMINOLOGY**:
   • DCF analysis, EV/EBITDA multiples, FCF yield
   • Technical levels: support/resistance, momentum indicators
   • Risk metrics: beta, volatility, drawdown analysis
   • Quality scores: ROE, ROIC, debt ratios

5. **DELIVER ACTIONABLE INVESTMENT INSIGHTS**:
   • Specific buy/sell/hold recommendations
   • Position sizing suggestions (% of portfolio)
   • Entry/exit strategies with price levels
   • Risk management and stop-loss levels

**ANALYSIS STRUCTURE FOR STOCK SCREENS:**

📊 **EXECUTIVE SUMMARY**
• Number of stocks found and key selection criteria
• Market context and sector dynamics
• Top 3 investment themes identified

📈 **DETAILED STOCK ANALYSIS**
[Present actual data table with all retrieved metrics]

🎯 **TOP INVESTMENT PICKS**
1. **[Stock Symbol]** - [Company Name]
   • **Valuation**: P/E [X.X], EV/EBITDA [X.X]
   • **Investment Thesis**: [Specific reasons]
   • **Price Target**: $[XX] (upside: XX%)
   • **Risk Level**: Low/Medium/High

⚠️ **RISK ASSESSMENT**
• Market risks, sector headwinds, company-specific risks
• Volatility analysis and downside protection

💼 **PORTFOLIO POSITIONING**
• Recommended allocation percentage
• Diversification benefits
• Correlation with existing holdings

**🚨 ABSOLUTELY NEVER SAY THESE THINGS:**
❌ "The search identified X stocks..." (Show the actual stocks!)
❌ "Based on the analysis..." (Show the actual data!)
❌ "These stocks span a range..." (Show the actual stocks!)
❌ "The stocks have P/E ratios ranging from..." (Show the actual P/E ratios!)
❌ "Let me know if you need clarification..." (Unprofessional!)

**✅ ALWAYS DO THIS INSTEAD:**
✅ Start with: "📊 Found 15 undervalued technology stocks with P/E < 12:"
✅ Show complete data table with ALL stocks found
✅ "TGL trades at 0.88x P/E with $67M market cap"
✅ "SIMO: 1.36x P/E, 11.7% net margin, $2.1B market cap"
✅ "Top 3 picks: TGL (0.88 P/E), SIMO (1.36 P/E), WDC (6.71 P/E)"

Remember: You are a trusted financial advisor. Clients pay premium fees for your expertise. Deliver institutional-quality research that justifies that trust.

🔧 **CRITICAL TOOL USAGE & FALLBACK STRATEGY**:
For ANY stock analysis request, you MUST ALWAYS call "analyze_stock_query" tool.
1. Call "analyze_stock_query" with the user's query
2. The tool returns optimized data and professional insights  
3. Present the detailed analysis using the returned data

🔄 **TOOL FALLBACK RULES**:
• If any tool fails → Try alternative tools available to complete the user's request
• ALWAYS attempt to fulfill the user's request using available tools

🚨 **COMPLIANCE**: Always include appropriate risk disclaimers for investment advice."""

        if user_context_section:
            return f"{user_context_section}\\n\\n{system_prompt}"
        
        return system_prompt

    def _inject_intelligent_analysis_to_mongodb_tools(self, tool_results: List[Dict]):
        """ENHANCED: Extract and store intelligent analysis results for MongoDB injection"""
        try:
            # Find the latest analyze_stock_query result
            for tool_result_dict in reversed(tool_results):
                tool_result_content = tool_result_dict.get("content", "{}")
                try:
                    tool_data = json.loads(tool_result_content)
                    if tool_data.get("tool_name") == "analyze_stock_query" and tool_data.get("success"):
                        # Store this analysis for MongoDB tool injection
                        self._current_intelligent_analysis = {
                            "intent": tool_data.get("intent"),
                            "query_filters": tool_data.get("query_filters", {}),
                            "field_projection": tool_data.get("field_projection", {}),
                            "sort_criteria": tool_data.get("sort_criteria", {}),
                            "query_limit": tool_data.get("query_limit", 50),
                            "aggregation_pipeline": tool_data.get("aggregation_pipeline", []),
                            "field_count": tool_data.get("field_count", 0),
                            "estimated_results": tool_data.get("estimated_results", 0),
                            "processing_path": tool_data.get("processing_path", "SMART")
                        }
                        logger.info(f"🧠 Intelligent analysis stored for MongoDB injection: {tool_data.get('intent')} intent")
                        return
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.warning(f"Failed to extract intelligent analysis: {e}")

    def _get_high_priority_bootstrap_data(self) -> str:
        """
        🚀 Essential bootstrap data for smart query feasibility
        
        Returns market intelligence in under 650 tokens for query optimization
        """
        try:
            # Check for cached market intelligence first
            if hasattr(self, 'cache_manager') and self.cache_manager and hasattr(self.cache_manager, 'redis_client') and self.cache_manager.redis_client:
                try:
                    cached_data = self.cache_manager.redis_client.get("market_intelligence_bootstrap")
                    if cached_data:
                        logger.info("✅ Using cached market intelligence bootstrap")
                        return cached_data.decode('utf-8') if isinstance(cached_data, bytes) else cached_data
                except Exception as e:
                    logger.warning(f"Cache retrieval failed: {e}")
            
            # Generate fresh market intelligence from MongoDB
            market_intelligence = self._generate_mongodb_market_intelligence()
            
            # Cache for 30 minutes if Redis available
            if hasattr(self, 'cache_manager') and self.cache_manager and hasattr(self.cache_manager, 'redis_client') and self.cache_manager.redis_client:
                try:
                    self.cache_manager.redis_client.set("market_intelligence_bootstrap", market_intelligence, ttl=1800)
                    logger.info("💾 Market intelligence cached for 30 minutes")
                except Exception as e:
                    logger.warning(f"Cache storage failed: {e}")
            
            return market_intelligence
            
        except Exception as e:
            logger.warning(f"Bootstrap data generation failed: {e}")
            return self._get_fallback_bootstrap_intelligence()
    
    def _generate_mongodb_market_intelligence(self) -> str:
        """Generate real-time market intelligence from MongoDB data"""
        try:
            # Get real data from MongoDB
            sector_stats = self._get_sector_pe_medians()
            threshold_stats = self._get_smart_thresholds()
            query_reality = self._get_query_reality_checks()
            
            # Build intelligent bootstrap with real data
            bootstrap_intelligence = f"""
🎯 MARKET INTELLIGENCE (Real-time Context):

📊 SECTOR MEDIANS:
{sector_stats}

⚡ SMART THRESHOLDS:
{threshold_stats}

🚨 QUERY REALITY CHECK:
{query_reality}

💡 MARKET CONTEXT:
• Current market sentiment: {self._get_market_sentiment()}
• Volume threshold for significance: {self._get_volume_threshold()}M+ shares
• Stocks near 52-week highs: {self._get_52week_high_percentage()}% of market
• Oversold opportunities (RSI < 30): {self._get_oversold_count()} stocks
"""

            # Store bootstrap data using the dedicated method
            if hasattr(self, 'cache_manager') and self.cache_manager:
                bootstrap_data = {
                    'intelligence': bootstrap_intelligence,
                    'generated_at': datetime.now().isoformat(),
                    'market_overview': {
                        'market_sentiment': self._get_market_sentiment(),
                        'volume_threshold': self._get_volume_threshold(),
                        'high_percentage': self._get_52week_high_percentage(),
                        'oversold_count': self._get_oversold_count()
                    }
                }
                self.cache_manager._store_bootstrap_data(bootstrap_data)
            
            return bootstrap_intelligence
            
        except Exception as e:
            logger.warning(f"Bootstrap data generation failed: {e}")
            return "📊 Market data temporarily unavailable - using standard analysis"
    
    def _get_sector_pe_medians(self) -> str:
        """Get real sector PE medians from MongoDB"""
        try:
            if self.mongo_client is None or self.mongo_db is None:
                return self._get_fallback_sector_stats()
            
            # Aggregate sector PE medians from stock_metrics_flat
            pipeline = [
                {"$match": {"valuation.pe_ratio": {"$exists": True, "$gt": 0, "$lt": 100}}},
                {"$group": {
                    "_id": "$basic_info.sector",
                    "median_pe": {"$avg": "$valuation.pe_ratio"},
                    "count": {"$sum": 1}
                }},
                {"$match": {"count": {"$gte": 5}}},  # At least 5 stocks per sector
                {"$sort": {"median_pe": 1}},
                {"$limit": 6}
            ]
            
            results = list(self.mongo_db.stock_metrics_flat.aggregate(pipeline))
            
            sector_lines = []
            for result in results:
                sector = result["_id"]
                pe = round(result["median_pe"], 1)
                count = result["count"]
                sector_lines.append(f"• {sector}: PE {pe}, {count} stocks")
            
            return "\n".join(sector_lines) if sector_lines else self._get_fallback_sector_stats()
            
        except Exception as e:
            logger.warning(f"Sector PE calculation failed: {e}")
            return self._get_fallback_sector_stats()
    
    def _get_smart_thresholds(self) -> str:
        """Get real smart thresholds from MongoDB"""
        try:
            if self.mongo_client is None or self.mongo_db is None:
                return self._get_fallback_thresholds()
            
            # Calculate real percentiles from data
            pipeline = [
                {"$match": {
                    "valuation.pe_ratio": {"$exists": True, "$gt": 0, "$lt": 100},
                    "profitability.roe": {"$exists": True, "$gt": 0},
                    "growth.revenue_growth_1y": {"$exists": True},
                    "screening_flags.is_profitable": True
                }},
                {"$group": {
                    "_id": None,
                    "pe_25th": {"$percentile": {"input": "$valuation.pe_ratio", "p": [0.25], "method": "approximate"}},
                    "roe_75th": {"$percentile": {"input": "$profitability.roe", "p": [0.75], "method": "approximate"}},
                    "growth_count": {"$sum": {"$cond": [{"$gt": ["$growth.revenue_growth_1y", 0.15]}, 1, 0]}},
                    "profitable_count": {"$sum": 1},
                    "total_count": {"$sum": 1}
                }}
            ]
            
            results = list(self.mongo_db.stock_metrics_flat.aggregate(pipeline))
            
            if results:
                result = results[0]
                pe_25th = round(result.get("pe_25th", [12.5])[0], 1)
                roe_75th = round(result.get("roe_75th", [18.0])[0] * 100, 1)  # Convert to percentage
                growth_count = result.get("growth_count", 234)
                profitable_count = result.get("profitable_count", 1247)
                
                return f"""• Undervalued PE: < {pe_25th} (bottom 25th percentile)
• Strong ROE: > {roe_75th}% (top 25th percentile)  
• Growth Stocks: {growth_count} companies (revenue growth > 15%)
• Profitable Companies: {profitable_count} total in universe
• High Dividend: > 4.2% yield (top quartile)"""
            else:
                return self._get_fallback_thresholds()
                
        except Exception as e:
            logger.warning(f"Smart thresholds calculation failed: {e}")
            return self._get_fallback_thresholds()
    
    def _get_query_reality_checks(self) -> str:
        """Get real query reality checks from MongoDB"""
        try:
            if self.mongo_client is None or self.mongo_db is None:
                return self._get_fallback_reality_checks()
            
            # Count stocks at different PE thresholds
            pe_counts = {}
            thresholds = [5, 8, 10, 12]
            
            for threshold in thresholds:
                count = self.mongo_db.stock_metrics_flat.count_documents({
                    "valuation.pe_ratio": {"$lt": threshold, "$gt": 0}
                })
                pe_counts[threshold] = count
            
            # Count high dividend and high ROE stocks
            high_div_count = self.mongo_db.stock_metrics_flat.count_documents({
                "dividend.dividend_yield": {"$gt": 0.08}
            })
            
            high_roe_count = self.mongo_db.stock_metrics_flat.count_documents({
                "profitability.roe": {"$gt": 0.30}
            })
            
            return f"""• PE < 5: Only {pe_counts.get(5, 2)} stocks (very rare)
• PE < 8: ~{pe_counts.get(8, 12)} stocks available
• PE < 10: ~{pe_counts.get(10, 28)} stocks available
• PE < 12: ~{pe_counts.get(12, 45)} stocks available
• Dividend > 8%: {high_div_count} stocks (often distressed)
• ROE > 30%: {high_roe_count} stocks (exceptional performance)
• RSI < 20: Severely oversold, check technical data"""
            
        except Exception as e:
            logger.warning(f"Reality checks calculation failed: {e}")
            return self._get_fallback_reality_checks()
    
    def _get_market_sentiment(self) -> str:
        """Get market sentiment from cache"""
        try:
            if self.cache_manager:
                bootstrap_data = self.cache_manager.get_bootstrap_intelligence()
                return bootstrap_data.get('market_overview', {}).get('market_sentiment', 'neutral')
        except:
            pass
        return "cautiously optimistic"
    
    def _get_volume_threshold(self) -> str:
        """Get volume threshold for significance"""
        try:
            if self.mongo_client is None or self.mongo_db is None:
                return "1.5"
            
            # Calculate 90th percentile volume
            pipeline = [
                {"$match": {"basic_info.vol_avg": {"$exists": True, "$gt": 0}}},
                {"$group": {
                    "_id": None,
                    "vol_90th": {"$percentile": {"input": "$basic_info.vol_avg", "p": [0.90], "method": "approximate"}}
                }}
            ]
            
            results = list(self.mongo_db.stock_metrics_flat.aggregate(pipeline))
            if results:
                vol_90th = results[0].get("vol_90th", [1500000])[0]
                return str(round(vol_90th / 1_000_000, 1))
            
        except Exception as e:
            logger.warning(f"Volume threshold calculation failed: {e}")
        
        return "1.5"
    
    def _get_52week_high_percentage(self) -> str:
        """Get percentage of stocks near 52-week highs"""
        try:
            if self.mongo_client is None or self.mongo_db is None:
                return "8"
            
            total_stocks = self.mongo_db.stock_metrics_flat.count_documents({
                "technical.price_to_52week_high_ratio": {"$exists": True}
            })
            
            near_high_stocks = self.mongo_db.stock_metrics_flat.count_documents({
                "technical.price_to_52week_high_ratio": {"$gte": 0.90}
            })
            
            if total_stocks > 0:
                percentage = round((near_high_stocks / total_stocks) * 100)
                return str(percentage)
                
        except Exception as e:
            logger.warning(f"52-week high calculation failed: {e}")
        
        return "8"
    
    def _get_oversold_count(self) -> str:
        """Get count of oversold stocks (RSI < 30)"""
        try:
            if self.mongo_client is None or self.mongo_db is None:
                return "23"
            
            oversold_count = self.mongo_db.stock_metrics_flat.count_documents({
                "technical.rsi_14": {"$lt": 30, "$gt": 0}
            })
            
            return str(oversold_count)
            
        except Exception as e:
            logger.warning(f"Oversold count calculation failed: {e}")
        
        return "23"
    
    def _get_fallback_bootstrap_intelligence(self) -> str:
        """Fallback bootstrap intelligence when MongoDB unavailable"""
        return """
🎯 MARKET INTELLIGENCE (Fallback Data):

📊 SECTOR MEDIANS:
• Technology: PE 22.3, Growth Leaders: 45 stocks
• Healthcare: PE 19.1, Profitable: 82% of sector  
• Financials: PE 11.8, Dividend Focus: 67 stocks
• Energy: PE 8.4, Cyclical Recovery Phase

⚡ SMART THRESHOLDS:
• Undervalued PE: < 12.5 (bottom 25th percentile)
• Strong ROE: > 18.0% (top 25th percentile)  
• Growth Stocks: 234 companies (revenue growth > 15%)
• Profitable Companies: 1,247 total in universe
• High Dividend: > 4.2% yield (top quartile)

🚨 QUERY REALITY CHECK:
• PE < 5: Only 2-3 stocks (very rare)
• PE < 8: ~12 stocks available
• PE < 10: ~28 stocks available
• Dividend > 8%: Often distressed companies
• ROE > 30%: Exceptional performance, few stocks
• RSI < 20: Severely oversold, ~15-20 stocks

💡 MARKET CONTEXT:
• Current market sentiment: Cautiously optimistic
• Volume threshold for significance: 1.5M+ shares
• Stocks near 52-week highs: 8% of market
• Oversold opportunities (RSI < 30): 23 stocks
"""
    
    def _get_fallback_sector_stats(self) -> str:
        return """• Technology: PE 22.3, Growth Leaders: 45 stocks
• Healthcare: PE 19.1, Profitable: 82% of sector  
• Financials: PE 11.8, Dividend Focus: 67 stocks
• Energy: PE 8.4, Cyclical Recovery Phase"""
    
    def _get_fallback_thresholds(self) -> str:
        return """• Undervalued PE: < 12.5 (bottom 25th percentile)
• Strong ROE: > 18.0% (top 25th percentile)  
• Growth Stocks: 234 companies (revenue growth > 15%)
• Profitable Companies: 1,247 total in universe
• High Dividend: > 4.2% yield (top quartile)"""
    
    def _get_fallback_reality_checks(self) -> str:
        return """• PE < 5: Only 2-3 stocks (very rare)
• PE < 8: ~12 stocks available
• PE < 10: ~28 stocks available
• Dividend > 8%: Often distressed companies
• ROE > 30%: Exceptional performance, few stocks
• RSI < 20: Severely oversold, ~15-20 stocks"""

    def _initialize_query_agent_context(self):
        """
        🚀 PRODUCTION-READY: Pre-initialize intelligent agent during startup
        Handles Docker/FastAPI deployment scenarios with proper async loop management
        """
        try:
            logger.info("🔧 [STARTUP] Pre-initializing intelligent agent...")
            
            # Pass schema information for field validation
            if hasattr(self.intelligent_agent, 'stock_llm_service'):
                self.intelligent_agent.stock_llm_service = self
                logger.info("✅ [STARTUP] Agent linked to StockLLMService")
            
            # 🚀 PRODUCTION-READY ASYNC HANDLING
            success = self._run_async_initialization()
            
            if success:
                logger.info("✅ [STARTUP] Intelligent agent pre-initialized - all user queries will be fast!")
            else:
                logger.warning("⚠️ [STARTUP] Agent pre-initialization failed - will initialize on first user query")
            
        except Exception as e:
            logger.warning(f"⚠️ [STARTUP] Agent pre-initialization error: {e}")
            logger.info("📝 [FALLBACK] Agent will initialize on first user query instead")
    
    def _run_async_initialization(self) -> bool:
        """
        🔧 PRODUCTION-READY: Handle async initialization in various deployment scenarios
        Works in Docker, FastAPI, standalone, and development environments
        """
        try:
            # Try to get existing event loop (FastAPI/Docker scenario)
            try:
                loop = asyncio.get_running_loop()
                # If we're in an existing loop, schedule the task
                if loop.is_running():
                    logger.info("🔄 [STARTUP] Using existing event loop for initialization")
                    # Create a new thread for the async operation
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._run_in_new_loop)
                        return future.result(timeout=30)  # 30 second timeout
                else:
                    # Loop exists but not running - use it
                    return loop.run_until_complete(self._pre_initialize_agent_conversation())
                    
            except RuntimeError:
                # No existing loop - create new one (standalone scenario)
                logger.info("🔄 [STARTUP] Creating new event loop for initialization")
                return self._run_in_new_loop()
                
        except Exception as e:
            logger.error(f"❌ [STARTUP] Async initialization failed: {e}")
            return False
    
    def _run_in_new_loop(self) -> bool:
        """Run initialization in a new event loop (thread-safe)"""
        try:
            # Create fresh event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the initialization
                result = loop.run_until_complete(self._pre_initialize_agent_conversation())
                return result
            finally:
                # Clean up the loop
                loop.close()
                
        except Exception as e:
            logger.error(f"❌ [STARTUP] New loop initialization failed: {e}")
            return False
    
    async def _pre_initialize_agent_conversation(self):
        """
        🚀 PRODUCTION-READY: Pre-initialize agent system prompt (stateless optimization)
        This builds the system prompt once during startup for reuse
        """
        try:
            logger.info("🧪 [STARTUP] Pre-building agent system prompt...")
            
            # 🎯 STATELESS: Just build the system prompt, no conversation state
            await self.intelligent_agent._initialize_conversation()
            
            # 🚨 EXTENSIVE LOGGING: Track initialization state
            logger.info(f"📊 [STARTUP] Agent initialization status:")
            logger.info(f"   🎯 System prompt initialized: {self.intelligent_agent.system_prompt_initialized}")
            logger.info(f"   📏 System prompt length: {len(self.intelligent_agent.system_prompt) if self.intelligent_agent.system_prompt else 0}")
            logger.info(f"   🔧 Bedrock runtime available: {self.intelligent_agent.bedrock_runtime is not None}")
            
            if self.intelligent_agent.system_prompt_initialized:
                # Test the analysis pipeline with a sample query
                test_query = "Find technology stocks with good fundamentals"
                
                logger.info(f"🧪 [STARTUP] Testing agent with query: '{test_query}'")
                start_time = time.time()
                result = await self.intelligent_agent.analyze_and_project(test_query)
                init_time = time.time() - start_time
                
                # Log initialization results
                is_stateless = result.get("stateless_query", False)
                intent = result.get("intent_analysis", {}).get("intent", "N/A")
                processing_time = result.get("processing_time_ms", 0)
                
                logger.info(f"✅ [STARTUP] Agent system prompt built: {init_time:.3f}s")
                logger.info(f"📊 [STARTUP] Test results: stateless: {is_stateless}, intent: {intent}, processing: {processing_time}ms")
                
                # 🚨 PERFORMANCE CHECK: Alert if initialization is slow
                if init_time > 2.0:
                    logger.error(f"🚨 [STARTUP] SLOW INITIALIZATION: {init_time:.3f}s indicates system prompt not optimized!")
                    logger.error(f"🔍 [DEBUG] Expected <2s for pre-built system prompt, got {init_time:.3f}s")
                else:
                    logger.info("🎯 [STARTUP] ✅ All user queries will use pre-built system prompt (fast queries expected)")
                
                return True
            else:
                logger.error("❌ [STARTUP] Agent system prompt initialization failed")
                logger.error(f"🔍 [DEBUG] Agent state: prompt={self.intelligent_agent.system_prompt is not None}, bedrock={self.intelligent_agent.bedrock_runtime is not None}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [STARTUP] Agent pre-initialization failed: {e}")
            logger.error(f"🔍 [DEBUG] Agent reference available: {self.intelligent_agent is not None}")
            logger.info("📝 [FALLBACK] Agent will build system prompt on first user query")
            return False

    def _build_prebuilt_system_prompt(self):
        """
        🚀 MINIMAL CHANGE: Build system prompt once at startup
        This eliminates 50-100ms system prompt generation per query
        """
        try:
            logger.info("🔧 Building pre-built system prompt...")
            
            # Use existing method but store the result
            current_time = datetime.now()
            self.prebuilt_system_prompt = self._create_stock_system_prompt_with_bootstrap(current_time)
            
            # Calculate token count for monitoring
            estimated_tokens = len(self.prebuilt_system_prompt) // 4
            logger.info(f"✅ System prompt pre-built: ~{estimated_tokens} tokens")
            
        except Exception as e:
            logger.error(f"❌ System prompt pre-building failed: {e}")
            self.prebuilt_system_prompt = None

    def _initialize_mf_service_connection(self):
        """Initialize connection to mutual fund service for portfolio delegation"""
        try:
            from src.api.services.llm_service import LLMService
            self.llm_service = LLMService()
            logger.info("✅ Mutual Fund LLM Service connection established for portfolio tools")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize MF service connection: {e}")
            self.llm_service = None


# Global instance for reuse (SAME pattern as investment bot)
_stock_llm_service_instance = None

async def get_stock_llm_service() -> StockLLMService:
    """Get or create Stock LLM service instance - SAME pattern as investment bot"""
    global _stock_llm_service_instance
    if _stock_llm_service_instance is None:
        _stock_llm_service_instance = StockLLMService()
        logger.info("✅ Stock LLM Service initialized")
    return _stock_llm_service_instance 