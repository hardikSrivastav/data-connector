"""
Uniware (Unicommerce) Adapter for querying order and warehouse management data
Integrates with Ceneca's AI analytics system
"""
import asyncio
import aiohttp
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from .base import DBAdapter

# Configure logging
logger = logging.getLogger(__name__)

class UniwareAdapter(DBAdapter):
    """
    Adapter for Uniware (Unicommerce) order and warehouse management platform
    
    This adapter handles OAuth2 authentication and provides comprehensive
    order, inventory, fulfillment, and returns data access.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize Uniware adapter
        
        Args:
            conn_uri: Uniware API base URL
            **kwargs: Additional arguments including:
                tenant_id: Uniware tenant ID
                facility_code: Primary facility code
                auth: Authentication configuration dict
        """
        super().__init__(conn_uri)
        self.base_url = conn_uri.rstrip("/")
        self.tenant_id = kwargs.get('tenant_id')
        self.facility_code = kwargs.get('facility_code')
        self.auth_config = kwargs.get('auth', {})
        
        # Session management
        self.session = None
        self.access_token = None
        self.token_expires_at = None
        
        # Credentials file for storing tokens
        self.credentials_file = os.path.join(
            str(Path.home()), 
            ".data-connector", 
            "uniware_credentials.json"
        )
        
        # Load existing credentials if available
        self._load_credentials()
        
    def _load_credentials(self) -> bool:
        """Load stored Uniware credentials if available"""
        try:
            if not os.path.exists(self.credentials_file):
                logger.info(f"Uniware credentials file not found: {self.credentials_file}")
                return False
                
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
                
            if self.tenant_id in credentials:
                tenant_data = credentials[self.tenant_id]
                self.access_token = tenant_data.get('access_token')
                expires_str = tenant_data.get('expires_at')
                
                if expires_str:
                    self.token_expires_at = datetime.fromisoformat(expires_str)
                    
                logger.info(f"Loaded credentials for tenant: {self.tenant_id}")
                return True
            else:
                logger.warning(f"No credentials found for tenant {self.tenant_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading Uniware credentials: {str(e)}")
            return False
    
    def _save_credentials(self, access_token: str, expires_in: int):
        """Save Uniware credentials to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
            
            # Load existing credentials or create new
            credentials = {}
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
            
            # Calculate expiry time
            expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # 5min buffer
            
            # Save credentials for this tenant
            credentials[self.tenant_id] = {
                'access_token': access_token,
                'expires_at': expires_at.isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
                
            logger.info(f"Saved credentials for tenant: {self.tenant_id}")
            
        except Exception as e:
            logger.error(f"Error saving Uniware credentials: {str(e)}")
    
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=10,
                keepalive_timeout=30
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    async def _authenticate(self) -> str:
        """Authenticate with Uniware OAuth2 API"""
        # Check if we have a valid cached token
        if (self.access_token and self.token_expires_at and 
            self.token_expires_at > datetime.now()):
            return self.access_token
            
        session = await self._get_session()
        
        auth_data = {
            'grant_type': 'password',
            'username': self.auth_config.get('username'),
            'password': self.auth_config.get('password'),
            'client_id': self.auth_config.get('client_id'),
            'client_secret': self.auth_config.get('client_secret'),
            'scope': ' '.join(self.auth_config.get('scopes', ['read']))
        }
        
        try:
            async with session.post(
                f"{self.base_url}/oauth/token",
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data['access_token']
                    expires_in = token_data.get('expires_in', 3600)
                    
                    # Update expiry time
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                    
                    # Save credentials
                    self._save_credentials(self.access_token, expires_in)
                    
                    logger.info("Uniware authentication successful")
                    return self.access_token
                else:
                    error_text = await response.text()
                    raise Exception(f"Authentication failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Uniware authentication error: {e}")
            raise
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to Uniware API query"""
        schema_chunks = kwargs.get('schema_chunks', [])
        
        # Define Uniware API endpoints and their purposes
        api_endpoints = {
            'orders': {
                'list': '/orders/get',
                'details': '/orders/get/{order_id}',
                'search': '/orders/search',
                'description': 'Order management - list, search, and get order details'
            },
            'inventory': {
                'list': '/inventory/get',
                'facilities': '/facilities/get',
                'stock': '/inventory/stock',
                'description': 'Inventory management across facilities'
            },
            'fulfillment': {
                'list': '/fulfillment/get',
                'create': '/fulfillment/create',
                'update': '/fulfillment/update',
                'description': 'Fulfillment and shipping operations'
            },
            'returns': {
                'list': '/returns/get',
                'process': '/returns/process',
                'description': 'Return management and processing'
            }
        }
        
        # Simple keyword-based routing (can be enhanced with LLM later)
        query_type = 'orders'  # Default
        
        prompt_lower = nl_prompt.lower()
        if any(word in prompt_lower for word in ['inventory', 'stock', 'warehouse', 'facility']):
            query_type = 'inventory'
        elif any(word in prompt_lower for word in ['fulfillment', 'shipping', 'dispatch', 'shipment']):
            query_type = 'fulfillment'
        elif any(word in prompt_lower for word in ['return', 'refund', 'replacement', 'cancel']):
            query_type = 'returns'
        
        return {
            'type': 'uniware_api',
            'endpoint': api_endpoints[query_type]['list'],
            'method': 'GET',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt),
            'description': api_endpoints[query_type]['description']
        }
    
    def _extract_query_params(self, nl_prompt: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {}
        
        # Extract common date ranges
        prompt_lower = nl_prompt.lower()
        
        if 'last week' in prompt_lower:
            params['fromDate'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            params['toDate'] = datetime.now().strftime('%Y-%m-%d')
        elif 'last month' in prompt_lower:
            params['fromDate'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            params['toDate'] = datetime.now().strftime('%Y-%m-%d')
        elif 'today' in prompt_lower:
            params['fromDate'] = datetime.now().strftime('%Y-%m-%d')
            params['toDate'] = datetime.now().strftime('%Y-%m-%d')
        elif 'yesterday' in prompt_lower:
            yesterday = datetime.now() - timedelta(days=1)
            params['fromDate'] = yesterday.strftime('%Y-%m-%d')
            params['toDate'] = yesterday.strftime('%Y-%m-%d')
            
        # Add facility code if configured
        if self.facility_code:
            params['facilityCode'] = self.facility_code
            
        # Extract status filters
        if 'pending' in prompt_lower:
            params['status'] = 'PENDING'
        elif 'completed' in prompt_lower or 'complete' in prompt_lower:
            params['status'] = 'COMPLETED'
        elif 'cancelled' in prompt_lower or 'canceled' in prompt_lower:
            params['status'] = 'CANCELLED'
            
        # Limit results for performance
        params['limit'] = 100
            
        return params
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute Uniware API query"""
        try:
            access_token = await self._authenticate()
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'X-Tenant-ID': self.tenant_id
            }
            
            url = f"{self.base_url}{query['endpoint']}"
            method = query.get('method', 'GET')
            params = query.get('params', {})
            
            logger.info(f"Executing Uniware API call: {method} {url}")
            logger.debug(f"Params: {params}")
            
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Normalize response based on endpoint category
                    category = query.get('category', 'unknown')
                    if category == 'orders':
                        return self._normalize_orders(data)
                    elif category == 'inventory':
                        return self._normalize_inventory(data)
                    elif category == 'fulfillment':
                        return self._normalize_fulfillment(data)
                    elif category == 'returns':
                        return self._normalize_returns(data)
                    else:
                        # Return raw data if no specific normalizer
                        return [data] if isinstance(data, dict) else data
                        
                elif response.status == 401:
                    # Token expired, clear it and retry once
                    self.access_token = None
                    self.token_expires_at = None
                    logger.warning("Uniware token expired, retrying authentication")
                    raise Exception("Authentication token expired")
                else:
                    error_text = await response.text()
                    logger.error(f"Uniware API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Uniware query execution error: {e}")
            return []
    
    def _normalize_orders(self, data: Dict) -> List[Dict]:
        """Normalize order data from Uniware API response"""
        orders = data.get('orders', data.get('elements', []))
        normalized = []
        
        for order in orders:
            normalized.append({
                'id': order.get('id'),
                'order_code': order.get('orderCode', order.get('code')),
                'channel': order.get('channel', order.get('channelName')),
                'status': order.get('status'),
                'total_amount': order.get('totalAmount', order.get('total')),
                'created_at': order.get('createdAt', order.get('created')),
                'updated_at': order.get('updatedAt', order.get('updated')),
                'customer_name': order.get('customerName', order.get('shippingAddress', {}).get('name')),
                'customer_email': order.get('customerEmail', order.get('email')),
                'customer_phone': order.get('customerPhone', order.get('phone')),
                'items_count': len(order.get('items', order.get('orderItems', []))),
                'shipping_method': order.get('shippingMethod'),
                'payment_method': order.get('paymentMethod'),
                'type': 'order',
                'source': 'uniware'
            })
        
        return normalized
    
    def _normalize_inventory(self, data: Dict) -> List[Dict]:
        """Normalize inventory data from Uniware API response"""
        inventory = data.get('inventory', data.get('elements', []))
        normalized = []
        
        for item in inventory:
            normalized.append({
                'id': item.get('id'),
                'sku': item.get('sku', item.get('skuCode')),
                'product_name': item.get('productName', item.get('name')),
                'available_quantity': item.get('availableQuantity', item.get('available')),
                'allocated_quantity': item.get('allocatedQuantity', item.get('allocated')),
                'inventory_quantity': item.get('inventoryQuantity', item.get('inventory')),
                'facility_code': item.get('facilityCode'),
                'facility_name': item.get('facilityName'),
                'last_updated': item.get('lastUpdated', item.get('updated')),
                'type': 'inventory',
                'source': 'uniware'
            })
        
        return normalized
    
    def _normalize_fulfillment(self, data: Dict) -> List[Dict]:
        """Normalize fulfillment data from Uniware API response"""
        fulfillments = data.get('fulfillments', data.get('elements', []))
        normalized = []
        
        for fulfillment in fulfillments:
            normalized.append({
                'id': fulfillment.get('id'),
                'order_code': fulfillment.get('orderCode'),
                'status': fulfillment.get('status'),
                'tracking_number': fulfillment.get('trackingNumber'),
                'shipping_provider': fulfillment.get('shippingProvider'),
                'shipped_date': fulfillment.get('shippedDate'),
                'delivery_date': fulfillment.get('deliveryDate'),
                'expected_delivery': fulfillment.get('expectedDeliveryDate'),
                'created_at': fulfillment.get('createdAt'),
                'updated_at': fulfillment.get('updatedAt'),
                'type': 'fulfillment',
                'source': 'uniware'
            })
        
        return normalized
    
    def _normalize_returns(self, data: Dict) -> List[Dict]:
        """Normalize return data from Uniware API response"""
        returns = data.get('returns', data.get('elements', []))
        normalized = []
        
        for return_item in returns:
            normalized.append({
                'id': return_item.get('id'),
                'order_code': return_item.get('orderCode'),
                'return_code': return_item.get('returnCode'),
                'status': return_item.get('status'),
                'reason': return_item.get('reason'),
                'return_date': return_item.get('returnDate'),
                'refund_amount': return_item.get('refundAmount'),
                'created_at': return_item.get('createdAt'),
                'updated_at': return_item.get('updatedAt'),
                'type': 'return',
                'source': 'uniware'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return Uniware schema information for the LLM"""
        return [
            {
                'id': 'uniware_orders',
                'content': '''Uniware Orders: Contains e-commerce order information
                Fields: id, order_code, channel, status (PENDING/COMPLETED/CANCELLED), total_amount, 
                created_at, updated_at, customer_name, customer_email, customer_phone, items_count, 
                shipping_method, payment_method
                
                Use for: Order tracking, sales analysis, customer orders, order status queries
                Example queries: "Show orders from last week", "Find pending orders", "Orders by customer email"'''
            },
            {
                'id': 'uniware_inventory',
                'content': '''Uniware Inventory: Contains product inventory across facilities
                Fields: id, sku, product_name, available_quantity, allocated_quantity, inventory_quantity,
                facility_code, facility_name, last_updated
                
                Use for: Stock levels, inventory management, warehouse queries, product availability
                Example queries: "Show low stock items", "Inventory by facility", "Product availability"'''
            },
            {
                'id': 'uniware_fulfillment',
                'content': '''Uniware Fulfillment: Contains shipping and fulfillment information
                Fields: id, order_code, status, tracking_number, shipping_provider, shipped_date, 
                delivery_date, expected_delivery, created_at, updated_at
                
                Use for: Shipment tracking, delivery status, logistics analysis
                Example queries: "Track shipments", "Delivery performance", "Pending fulfillments"'''
            },
            {
                'id': 'uniware_returns',
                'content': '''Uniware Returns: Contains return and refund information
                Fields: id, order_code, return_code, status, reason, return_date, refund_amount,
                created_at, updated_at
                
                Use for: Return processing, refund tracking, return analytics
                Example queries: "Show recent returns", "Returns by reason", "Refund amounts"'''
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test Uniware connection"""
        try:
            # Try to authenticate
            access_token = await self._authenticate()
            if not access_token:
                return False
                
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'X-Tenant-ID': self.tenant_id
            }
            
            # Test with a simple API call
            async with session.get(
                f"{self.base_url}/facilities/get",
                headers=headers,
                params={'limit': 1}
            ) as response:
                success = response.status == 200
                if success:
                    logger.info("Uniware connection test successful")
                else:
                    error_text = await response.text()
                    logger.error(f"Uniware connection test failed: {response.status} - {error_text}")
                return success
                
        except Exception as e:
            logger.error(f"Uniware connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None 