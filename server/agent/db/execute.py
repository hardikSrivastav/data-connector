import asyncpg
import asyncio
import json
import re
import random
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..config.settings import Settings

# Set up logging for the demo LLM client
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_conn():
    """
    Test database connection by connecting and executing a simple query
    """
    s = Settings()
    print(f"Connecting to database: {s.DB_HOST}/{s.DB_NAME}")
    print(f"Connection string: {s.db_dsn}")
    
    try:
        conn = await asyncpg.connect(s.db_dsn)
        result = await conn.fetchval("SELECT 1")
        print(f"Connection successful! Test query result: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        return False

async def create_connection_pool() -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool
    """
    settings = Settings()
    return await asyncpg.create_pool(
        dsn=settings.db_dsn,
        min_size=5,
        max_size=20
    )

async def execute_query(query: str) -> list:
    """
    Execute a SQL query and return the results
    
    Args:
        query: SQL query to execute
        
    Returns:
        List of dictionaries with query results
    """
    pool = await create_connection_pool()
    try:
        async with pool.acquire() as conn:
            results = await conn.fetch(query)
            # Convert to dict list for easier serialization
            return [dict(row) for row in results]
    finally:
        await pool.close()

class DemoLLMClient:
    """
    Demo LLM Client that provides intelligent responses to natural language queries
    without requiring external LLM APIs. This serves as a comprehensive demo for
    the AI query functionality in the web application.
    """
    
    def __init__(self):
        self.model_name = "demo-gpt-4"
        self.response_patterns = self._initialize_response_patterns()
        self.sample_data = self._initialize_sample_data()
        logger.info(f"🤖 Demo LLM Client initialized with model: {self.model_name}")
        
    def _initialize_response_patterns(self) -> Dict[str, Any]:
        """Initialize intelligent response patterns for different query types"""
        patterns = {
            "greetings": {
                "patterns": [r"hello", r"hi", r"hey", r"greetings"],
                "responses": [
                    "Hello! I'm your AI assistant. I can help you with data queries, analysis, and insights. What would you like to know?",
                    "Hi there! I'm ready to help you explore your data. Ask me anything about your database or analytics!",
                    "Greetings! I can generate SQL queries, analyze data, and provide insights. How can I assist you today?"
                ]
            },
            "data_queries": {
                "patterns": [r"show", r"list", r"find", r"get", r"fetch", r"select", r"query"],
                "responses": [
                    "I'll generate a SQL query to retrieve that data for you.",
                    "Let me fetch that information from the database.",
                    "I'll analyze the data and show you the results."
                ]
            },
            "analytics": {
                "patterns": [r"analyze", r"analysis", r"insights", r"trends", r"statistics", r"stats"],
                "responses": [
                    "I'll perform a comprehensive analysis of your data.",
                    "Let me generate insights and statistics for you.",
                    "I'll analyze the patterns and provide actionable insights."
                ]
            },
            "performance": {
                "patterns": [r"performance", r"optimize", r"speed", r"fast", r"slow"],
                "responses": [
                    "I'll analyze the performance metrics and suggest optimizations.",
                    "Let me check the performance data and identify bottlenecks.",
                    "I'll generate a performance analysis with recommendations."
                ]
            },
            "users": {
                "patterns": [r"user", r"customer", r"account", r"profile"],
                "sql_templates": [
                    "SELECT id, name, email, created_at, last_login FROM users ORDER BY created_at DESC LIMIT 10",
                    "SELECT COUNT(*) as total_users, COUNT(CASE WHEN last_login > NOW() - INTERVAL '30 days' THEN 1 END) as active_users FROM users",
                    "SELECT DATE(created_at) as signup_date, COUNT(*) as new_users FROM users WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY DATE(created_at) ORDER BY signup_date"
                ]
            },
            "orders": {
                "patterns": [r"order", r"purchase", r"sale", r"transaction", r"revenue"],
                "sql_templates": [
                    "SELECT id, customer_id, total_amount, status, created_at FROM orders ORDER BY created_at DESC LIMIT 10",
                    "SELECT DATE(created_at) as order_date, COUNT(*) as order_count, SUM(total_amount) as revenue FROM orders WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY DATE(created_at) ORDER BY order_date",
                    "SELECT status, COUNT(*) as count, AVG(total_amount) as avg_amount FROM orders GROUP BY status"
                ]
            },
            "products": {
                "patterns": [r"product", r"item", r"inventory", r"catalog"],
                "sql_templates": [
                    "SELECT id, name, price, category, stock_quantity FROM products ORDER BY name LIMIT 10",
                    "SELECT category, COUNT(*) as product_count, AVG(price) as avg_price FROM products GROUP BY category ORDER BY product_count DESC",
                    "SELECT name, stock_quantity FROM products WHERE stock_quantity < 10 ORDER BY stock_quantity"
                ]
            }
        }
        logger.info(f"📝 Initialized {len(patterns)} response pattern categories")
        return patterns
    
    def _initialize_sample_data(self) -> Dict[str, List[Dict]]:
        """Initialize sample data for different query types"""
        data = {
            "users": [
                {"id": 1, "name": "Alice Johnson", "email": "alice@example.com", "created_at": "2024-01-15", "last_login": "2024-01-20"},
                {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "created_at": "2024-01-10", "last_login": "2024-01-19"},
                {"id": 3, "name": "Carol Davis", "email": "carol@example.com", "created_at": "2024-01-12", "last_login": "2024-01-18"},
                {"id": 4, "name": "David Wilson", "email": "david@example.com", "created_at": "2024-01-14", "last_login": "2024-01-21"},
                {"id": 5, "name": "Eva Brown", "email": "eva@example.com", "created_at": "2024-01-16", "last_login": "2024-01-20"}
            ],
            "orders": [
                {"id": 101, "customer_id": 1, "total_amount": 299.99, "status": "completed", "created_at": "2024-01-20"},
                {"id": 102, "customer_id": 2, "total_amount": 149.50, "status": "pending", "created_at": "2024-01-19"},
                {"id": 103, "customer_id": 3, "total_amount": 89.99, "status": "completed", "created_at": "2024-01-18"},
                {"id": 104, "customer_id": 1, "total_amount": 199.00, "status": "shipped", "created_at": "2024-01-17"},
                {"id": 105, "customer_id": 4, "total_amount": 349.99, "status": "completed", "created_at": "2024-01-21"}
            ],
            "products": [
                {"id": 1, "name": "Wireless Headphones", "price": 99.99, "category": "Electronics", "stock_quantity": 25},
                {"id": 2, "name": "Coffee Maker", "price": 149.99, "category": "Appliances", "stock_quantity": 8},
                {"id": 3, "name": "Running Shoes", "price": 129.99, "category": "Sports", "stock_quantity": 15},
                {"id": 4, "name": "Smartphone Case", "price": 29.99, "category": "Electronics", "stock_quantity": 3},
                {"id": 5, "name": "Yoga Mat", "price": 39.99, "category": "Sports", "stock_quantity": 12}
            ],
            "analytics": [
                {"metric": "Total Users", "value": 1250, "change": "+12%", "period": "Last 30 days"},
                {"metric": "Active Users", "value": 890, "change": "+8%", "period": "Last 30 days"},
                {"metric": "Revenue", "value": 25400.50, "change": "+15%", "period": "Last 30 days"},
                {"metric": "Conversion Rate", "value": 3.2, "change": "+0.5%", "period": "Last 30 days"}
            ]
        }
        logger.info(f"📊 Initialized sample data with {sum(len(v) for v in data.values())} total records")
        return data
    
    def _detect_query_intent(self, query: str) -> str:
        """Detect the intent of the user's query"""
        query_lower = query.lower()
        logger.info(f"🔍 Analyzing query intent for: '{query}'")
        
        # Check for specific patterns
        for intent, config in self.response_patterns.items():
            if "patterns" in config:
                for pattern in config["patterns"]:
                    if re.search(pattern, query_lower):
                        logger.info(f"✅ Detected intent: {intent} (matched pattern: {pattern})")
                        return intent
        
        # Default to data_queries for unknown patterns
        logger.info(f"🔄 Using default intent: data_queries")
        return "data_queries"
    
    def _detect_data_type(self, query: str) -> str:
        """Detect what type of data the user is asking about"""
        query_lower = query.lower()
        logger.info(f"📊 Detecting data type for: '{query}'")
        
        if any(word in query_lower for word in ["user", "customer", "account", "profile"]):
            logger.info(f"👥 Detected data type: users")
            return "users"
        elif any(word in query_lower for word in ["order", "purchase", "sale", "transaction", "revenue"]):
            logger.info(f"🛒 Detected data type: orders")
            return "orders"
        elif any(word in query_lower for word in ["product", "item", "inventory", "catalog"]):
            logger.info(f"📦 Detected data type: products")
            return "products"
        elif any(word in query_lower for word in ["analytics", "metrics", "stats", "performance"]):
            logger.info(f"📈 Detected data type: analytics")
            return "analytics"
        else:
            logger.info(f"�� Using default data type: users")
            return "users"  # Default fallback
    
    def _generate_sql_query(self, query: str, data_type: str) -> str:
        """Generate appropriate SQL query based on the user's request"""
        logger.info(f"🛠️ Generating SQL query for data_type='{data_type}', query='{query}'")
        
        patterns = self.response_patterns.get(data_type, {})
        sql_templates = patterns.get("sql_templates", [])
        
        if sql_templates:
            # Choose template based on query keywords
            query_lower = query.lower()
            
            if any(word in query_lower for word in ["count", "total", "number", "how many"]):
                # Return count/aggregate query if available
                count_queries = [q for q in sql_templates if "COUNT" in q.upper()]
                if count_queries:
                    selected_sql = random.choice(count_queries)
                    logger.info(f"📊 Selected COUNT/aggregate SQL template: {selected_sql[:50]}...")
                    return selected_sql
            
            if any(word in query_lower for word in ["recent", "latest", "new", "last"]):
                # Return recent data query if available
                recent_queries = [q for q in sql_templates if "ORDER BY" in q and "DESC" in q]
                if recent_queries:
                    selected_sql = random.choice(recent_queries)
                    logger.info(f"🕒 Selected recent data SQL template: {selected_sql[:50]}...")
                    return selected_sql
            
            if any(word in query_lower for word in ["group", "category", "by"]):
                # Return grouped data query if available
                group_queries = [q for q in sql_templates if "GROUP BY" in q.upper()]
                if group_queries:
                    selected_sql = random.choice(group_queries)
                    logger.info(f"📊 Selected GROUP BY SQL template: {selected_sql[:50]}...")
                    return selected_sql
            
            # Default to first template
            selected_sql = sql_templates[0]
            logger.info(f"🔄 Selected default SQL template: {selected_sql[:50]}...")
            return selected_sql
        
        # Fallback generic query
        fallback_sql = f"SELECT * FROM {data_type} LIMIT 10"
        logger.info(f"⚠️ Using fallback SQL: {fallback_sql}")
        return fallback_sql
    
    def _get_sample_data(self, data_type: str, limit: int = 5) -> List[Dict]:
        """Get sample data for the specified data type"""
        logger.info(f"📋 Retrieving sample data for data_type='{data_type}', limit={limit}")
        
        data = self.sample_data.get(data_type, [])
        sample = data[:limit]
        
        logger.info(f"✅ Retrieved {len(sample)} sample records")
        if sample:
            logger.info(f"📝 Sample data preview: {list(sample[0].keys()) if sample else 'No data'}")
        
        return sample
    
    def _generate_analysis(self, query: str, data: List[Dict], data_type: str) -> str:
        """Generate intelligent analysis based on the query and data"""
        logger.info(f"🧠 Generating analysis for query='{query}', data_type='{data_type}', records={len(data)}")
        
        analysis_parts = []
        
        # Basic data summary
        if data:
            summary = f"📊 **Data Summary**: Found {len(data)} records"
            analysis_parts.append(summary)
            logger.info(f"✅ Added basic summary: {summary}")
            
            # Type-specific insights
            if data_type == "users":
                if "email" in data[0]:
                    domains = [row["email"].split("@")[1] for row in data if "@" in str(row.get("email", ""))]
                    unique_domains = len(set(domains))
                    insight = f"👥 **User Insights**: Users from {unique_domains} different email domains"
                    analysis_parts.append(insight)
                    logger.info(f"👥 Added user insight: {insight}")
                
                if "created_at" in data[0]:
                    temporal_insight = "📅 **Temporal Pattern**: Recent user registrations show steady growth"
                    analysis_parts.append(temporal_insight)
                    logger.info(f"📅 Added temporal insight: {temporal_insight}")
            
            elif data_type == "orders":
                if "total_amount" in data[0]:
                    total_revenue = sum(float(row.get("total_amount", 0)) for row in data)
                    avg_order = total_revenue / len(data) if data else 0
                    revenue_insight = f"💰 **Revenue Insights**: Average order value: ${avg_order:.2f}"
                    analysis_parts.append(revenue_insight)
                    logger.info(f"💰 Added revenue insight: {revenue_insight}")
                
                if "status" in data[0]:
                    statuses = [row.get("status", "") for row in data]
                    completed = statuses.count("completed")
                    status_insight = f"✅ **Order Status**: {completed}/{len(data)} orders completed"
                    analysis_parts.append(status_insight)
                    logger.info(f"✅ Added status insight: {status_insight}")
            
            elif data_type == "products":
                if "category" in data[0]:
                    categories = set(row.get("category", "") for row in data)
                    category_insight = f"🏷️ **Product Diversity**: {len(categories)} different categories"
                    analysis_parts.append(category_insight)
                    logger.info(f"🏷️ Added category insight: {category_insight}")
                
                if "stock_quantity" in data[0]:
                    low_stock = sum(1 for row in data if int(row.get("stock_quantity", 0)) < 10)
                    if low_stock > 0:
                        stock_insight = f"⚠️ **Inventory Alert**: {low_stock} products with low stock"
                        analysis_parts.append(stock_insight)
                        logger.info(f"⚠️ Added inventory insight: {stock_insight}")
            
            elif data_type == "analytics":
                perf_insight = "📈 **Performance Metrics**: Key indicators showing positive trends"
                analysis_parts.append(perf_insight)
                logger.info(f"📈 Added performance insight: {perf_insight}")
                
                positive_changes = sum(1 for row in data if "+" in str(row.get("change", "")))
                if positive_changes > 0:
                    growth_insight = f"📊 **Growth Indicators**: {positive_changes}/{len(data)} metrics showing improvement"
                    analysis_parts.append(growth_insight)
                    logger.info(f"📊 Added growth insight: {growth_insight}")
        
        # Query-specific insights
        query_lower = query.lower()
        if "trend" in query_lower or "growth" in query_lower:
            trend_insight = "📈 **Trend Analysis**: Data indicates steady upward trajectory with seasonal variations"
            analysis_parts.append(trend_insight)
            logger.info(f"📈 Added trend insight: {trend_insight}")
        
        if "performance" in query_lower:
            perf_specific = "⚡ **Performance Insights**: System metrics within optimal ranges, minor optimizations possible"
            analysis_parts.append(perf_specific)
            logger.info(f"⚡ Added performance insight: {perf_specific}")
        
        if "comparison" in query_lower or "compare" in query_lower:
            compare_insight = "🔍 **Comparative Analysis**: Current period shows 15% improvement over previous baseline"
            analysis_parts.append(compare_insight)
            logger.info(f"🔍 Added comparison insight: {compare_insight}")
        
        # Recommendations
        if data_type in ["users", "orders"]:
            recommendation = "💡 **Recommendations**: Consider implementing retention campaigns for inactive users"
            analysis_parts.append(recommendation)
            logger.info(f"💡 Added recommendation: {recommendation}")
        elif data_type == "products":
            recommendation = "💡 **Recommendations**: Monitor low-stock items and optimize inventory levels"
            analysis_parts.append(recommendation)
            logger.info(f"💡 Added recommendation: {recommendation}")
        
        final_analysis = "\n\n".join(analysis_parts) if analysis_parts else "Analysis completed successfully."
        logger.info(f"🎯 Generated complete analysis with {len(analysis_parts)} sections")
        
        return final_analysis
    
    async def process_query(self, question: str, analyze: bool = False) -> Dict[str, Any]:
        """
        Process a natural language query and return appropriate response
        
        Args:
            question: User's natural language question
            analyze: Whether to include analysis in the response
            
        Returns:
            Dictionary with rows, sql, and optional analysis
        """
        logger.info(f"🚀 PROCESSING QUERY: '{question}' (analyze={analyze})")
        
        try:
            # Detect query intent and data type
            intent = self._detect_query_intent(question)
            data_type = self._detect_data_type(question)
            
            logger.info(f"📊 Query classification: intent='{intent}', data_type='{data_type}'")
            
            # Handle greetings and general queries
            if intent == "greetings":
                greeting_response = random.choice(self.response_patterns["greetings"]["responses"])
                response = {
                    "rows": [{"message": greeting_response}],
                    "sql": "-- No SQL query needed for greetings",
                    "analysis": "This is a greeting message. Ask me about your data and I'll help you explore it!" if analyze else None
                }
                logger.info(f"👋 Greeting response generated: {greeting_response[:50]}...")
                logger.info(f"📤 FINAL RESPONSE: {response}")
                return response
            
            # Generate SQL query
            sql_query = self._generate_sql_query(question, data_type)
            logger.info(f"🛠️ Generated SQL: {sql_query}")
            
            # Get sample data (simulate database execution)
            sample_data = self._get_sample_data(data_type)
            logger.info(f"📋 Retrieved {len(sample_data)} sample records")
            
            # Prepare response
            response = {
                "rows": sample_data,
                "sql": sql_query
            }
            
            # Add analysis if requested
            if analyze:
                analysis = self._generate_analysis(question, sample_data, data_type)
                response["analysis"] = analysis
                logger.info(f"🧠 Analysis generated: {len(analysis)} characters")
            
            logger.info(f"📤 FINAL RESPONSE: rows={len(response['rows'])}, sql={len(response['sql'])} chars, analysis={len(response.get('analysis', '')) if response.get('analysis') else 0} chars")
            return response
            
        except Exception as e:
            logger.error(f"❌ Error processing query '{question}': {str(e)}")
            # Return error response
            error_response = {
                "rows": [{"error": f"Query processing failed: {str(e)}"}],
                "sql": "-- Error occurred during query generation",
                "analysis": f"❌ **Error**: {str(e)}" if analyze else None
            }
            logger.info(f"📤 ERROR RESPONSE: {error_response}")
            return error_response

# Create global demo client instance
demo_llm_client = DemoLLMClient()

async def process_ai_query(question: str, analyze: bool = False) -> Dict[str, Any]:
    """
    Process an AI query using the demo LLM client
    
    Args:
        question: Natural language question
        analyze: Whether to include analysis
        
    Returns:
        Formatted response with rows, sql, and optional analysis
    """
    logger.info(f"🎯 ENTRY POINT: process_ai_query called with question='{question}', analyze={analyze}")
    result = await demo_llm_client.process_query(question, analyze)
    logger.info(f"🏁 ENTRY POINT: process_ai_query returning: {type(result)} with keys: {list(result.keys())}")
    return result

if __name__ == "__main__":
    # Test the demo client
    async def test_demo():
        print("🤖 Testing Demo LLM Client")
        print("=" * 50)
        
        test_queries = [
            "Hello! What can you help me with?",
            "Show me the latest users",
            "How many orders were placed recently?",
            "Analyze product performance",
            "Find users with low activity",
            "What's the revenue trend?",
            "Show me products with low stock"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Query: {query}")
            result = await process_ai_query(query, analyze=True)
            print(f"📊 SQL: {result['sql']}")
            print(f"📋 Rows: {len(result['rows'])} results")
            if result.get('analysis'):
                print(f"🧠 Analysis: {result['analysis'][:100]}...")
            print("-" * 30)
    
    # Also test database connection
    asyncio.run(test_demo())
    asyncio.run(test_conn())
