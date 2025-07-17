"""
Shopify Adapter for querying Shopify e-commerce data
Integrates with Ceneca's AI analytics and FAISS indexing system
"""
import json
import logging
import os
import requests
import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
import hmac
import hashlib
import base64

from .base import DBAdapter

# Configure logging
logger = logging.getLogger(__name__)

class ShopifyAdapter(DBAdapter):
    """
    Adapter for querying Shopify e-commerce data
    
    This adapter handles OAuth authentication, real-time webhook processing,
    and provides comprehensive e-commerce data access for Ceneca's AI models.
    """
    
    def __init__(self, connection_uri: str, **kwargs):
        """
        Initialize Shopify adapter
        
        Args:
            connection_uri: Shopify app URL or shop domain
            **kwargs: Additional arguments
                shop_domain: Shopify shop domain (e.g., 'mystore.myshopify.com')
                api_version: Shopify API version (default: '2025-04')
                cache_dir: Optional directory to cache schema data
        """
        # Use default if connection_uri is empty
        if not connection_uri:
            connection_uri = "https://ceneca.ai"
            
        self.app_url = connection_uri.rstrip("/")
        self.shop_domain = kwargs.get("shop_domain")
        self.api_version = kwargs.get("api_version", "2025-04")
        
        # Credentials management
        self.credentials_file = os.path.join(
            str(Path.home()), 
            ".data-connector", 
            "shopify_credentials.json"
        )
        self.cache_dir = kwargs.get("cache_dir")
        
        # Authentication state
        self.access_token = None
        self.token_expires_at = None
        self.shop_info = None
        self.granted_scopes = []
        self.requested_scopes = []
        
        # Load existing credentials
        self._load_credentials()
        
    def _parse_shopify_app_toml(self) -> List[str]:
        """
        Parse shopify.app.toml file to extract all defined scopes
        
        Returns:
            List of scopes defined in the TOML file
        """
        try:
            # Look for the TOML file in various possible locations
            possible_paths = [
                # From server/agent directory
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "ceneca-shopify", "shopify.app.toml"),
                # From project root
                os.path.join(os.getcwd(), "ceneca-shopify", "shopify.app.toml"),
                os.path.join(os.getcwd(), "..", "ceneca-shopify", "shopify.app.toml"),
                # Absolute path attempts
                "/Users/hardiksrivastav/Projects/data-connector/ceneca-shopify/shopify.app.toml",
            ]
            
            toml_content = ""
            toml_path = ""
            
            for file_path in possible_paths:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        toml_content = f.read()
                    toml_path = file_path
                    break
            
            if not toml_content:
                logger.warning("shopify.app.toml not found, using fallback scopes")
                # Fallback to the scopes we know from the TOML file
                return [
                    'read_orders', 'read_products', 'read_customers', 'read_inventory',
                    'read_locations', 'read_price_rules', 'read_discounts', 'read_analytics',
                    'read_reports', 'read_checkouts', 'read_draft_orders', 'read_fulfillments',
                    'read_gift_cards', 'read_marketing_events', 'read_order_edits',
                    'read_payment_terms', 'read_shipping', 'read_themes', 'read_translations',
                    'read_all_orders', 'read_assigned_fulfillment_orders',
                    'read_merchant_managed_fulfillment_orders', 'read_third_party_fulfillment_orders',
                    'write_assigned_fulfillment_orders', 'write_merchant_managed_fulfillment_orders',
                    'write_third_party_fulfillment_orders'
                ]
            
            logger.info(f"Found shopify.app.toml at: {toml_path}")
            
            # Simple TOML parsing for scopes section
            # Look for the scopes = """ ... """ block
            scopes_match = re.search(r'scopes\s*=\s*"""\s*([\s\S]*?)\s*"""', toml_content)
            
            if not scopes_match:
                logger.warning("No scopes section found in TOML file")
                return []
            
            scopes_text = scopes_match.group(1)
            
            # Parse the scopes - they're comma-separated and may span multiple lines
            scopes = []
            for line in scopes_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Remove comments and split by comma
                    line = line.split('#')[0].strip()
                    if line.endswith(','):
                        line = line[:-1]
                    if line:
                        scopes.append(line.strip())
            
            logger.info(f"Parsed {len(scopes)} scopes from TOML file: {scopes}")
            return scopes
            
        except Exception as e:
            logger.error(f"Error parsing shopify.app.toml: {str(e)}")
            return []
    
    def _load_credentials(self) -> bool:
        """Load stored Shopify credentials if available"""
        try:
            if not os.path.exists(self.credentials_file):
                logger.warning(f"Shopify credentials file not found: {self.credentials_file}")
                return False
                
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
                
            # Check if credentials contain required fields
            if 'shops' not in credentials or not credentials.get('shops'):
                logger.warning("No shops found in Shopify credentials file")
                return False
                
            # Find the shop domain or use default
            shop_data = None
            if self.shop_domain:
                shop_data = credentials['shops'].get(self.shop_domain)
            else:
                # Use the first shop if no specific domain provided
                shop_data = next(iter(credentials['shops'].values()))
                self.shop_domain = next(iter(credentials['shops'].keys()))
                
            if not shop_data:
                logger.warning(f"Shop {self.shop_domain} not found in credentials")
                return False
                
            self.access_token = shop_data.get('access_token')
            self.shop_info = shop_data.get('shop_info', {})
            
            # Handle both old and new credential formats
            if 'granted_scopes' in shop_data and 'requested_scopes' in shop_data:
                # New format with separate granted and requested scopes
                self.granted_scopes = shop_data.get('granted_scopes', [])
                self.requested_scopes = shop_data.get('requested_scopes', [])
                logger.info(f"Loaded credentials with {len(self.granted_scopes)} granted scopes and {len(self.requested_scopes)} requested scopes")
            else:
                # Old format - treat existing scopes as granted scopes
                self.granted_scopes = shop_data.get('scopes', [])
                # Try to get requested scopes from TOML file
                self.requested_scopes = self._parse_shopify_app_toml()
                logger.info(f"Loaded legacy credentials, upgrading format")
                
                # Update the credentials file with the new format
                self._upgrade_credentials_format(credentials)
            
            logger.info(f"Loaded credentials for shop: {self.shop_domain}")
            return True
                
        except Exception as e:
            logger.error(f"Error loading Shopify credentials: {str(e)}")
            return False
    
    def _upgrade_credentials_format(self, credentials: Dict):
        """Upgrade old credential format to new format with granted/requested scopes"""
        try:
            updated = False
            for shop_domain, shop_data in credentials['shops'].items():
                if 'granted_scopes' not in shop_data or 'requested_scopes' not in shop_data:
                    # Upgrade this shop's credentials
                    old_scopes = shop_data.get('scopes', [])
                    requested_scopes = self._parse_shopify_app_toml()
                    
                    shop_data['granted_scopes'] = old_scopes
                    shop_data['requested_scopes'] = requested_scopes
                    shop_data['scopes'] = requested_scopes  # Use requested scopes as main scopes
                    
                    updated = True
                    logger.info(f"Upgraded credentials format for shop: {shop_domain}")
            
            if updated:
                # Save the updated credentials
                with open(self.credentials_file, 'w') as f:
                    json.dump(credentials, f, indent=2)
                logger.info("Saved upgraded credentials file")
                
        except Exception as e:
            logger.error(f"Error upgrading credentials format: {str(e)}")
    
    def get_available_scopes(self) -> Dict[str, List[str]]:
        """
        Get information about available scopes
        
        Returns:
            Dictionary with 'granted', 'requested', and 'missing' scope lists
        """
        requested_scopes = self.requested_scopes or self._parse_shopify_app_toml()
        granted_scopes = self.granted_scopes or []
        missing_scopes = [scope for scope in requested_scopes if scope not in granted_scopes]
        
        return {
            'granted': granted_scopes,
            'requested': requested_scopes,
            'missing': missing_scopes
        }
    
    def _save_credentials(self, shop_domain: str, access_token: str, shop_info: Dict = None, granted_scopes: List[str] = None):
        """Save Shopify credentials securely"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
            
            # Load existing credentials or create new structure
            credentials = {}
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
            
            if 'shops' not in credentials:
                credentials['shops'] = {}
            
            # Get requested scopes from TOML file
            requested_scopes = self._parse_shopify_app_toml()
            granted_scopes = granted_scopes or []
                
            # Save shop credentials with new format
            credentials['shops'][shop_domain] = {
                'access_token': access_token,
                'shop_info': shop_info or {},
                'scopes': requested_scopes,  # Use requested scopes as main scopes
                'granted_scopes': granted_scopes,
                'requested_scopes': requested_scopes,
                'last_updated': datetime.now().isoformat(),
                'api_version': self.api_version
            }
            
            # Write credentials file with secure permissions
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            # Set secure file permissions (readable only by owner)
            os.chmod(self.credentials_file, 0o600)
            
            logger.info(f"Saved credentials for shop: {shop_domain}")
            
        except Exception as e:
            logger.error(f"Error saving Shopify credentials: {str(e)}")
            raise
    
    async def authenticate_shop(self, shop_domain: str, access_token: str) -> bool:
        """
        Authenticate with a Shopify shop and save credentials
        
        Args:
            shop_domain: The shop domain (e.g., 'mystore.myshopify.com')
            access_token: OAuth access token from Shopify app installation
            
        Returns:
            True if authentication successful
        """
        try:
            # Test the token by fetching shop info
            headers = {
                'X-Shopify-Access-Token': access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"https://{shop_domain}/admin/api/{self.api_version}/shop.json",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                shop_info = response.json().get('shop', {})
                
                # Save credentials
                self._save_credentials(shop_domain, access_token, shop_info)
                
                # Update instance state
                self.shop_domain = shop_domain
                self.access_token = access_token
                self.shop_info = shop_info
                
                logger.info(f"Successfully authenticated with shop: {shop_info.get('name', shop_domain)}")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error authenticating shop: {str(e)}")
            return False
    
    async def _make_api_request(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Dict:
        """
        Make authenticated API request to Shopify
        
        Args:
            endpoint: API endpoint (e.g., 'orders', 'products')
            method: HTTP method
            params: Query parameters
            data: Request body data
            
        Returns:
            API response data
        """
        if not self.access_token or not self.shop_domain:
            raise Exception("Not authenticated. Please authenticate first.")
            
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        url = f"https://{self.shop_domain}/admin/api/{self.api_version}/{endpoint.lstrip('/')}.json"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                raise Exception(f"Shopify API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error making API request to {endpoint}: {str(e)}")
            raise
    
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verify Shopify webhook signature for security
        
        Args:
            payload: Raw webhook payload
            signature: X-Shopify-Hmac-Sha256 header value
            
        Returns:
            True if signature is valid
        """
        try:
            # In production, this should come from environment variables
            webhook_secret = os.getenv('SHOPIFY_WEBHOOK_SECRET', '')
            
            if not webhook_secret:
                logger.warning("No webhook secret configured - skipping verification")
                return True  # Allow in development
                
            # Calculate expected signature
            expected_signature = base64.b64encode(
                hmac.new(
                    webhook_secret.encode('utf-8'),
                    payload,
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    async def process_webhook(self, topic: str, data: Dict) -> Dict:
        """
        Process incoming webhook data and update FAISS index
        
        Args:
            topic: Webhook topic (e.g., 'orders/paid', 'customers/update')
            data: Webhook payload data
            
        Returns:
            Processing result
        """
        try:
            logger.info(f"Processing webhook: {topic}")
            
            # Normalize the data based on webhook topic
            normalized_data = self._normalize_webhook_data(topic, data)
            
            # TODO: Update FAISS index with new data
            # This will be implemented when integrating with the meta indexing system
            
            return {
                "status": "processed",
                "topic": topic,
                "timestamp": datetime.now().isoformat(),
                "data_type": normalized_data.get("type"),
                "shop_domain": self.shop_domain
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook {topic}: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _normalize_webhook_data(self, topic: str, data: Dict) -> Dict:
        """Normalize webhook data for consistent processing"""
        try:
            # Extract the main data object
            if topic.startswith('orders/'):
                return {
                    "type": "order",
                    "id": data.get('id'),
                    "data": data,
                    "shop_domain": self.shop_domain,
                    "updated_at": data.get('updated_at')
                }
            elif topic.startswith('customers/'):
                return {
                    "type": "customer", 
                    "id": data.get('id'),
                    "data": data,
                    "shop_domain": self.shop_domain,
                    "updated_at": data.get('updated_at')
                }
            elif topic.startswith('products/'):
                return {
                    "type": "product",
                    "id": data.get('id'), 
                    "data": data,
                    "shop_domain": self.shop_domain,
                    "updated_at": data.get('updated_at')
                }
            elif topic.startswith('inventory_levels/'):
                return {
                    "type": "inventory",
                    "id": f"{data.get('inventory_item_id')}_{data.get('location_id')}",
                    "data": data,
                    "shop_domain": self.shop_domain,
                    "updated_at": datetime.now().isoformat()
                }
            elif topic.startswith('checkouts/'):
                return {
                    "type": "checkout",
                    "id": data.get('id'),
                    "data": data, 
                    "shop_domain": self.shop_domain,
                    "updated_at": data.get('updated_at')
                }
            else:
                return {
                    "type": "unknown",
                    "id": data.get('id'),
                    "data": data,
                    "shop_domain": self.shop_domain,
                    "updated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error normalizing webhook data: {str(e)}")
            return {"type": "error", "error": str(e)}

    # DBAdapter interface implementation
    
    async def test_connection(self) -> bool:
        """Test the Shopify API connection"""
        try:
            if not self.access_token or not self.shop_domain:
                return False
                
            # Test with a simple shop info request
            await self._make_api_request('shop')
            return True
            
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """
        Convert natural language prompt to Shopify API queries
        
        Args:
            nl_prompt: Natural language question
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with query information and API endpoints
        """
        try:
            # Simple query mapping - this would be enhanced with LLM processing
            query_mapping = {
                # Orders queries
                "orders": {"endpoint": "orders", "params": {"status": "any"}},
                "recent orders": {"endpoint": "orders", "params": {"status": "any", "limit": 50}},
                "paid orders": {"endpoint": "orders", "params": {"financial_status": "paid"}},
                "pending orders": {"endpoint": "orders", "params": {"financial_status": "pending"}},
                
                # Products queries  
                "products": {"endpoint": "products", "params": {}},
                "inventory": {"endpoint": "products", "params": {}},
                "low stock": {"endpoint": "inventory_levels", "params": {}},
                
                # Customers queries
                "customers": {"endpoint": "customers", "params": {}},
                "new customers": {"endpoint": "customers", "params": {"created_at_min": (datetime.now() - timedelta(days=30)).isoformat()}},
                
                # Analytics queries
                "sales": {"endpoint": "orders", "params": {"status": "any", "financial_status": "paid"}},
                "revenue": {"endpoint": "orders", "params": {"status": "any", "financial_status": "paid"}},
            }
            
            # Find the best matching query
            prompt_lower = nl_prompt.lower()
            query_info = None
            
            for keyword, query_data in query_mapping.items():
                if keyword in prompt_lower:
                    query_info = query_data
                    break
            
            if not query_info:
                # Default to general search across products and orders
                query_info = {"endpoint": "orders", "params": {"limit": 100}}
            
            # Add additional parameters from kwargs
            if "limit" in kwargs:
                query_info["params"]["limit"] = kwargs["limit"]
            if "since_date" in kwargs:
                query_info["params"]["created_at_min"] = kwargs["since_date"]
                
            return {
                "type": "shopify_api",
                "query": query_info,
                "original_prompt": nl_prompt,
                "shop_domain": self.shop_domain
            }
            
        except Exception as e:
            logger.error(f"Error converting prompt to query: {str(e)}")
            return {"type": "error", "error": str(e)}
    
    async def execute(self, query: Any) -> List[Dict]:
        """
        Execute Shopify API query and return results
        
        Args:
            query: Query object from llm_to_query, orchestrator parameters, or SQL-style string
            
        Returns:
            List of results from Shopify API
        """
        try:
            # Convert query to proper Shopify format if needed
            shopify_query = await self._convert_query_format(query)
            
            # Extract endpoint and params from converted query
            endpoint = shopify_query.get("endpoint", "orders")
            params = shopify_query.get("params", {})
            
            # Handle limit parameter
            if "limit" in shopify_query:
                params["limit"] = shopify_query["limit"]
            
            # Make API request
            response = await self._make_api_request(endpoint, params=params)
            
            # Extract the data array from response
            if endpoint == "orders":
                return response.get("orders", [])
            elif endpoint == "products":
                return response.get("products", [])
            elif endpoint == "customers":
                return response.get("customers", [])
            elif endpoint == "inventory_levels":
                return response.get("inventory_levels", [])
            else:
                # Return the whole response if structure is unknown
                return [response] if isinstance(response, dict) else response
                
        except Exception as e:
            logger.error(f"Error executing Shopify query: {str(e)}")
            return [{"error": str(e)}]
    
    async def _convert_query_format(self, query: Any) -> Dict[str, Any]:
        """
        Convert various query formats to Shopify API format.
        
        Args:
            query: Query in various formats (string, dict, etc.)
            
        Returns:
            Dict with Shopify API query parameters
        """
        import re
        from ...config.settings import Settings
        
        settings = Settings()
        
        # Handle SQL-style string queries
        if isinstance(query, str):
            query_lower = query.lower().strip()
            
            logger.info(f"🛍️ Shopify Query Conversion (API v{settings.SHOPIFY_API_VERSION}): \"{query}\" → ", end="")
            
            # Parse common SQL patterns for Shopify
            if "select" in query_lower and "from" in query_lower:
                # Extract table/endpoint from SQL - use just the resource name
                if "products" in query_lower:
                    endpoint = "products"
                elif "orders" in query_lower:
                    endpoint = "orders"
                elif "customers" in query_lower:
                    endpoint = "customers"
                elif "inventory" in query_lower:
                    endpoint = "inventory_levels"
                elif "locations" in query_lower:
                    endpoint = "locations"
                elif "collections" in query_lower:
                    endpoint = "collections"
                elif "variants" in query_lower:
                    endpoint = "variants"
                elif "transactions" in query_lower:
                    endpoint = "transactions"
                else:
                    # Default to products
                    endpoint = "products"
                
                # Extract LIMIT if present
                limit_match = re.search(r'limit\s+(\d+)', query_lower)
                limit = int(limit_match.group(1)) if limit_match else 50
                
                # Create Shopify API query with proper structure
                shopify_query = {
                    "endpoint": endpoint,  # Just the resource name (e.g., 'products')
                    "method": "GET",
                    "params": {"limit": min(limit, 250)}  # Shopify API limit
                }
                
                # Add additional filters based on SQL WHERE clauses
                if "where" in query_lower:
                    # Parse basic WHERE conditions
                    if "status" in query_lower:
                        status_match = re.search(r"status\s*=\s*['\"]([^'\"]+)['\"]", query_lower)
                        if status_match:
                            shopify_query["params"]["status"] = status_match.group(1)
                    
                    if "created_at" in query_lower or "updated_at" in query_lower:
                        # Handle date filters
                        date_match = re.search(r"(created_at|updated_at)\s*>\s*['\"]([^'\"]+)['\"]", query_lower)
                        if date_match:
                            field, date_val = date_match.groups()
                            shopify_query["params"][f"{field}_min"] = date_val
                
            elif "count" in query_lower:
                # Handle COUNT queries - use just the resource name with /count
                if "products" in query_lower:
                    endpoint = "products/count"
                elif "orders" in query_lower:
                    endpoint = "orders/count"
                elif "customers" in query_lower:
                    endpoint = "customers/count"
                else:
                    endpoint = "products/count"
                
                shopify_query = {
                    "endpoint": endpoint,
                    "method": "GET",
                    "params": {}
                }
            else:
                # Default query for general requests
                shopify_query = {
                    "endpoint": "products",
                    "method": "GET",
                    "params": {"limit": 50}
                }
            
            logger.info(f"{shopify_query}")
            return shopify_query
        
        # Handle dict queries
        elif isinstance(query, dict):
            # Handle legacy format from llm_to_query
            if query.get("type") == "shopify_api":
                query_info = query["query"]
                endpoint = query_info["endpoint"]
                params = query_info.get("params", {})
                return {"endpoint": endpoint, "params": params}
            
            # Handle orchestrator format
            elif "endpoint" in query:
                shopify_query = query.copy()
                
                # Convert full API paths to just resource names if needed
                endpoint = query["endpoint"]
                if endpoint.startswith("/admin/api/"):
                    # Extract just the resource name from full API path
                    # e.g., "/admin/api/2025-04/products.json" -> "products"
                    match = re.search(r'/admin/api/[^/]+/([^.]+)(?:\.json)?$', endpoint)
                    if match:
                        shopify_query["endpoint"] = match.group(1)
                
                return shopify_query
            else:
                # Try to infer endpoint from query structure
                return {
                    "endpoint": "products",
                    "method": "GET",
                    "params": query.get("params", {"limit": 50})
                }
        
        # Fallback for unknown query types
        else:
            return {
                "endpoint": "products",
                "method": "GET", 
                "params": {"limit": 50}
            }
    
    async def execute_query(self, query: Dict[str, Any]) -> List[Dict]:
        """
        Execute a query with orchestrator-compatible interface
        
        Args:
            query: Query parameters from orchestrator
            
        Returns:
            List of results from Shopify API
        """
        return await self.execute(query)
    
    async def validate_query(self, query: Dict[str, Any]) -> bool:
        """
        Validate a query without executing it
        
        Args:
            query: Query parameters to validate
            
        Returns:
            True if query is valid, False otherwise
        """
        try:
            # Basic validation
            if not isinstance(query, dict):
                return False
            
            # Check for required fields
            endpoint = query.get("endpoint")
            if not endpoint:
                return False
            
            # Validate endpoint
            valid_endpoints = [
                "orders", "products", "customers", "inventory_levels", 
                "checkouts", "variants", "collections", "locations",
                "fulfillments", "transactions", "discounts", "price_rules"
            ]
            
            if endpoint not in valid_endpoints:
                logger.warning(f"Unknown Shopify endpoint: {endpoint}")
                # Don't fail validation for unknown endpoints
            
            return True
        except Exception as e:
            logger.error(f"Error validating Shopify query: {str(e)}")
            return False
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """
        Introspect Shopify data schema for FAISS indexing
        
        Returns:
            List of schema documents for embedding and search
        """
        try:
            schema_docs = []
            
            # Orders schema
            schema_docs.append({
                "id": "shopify_orders_schema",
                "content": "Shopify Orders: Contains order data including id, customer_id, total_price, financial_status, fulfillment_status, created_at, updated_at, line_items, shipping_address, billing_address, taxes, discounts"
            })
            
            # Products schema
            schema_docs.append({
                "id": "shopify_products_schema", 
                "content": "Shopify Products: Contains product data including id, title, description, vendor, product_type, handle, status, variants, options, images, tags, price"
            })
            
            # Customers schema
            schema_docs.append({
                "id": "shopify_customers_schema",
                "content": "Shopify Customers: Contains customer data including id, first_name, last_name, email, phone, addresses, orders_count, total_spent, created_at, updated_at, tags"
            })
            
            # Inventory schema
            schema_docs.append({
                "id": "shopify_inventory_schema",
                "content": "Shopify Inventory: Contains inventory levels including inventory_item_id, location_id, available, updated_at"
            })
            
            # Checkouts schema
            schema_docs.append({
                "id": "shopify_checkouts_schema",
                "content": "Shopify Checkouts: Contains abandoned cart data including id, email, total_price, line_items, created_at, updated_at, customer"
            })
            
            # Add semantic search capabilities
            search_doc = {
                "id": "slack:semantic_search",
                "content": f"""
                SEMANTIC SEARCH:
                
                You can search for messages semantically by using the semantic_search query type.
                This allows finding messages based on their meaning, not just exact keywords.
                
                Example query:
                {{
                  "type": "semantic_search",
                  "query": "discussion about annual budget planning",
                  "limit": 20,
                  "channels": ["C0123456789"],  # Optional channel filter
                  "date_from": "2023-01-01",    # Optional date filter
                  "date_to": "2023-12-31",      # Optional date filter
                  "users": ["U0123456789"]      # Optional user filter
                }}
                
                Or you can simply pass the natural language query directly to the execute_query method.
                """
            }
            schema_docs.append(search_doc)
            
            return schema_docs
                
        except Exception as e:
            logger.error(f"Error introspecting Shopify schema: {str(e)}")
            raise

    # Additional Shopify-specific tools for the registry
    
    async def analyze_product_performance(self, product_ids: List[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Analyze product performance metrics including sales, views, and conversion rates.
        
        Args:
            product_ids: Optional list of specific product IDs to analyze
            days: Number of days to analyze (default 30)
            
        Returns:
            Product performance analysis results
        """
        logger.info(f"Analyzing product performance for {len(product_ids) if product_ids else 'all'} products over {days} days")
        
        try:
            # Get products data
            products_query = {"endpoint": "products", "params": {"limit": 250}}
            if product_ids:
                products_query["params"]["ids"] = ",".join(product_ids)
            
            products = await self.execute(products_query)
            
            # Get recent orders for sales analysis
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            orders_query = {"endpoint": "orders", "params": {"status": "any", "created_at_min": since_date, "limit": 250}}
            orders = await self.execute(orders_query)
            
            # Analyze product performance
            product_performance = {}
            
            for product in products:
                product_id = str(product.get('id'))
                product_performance[product_id] = {
                    "product_id": product_id,
                    "title": product.get('title', 'Unknown'),
                    "vendor": product.get('vendor', 'Unknown'),
                    "product_type": product.get('product_type', 'Unknown'),
                    "status": product.get('status', 'Unknown'),
                    "created_at": product.get('created_at'),
                    "total_sales": 0,
                    "units_sold": 0,
                    "orders_count": 0,
                    "average_order_value": 0,
                    "revenue": 0.0,
                    "variant_count": len(product.get('variants', [])),
                    "image_count": len(product.get('images', []))
                }
            
            # Calculate sales metrics from orders
            for order in orders:
                for line_item in order.get('line_items', []):
                    product_id = str(line_item.get('product_id'))
                    if product_id in product_performance:
                        quantity = int(line_item.get('quantity', 0))
                        price = float(line_item.get('price', 0))
                        
                        product_performance[product_id]["units_sold"] += quantity
                        product_performance[product_id]["orders_count"] += 1
                        product_performance[product_id]["revenue"] += quantity * price
                        product_performance[product_id]["total_sales"] += 1
            
            # Calculate average order values
            for product_id, metrics in product_performance.items():
                if metrics["orders_count"] > 0:
                    metrics["average_order_value"] = metrics["revenue"] / metrics["orders_count"]
            
            # Generate recommendations
            recommendations = self._generate_product_performance_recommendations(list(product_performance.values()))
            
            analysis_result = {
                "analysis_period_days": days,
                "products_analyzed": len(product_performance),
                "total_products": len(products),
                "total_orders_analyzed": len(orders),
                "product_metrics": list(product_performance.values()),
                "top_performers": sorted(product_performance.values(), key=lambda x: x["revenue"], reverse=True)[:10],
                "recommendations": recommendations,
                "summary": {
                    "total_revenue": sum(p["revenue"] for p in product_performance.values()),
                    "total_units_sold": sum(p["units_sold"] for p in product_performance.values()),
                    "average_products_per_order": sum(p["orders_count"] for p in product_performance.values()) / len(orders) if orders else 0
                }
            }
            
            logger.info(f"Product performance analysis completed: {analysis_result['products_analyzed']} products, ${analysis_result['summary']['total_revenue']:.2f} revenue")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Failed to analyze product performance: {e}")
            raise
    
    def _generate_product_performance_recommendations(self, product_metrics: List[Dict]) -> List[str]:
        """Generate recommendations based on product performance analysis."""
        recommendations = []
        
        try:
            # Find products with no sales
            no_sales_products = [p for p in product_metrics if p["revenue"] == 0]
            if no_sales_products:
                recommendations.append(f"{len(no_sales_products)} products have no sales - consider reviewing pricing, descriptions, or promotion strategies")
            
            # Find high-performing products
            high_performers = [p for p in product_metrics if p["revenue"] > 1000]  # Example threshold
            if high_performers:
                recommendations.append(f"{len(high_performers)} products are high performers - consider increasing inventory or creating similar products")
            
            # Check for products with low conversion
            low_conversion = [p for p in product_metrics if p["total_sales"] > 0 and p["units_sold"] / p["total_sales"] < 0.5]
            if low_conversion:
                recommendations.append(f"{len(low_conversion)} products have low conversion rates - review product descriptions and images")
            
            # Check for products without images
            no_images = [p for p in product_metrics if p["image_count"] == 0]
            if no_images:
                recommendations.append(f"{len(no_images)} products have no images - add product photos to improve conversion")
                
        except Exception as e:
            logger.warning(f"Failed to generate product recommendations: {e}")
        
        return recommendations
    
    async def optimize_inventory_tracking(self, location_ids: List[str] = None) -> Dict[str, Any]:
        """
        Optimize inventory tracking and identify stock level issues.
        
        Args:
            location_ids: Optional list of location IDs to focus on
            
        Returns:
            Inventory optimization results
        """
        logger.info(f"Optimizing inventory tracking for {len(location_ids) if location_ids else 'all'} locations")
        
        try:
            # Get inventory levels
            inventory_query = {"endpoint": "inventory_levels", "params": {"limit": 250}}
            if location_ids:
                inventory_query["params"]["location_ids"] = ",".join(location_ids)
            
            inventory_levels = await self.execute(inventory_query)
            
            # Get products for context
            products_query = {"endpoint": "products", "params": {"limit": 250}}
            products = await self.execute(products_query)
            
            # Create product lookup
            product_lookup = {}
            for product in products:
                for variant in product.get('variants', []):
                    variant_id = variant.get('inventory_item_id')
                    if variant_id:
                        product_lookup[str(variant_id)] = {
                            "product_title": product.get('title'),
                            "variant_title": variant.get('title'),
                            "sku": variant.get('sku'),
                            "price": variant.get('price')
                        }
            
            # Analyze inventory levels
            inventory_analysis = {}
            low_stock_items = []
            out_of_stock_items = []
            overstocked_items = []
            
            for item in inventory_levels:
                inventory_item_id = str(item.get('inventory_item_id'))
                available = item.get('available', 0)
                location_id = item.get('location_id')
                
                product_info = product_lookup.get(inventory_item_id, {})
                
                # Categorize inventory levels
                if available == 0:
                    out_of_stock_items.append({
                        "inventory_item_id": inventory_item_id,
                        "location_id": location_id,
                        "available": available,
                        **product_info
                    })
                elif available < 10:  # Low stock threshold
                    low_stock_items.append({
                        "inventory_item_id": inventory_item_id,
                        "location_id": location_id,
                        "available": available,
                        **product_info
                    })
                elif available > 100:  # Overstock threshold
                    overstocked_items.append({
                        "inventory_item_id": inventory_item_id,
                        "location_id": location_id,
                        "available": available,
                        **product_info
                    })
                
                inventory_analysis[inventory_item_id] = {
                    "inventory_item_id": inventory_item_id,
                    "location_id": location_id,
                    "available": available,
                    "status": "out_of_stock" if available == 0 else "low_stock" if available < 10 else "overstock" if available > 100 else "normal",
                    **product_info
                }
            
            # Generate optimization recommendations
            recommendations = self._generate_inventory_recommendations(low_stock_items, out_of_stock_items, overstocked_items)
            
            optimization_result = {
                "inventory_items_analyzed": len(inventory_levels),
                "location_ids": list(set(item.get('location_id') for item in inventory_levels)),
                "stock_analysis": {
                    "out_of_stock": len(out_of_stock_items),
                    "low_stock": len(low_stock_items),
                    "overstocked": len(overstocked_items),
                    "normal_stock": len(inventory_levels) - len(out_of_stock_items) - len(low_stock_items) - len(overstocked_items)
                },
                "critical_items": {
                    "out_of_stock_items": out_of_stock_items[:10],  # Top 10
                    "low_stock_items": low_stock_items[:10],
                    "overstocked_items": overstocked_items[:10]
                },
                "recommendations": recommendations,
                "inventory_health_score": self._calculate_inventory_health_score(
                    len(inventory_levels), len(low_stock_items), len(out_of_stock_items), len(overstocked_items)
                ),
                "optimization_opportunities": {
                    "reorder_needed": len(out_of_stock_items) + len(low_stock_items),
                    "excess_inventory_value": sum(float(item.get('price', 0)) * item.get('available', 0) for item in overstocked_items)
                }
            }
            
            logger.info(f"Inventory optimization completed: {optimization_result['inventory_health_score']:.1f}% health score")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Failed to optimize inventory tracking: {e}")
            raise
            
            # Analyze inventory levels
            low_stock_items = []
            out_of_stock_items = []
            overstocked_items = []
            
            for item in inventory_levels:
                available = item.get('available', 0)
                inventory_item_id = str(item.get('inventory_item_id'))
                location_id = str(item.get('location_id'))
                
                product_info = product_lookup.get(inventory_item_id, {})
                
                inventory_analysis = {
                    "inventory_item_id": inventory_item_id,
                    "location_id": location_id,
                    "available_quantity": available,
                    "product_info": product_info,
                    "updated_at": item.get('updated_at')
                }
                
                if available == 0:
                    out_of_stock_items.append(inventory_analysis)
                elif available <= 5:  # Low stock threshold
                    low_stock_items.append(inventory_analysis)
                elif available >= 100:  # Overstock threshold
                    overstocked_items.append(inventory_analysis)
            
            # Generate optimization recommendations
            recommendations = self._generate_inventory_recommendations(
                low_stock_items, out_of_stock_items, overstocked_items
            )
            
            optimization_result = {
                "total_inventory_items": len(inventory_levels),
                "locations_analyzed": len(set(item.get('location_id') for item in inventory_levels)),
                "low_stock_count": len(low_stock_items),
                "out_of_stock_count": len(out_of_stock_items),
                "overstocked_count": len(overstocked_items),
                "low_stock_items": low_stock_items[:20],  # Top 20
                "out_of_stock_items": out_of_stock_items[:20],  # Top 20
                "overstocked_items": overstocked_items[:10],  # Top 10
                "recommendations": recommendations,
                "inventory_health_score": self._calculate_inventory_health_score(
                    len(inventory_levels), len(low_stock_items), len(out_of_stock_items), len(overstocked_items)
                )
            }
            
            logger.info(f"Inventory optimization completed: {optimization_result['inventory_health_score']:.1f}% health score")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Failed to optimize inventory tracking: {e}")
            raise
    
    def _generate_inventory_recommendations(
        self, 
        low_stock: List[Dict], 
        out_of_stock: List[Dict], 
        overstocked: List[Dict]
    ) -> List[str]:
        """Generate inventory optimization recommendations."""
        recommendations = []
        
        if out_of_stock:
            recommendations.append(f"Urgent: {len(out_of_stock)} items are out of stock - immediate restocking needed")
        
        if low_stock:
            recommendations.append(f"Warning: {len(low_stock)} items have low stock levels - consider reordering soon")
        
        if overstocked:
            recommendations.append(f"Note: {len(overstocked)} items may be overstocked - consider promotions or reduced ordering")
        
        return recommendations
    
    def _calculate_inventory_health_score(
        self, 
        total_items: int, 
        low_stock: int, 
        out_of_stock: int, 
        overstocked: int
    ) -> float:
        """Calculate an inventory health score (0-100)."""
        if total_items == 0:
            return 0.0
        
        # Penalize out of stock and low stock more heavily
        penalty = (out_of_stock * 3 + low_stock * 2 + overstocked * 1) / total_items
        health_score = max(0, 100 - (penalty * 100))
        
        return health_score
    
    async def get_order_statistics(self, days: int = 30, status_filter: str = "any") -> Dict[str, Any]:
        """
        Get comprehensive order statistics and trends.
        
        Args:
            days: Number of days to analyze (default 30)
            status_filter: Order status filter ("any", "paid", "pending", etc.)
            
        Returns:
            Order statistics and trends
        """
        logger.info(f"Getting order statistics for {days} days with status filter: {status_filter}")
        
        try:
            # Get orders data
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            orders_query = {
                "endpoint": "orders",
                "params": {
                    "status": status_filter,
                    "created_at_min": since_date,
                    "limit": 250
                }
            }
            
            orders = await self.execute(orders_query)
            
            # Calculate statistics
            total_orders = len(orders)
            total_revenue = sum(float(order.get('total_price', 0)) for order in orders)
            total_items = sum(len(order.get('line_items', [])) for order in orders)
            
            # Calculate averages
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            avg_items_per_order = total_items / total_orders if total_orders > 0 else 0
            
            # Analyze by status
            status_breakdown = {}
            for order in orders:
                financial_status = order.get('financial_status', 'unknown')
                fulfillment_status = order.get('fulfillment_status', 'unfulfilled')
                
                key = f"{financial_status}_{fulfillment_status}"
                if key not in status_breakdown:
                    status_breakdown[key] = {"count": 0, "revenue": 0}
                
                status_breakdown[key]["count"] += 1
                status_breakdown[key]["revenue"] += float(order.get('total_price', 0))
            
            # Analyze by day
            daily_breakdown = {}
            for order in orders:
                created_at = order.get('created_at', '')
                order_date = created_at.split('T')[0] if created_at else 'unknown'
                
                if order_date not in daily_breakdown:
                    daily_breakdown[order_date] = {"count": 0, "revenue": 0}
                
                daily_breakdown[order_date]["count"] += 1
                daily_breakdown[order_date]["revenue"] += float(order.get('total_price', 0))
            
            # Top customers by order value
            customer_analysis = {}
            for order in orders:
                customer_id = order.get('customer', {}).get('id') if order.get('customer') else 'guest'
                customer_email = order.get('customer', {}).get('email') if order.get('customer') else 'guest'
                
                if customer_id not in customer_analysis:
                    customer_analysis[customer_id] = {
                        "email": customer_email,
                        "order_count": 0,
                        "total_spent": 0
                    }
                
                customer_analysis[customer_id]["order_count"] += 1
                customer_analysis[customer_id]["total_spent"] += float(order.get('total_price', 0))
            
            top_customers = sorted(
                customer_analysis.values(),
                key=lambda x: x["total_spent"],
                reverse=True
            )[:10]
            
            statistics = {
                "analysis_period_days": days,
                "status_filter": status_filter,
                "summary": {
                    "total_orders": total_orders,
                    "total_revenue": total_revenue,
                    "total_items_sold": total_items,
                    "average_order_value": avg_order_value,
                    "average_items_per_order": avg_items_per_order
                },
                "status_breakdown": status_breakdown,
                "daily_breakdown": daily_breakdown,
                "top_customers": top_customers,
                "recommendations": self._generate_order_recommendations(orders)
            }
            
            logger.info(f"Order statistics completed: {total_orders} orders, ${total_revenue:.2f} revenue")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get order statistics: {e}")
            raise
    
    def _generate_order_recommendations(self, orders: List[Dict]) -> List[str]:
        """Generate recommendations based on order analysis."""
        recommendations = []
        
        try:
            # Check for pending payments
            pending_payments = [o for o in orders if o.get('financial_status') == 'pending']
            if pending_payments:
                recommendations.append(f"{len(pending_payments)} orders have pending payments - follow up needed")
            
            # Check for unfulfilled orders
            unfulfilled = [o for o in orders if o.get('fulfillment_status') in [None, 'unfulfilled']]
            if unfulfilled:
                recommendations.append(f"{len(unfulfilled)} orders are unfulfilled - prioritize fulfillment")
            
            # Check for high-value orders
            high_value = [o for o in orders if float(o.get('total_price', 0)) > 500]
            if high_value:
                recommendations.append(f"{len(high_value)} high-value orders detected - ensure premium service")
                
        except Exception as e:
            logger.warning(f"Failed to generate order recommendations: {e}")
        
        return recommendations
    
    async def validate_webhook_signature(self, payload: bytes, signature: str, topic: str) -> Dict[str, Any]:
        """
        Validate webhook signature and provide security analysis.
        
        Args:
            payload: Raw webhook payload
            signature: Signature header value
            topic: Webhook topic
            
        Returns:
            Validation results and security analysis
        """
        logger.info(f"Validating webhook signature for topic: {topic}")
        
        try:
            # Validate signature
            is_valid = await self.verify_webhook(payload, signature)
            
            # Parse payload for analysis
            try:
                payload_data = json.loads(payload.decode('utf-8'))
            except:
                payload_data = {}
            
            # Security analysis
            security_analysis = {
                "signature_valid": is_valid,
                "topic": topic,
                "payload_size_bytes": len(payload),
                "timestamp": datetime.now().isoformat(),
                "shop_domain": self.shop_domain,
                "security_recommendations": []
            }
            
            # Add security recommendations
            if not is_valid:
                security_analysis["security_recommendations"].append("Invalid webhook signature - potential security risk")
            
            if len(payload) > 1024 * 1024:  # 1MB
                security_analysis["security_recommendations"].append("Large payload size - monitor for potential DoS attacks")
            
            if topic.startswith('app/'):
                security_analysis["security_recommendations"].append("App-related webhook - ensure proper app permissions")
            
            logger.info(f"Webhook validation completed: {is_valid} for topic {topic}")
            return security_analysis
            
        except Exception as e:
            logger.error(f"Failed to validate webhook signature: {e}")
            raise 