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
            query: Query object from llm_to_query or orchestrator parameters
            
        Returns:
            List of results from Shopify API
        """
        try:
            # Handle orchestrator-style parameters
            if isinstance(query, dict):
                if query.get("type") == "shopify_api":
                    # Legacy format from llm_to_query
                    query_info = query["query"]
                    endpoint = query_info["endpoint"]
                    params = query_info.get("params", {})
                elif "endpoint" in query:
                    # New orchestrator format
                    endpoint = query.get("endpoint", "orders")
                    params = query.get("params", {})
                    # Handle limit parameter
                    if "limit" in query:
                        params["limit"] = query["limit"]
                else:
                    raise ValueError("Invalid query format for Shopify adapter")
                
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
            else:
                raise ValueError("Invalid query format for Shopify adapter")
                
        except Exception as e:
            logger.error(f"Error executing Shopify query: {str(e)}")
            return [{"error": str(e)}]
    
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
            
            return schema_docs
            
        except Exception as e:
            logger.error(f"Error introspecting Shopify schema: {str(e)}")
            return [{"id": "error", "content": f"Schema introspection error: {str(e)}"}] 