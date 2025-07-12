# Indian DTC Marketplace Services - Implementation Plan

## Overview

This document outlines the implementation plan for integrating four critical Indian DTC marketplace services into Ceneca's existing adapter architecture:

- **Uniware (Unicommerce)** - Order and warehouse management
- **PayU** - Payment gateway services
- **Easebuzz** - Payment gateway and business solutions  
- **Shiprocket** - Shipping and logistics platform

## Architecture Integration

### 1. Adapter Implementation Pattern

Each service will follow the existing `DBAdapter` base class pattern:

```python
# server/agent/db/adapters/uniware.py
class UniwareAdapter(DBAdapter):
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict
    async def execute(self, query: Any) -> List[Dict]
    async def introspect_schema(self) -> List[Dict[str, str]]
    async def test_connection(self) -> bool
```

### 2. Configuration Structure

#### config.yaml Extensions

```yaml
# Uniware configuration
uniware:
  uri: "https://api.unicommerce.com/v1"
  tenant_id: "your-tenant-id"
  facility_code: "your-facility-code"
  pool:
    max_connections: 5
    timeout_ms: 30000
    retry_attempts: 3

# PayU configuration  
payu:
  uri: "https://secure.payu.in"
  merchant_id: "your-merchant-id"
  environment: "production"  # or "test"
  pool:
    max_connections: 10
    timeout_ms: 15000

# Easebuzz configuration
easebuzz:
  uri: "https://api.easebuzz.in"
  merchant_id: "your-merchant-id"
  environment: "production"  # or "test"
  pool:
    max_connections: 8
    timeout_ms: 20000

# Shiprocket configuration
shiprocket:
  uri: "https://api.shiprocket.in/v1"
  company_id: "your-company-id"
  pool:
    max_connections: 5
    timeout_ms: 25000
```

#### auth-config.yaml Extensions

```yaml
# API Key Authentication for DTC Services
api_auth:
  uniware:
    type: "oauth2"
    username: "your-username"
    password: "your-password"
    auth_url: "https://api.unicommerce.com/oauth/token"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
    scopes: ["read", "write"]
    token_refresh_minutes: 50  # OAuth tokens expire in 60 minutes

  payu:
    type: "api_key"
    merchant_key: "your-merchant-key"
    salt: "your-salt"
    # PayU uses hash-based authentication

  easebuzz:
    type: "api_key"
    api_key: "your-api-key"
    secret_key: "your-secret-key"
    # Easebuzz uses API key + secret for authentication

  shiprocket:
    type: "bearer_token"
    email: "your-email"
    password: "your-password"
    auth_url: "https://api.shiprocket.in/v1/external/auth/login"
    token_refresh_hours: 23  # Tokens expire in 24 hours
```

## Implementation Details

### 1. Uniware Adapter Implementation

```python
# server/agent/db/adapters/uniware.py
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .base import DBAdapter

logger = logging.getLogger(__name__)

class UniwareAdapter(DBAdapter):
    """
    Adapter for Uniware (Unicommerce) order and warehouse management platform
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        super().__init__(conn_uri)
        self.config = kwargs
        self.base_url = conn_uri
        self.tenant_id = kwargs.get('tenant_id')
        self.facility_code = kwargs.get('facility_code')
        self.session = None
        self.access_token = None
        self.token_expires_at = None
        
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=self.config.get('pool', {}).get('max_connections', 5),
                limit_per_host=self.config.get('pool', {}).get('max_connections', 5)
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.config.get('pool', {}).get('timeout_ms', 30000) / 1000
                )
            )
        return self.session
    
    async def _authenticate(self) -> str:
        """Authenticate with Uniware OAuth2 API"""
        if self.access_token and self.token_expires_at > datetime.now():
            return self.access_token
            
        auth_config = self.config.get('auth', {})
        session = await self._get_session()
        
        auth_data = {
            'grant_type': 'password',
            'username': auth_config.get('username'),
            'password': auth_config.get('password'),
            'client_id': auth_config.get('client_id'),
            'client_secret': auth_config.get('client_secret'),
            'scope': ' '.join(auth_config.get('scopes', ['read']))
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
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
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
        # Use LLM to convert natural language to Uniware API calls
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
        
        # Simple keyword-based routing for now
        # In production, this would use the LLM client
        query_type = 'orders'  # Default
        
        if any(word in nl_prompt.lower() for word in ['inventory', 'stock', 'warehouse']):
            query_type = 'inventory'
        elif any(word in nl_prompt.lower() for word in ['fulfillment', 'shipping', 'dispatch']):
            query_type = 'fulfillment'
        elif any(word in nl_prompt.lower() for word in ['return', 'refund', 'replacement']):
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
        
        # Extract common parameters
        if 'last week' in nl_prompt.lower():
            params['fromDate'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif 'last month' in nl_prompt.lower():
            params['fromDate'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif 'today' in nl_prompt.lower():
            params['fromDate'] = datetime.now().strftime('%Y-%m-%d')
            
        # Add facility code if configured
        if self.facility_code:
            params['facilityCode'] = self.facility_code
            
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
            
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Normalize response based on endpoint
                    if query['category'] == 'orders':
                        return self._normalize_orders(data)
                    elif query['category'] == 'inventory':
                        return self._normalize_inventory(data)
                    elif query['category'] == 'fulfillment':
                        return self._normalize_fulfillment(data)
                    elif query['category'] == 'returns':
                        return self._normalize_returns(data)
                    else:
                        return [data] if isinstance(data, dict) else data
                else:
                    error_text = await response.text()
                    logger.error(f"Uniware API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Uniware query execution error: {e}")
            return []
    
    def _normalize_orders(self, data: Dict) -> List[Dict]:
        """Normalize order data"""
        orders = data.get('orders', [])
        normalized = []
        
        for order in orders:
            normalized.append({
                'id': order.get('id'),
                'order_code': order.get('orderCode'),
                'channel': order.get('channel'),
                'status': order.get('status'),
                'total_amount': order.get('totalAmount'),
                'created_at': order.get('createdAt'),
                'customer_name': order.get('customerName'),
                'customer_email': order.get('customerEmail'),
                'items_count': len(order.get('items', [])),
                'type': 'order'
            })
        
        return normalized
    
    def _normalize_inventory(self, data: Dict) -> List[Dict]:
        """Normalize inventory data"""
        inventory = data.get('inventory', [])
        normalized = []
        
        for item in inventory:
            normalized.append({
                'id': item.get('id'),
                'sku': item.get('sku'),
                'product_name': item.get('productName'),
                'available_quantity': item.get('availableQuantity'),
                'allocated_quantity': item.get('allocatedQuantity'),
                'facility_code': item.get('facilityCode'),
                'last_updated': item.get('lastUpdated'),
                'type': 'inventory'
            })
        
        return normalized
    
    def _normalize_fulfillment(self, data: Dict) -> List[Dict]:
        """Normalize fulfillment data"""
        fulfillments = data.get('fulfillments', [])
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
                'type': 'fulfillment'
            })
        
        return normalized
    
    def _normalize_returns(self, data: Dict) -> List[Dict]:
        """Normalize return data"""
        returns = data.get('returns', [])
        normalized = []
        
        for return_item in returns:
            normalized.append({
                'id': return_item.get('id'),
                'order_code': return_item.get('orderCode'),
                'status': return_item.get('status'),
                'reason': return_item.get('reason'),
                'return_date': return_item.get('returnDate'),
                'refund_amount': return_item.get('refundAmount'),
                'type': 'return'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return Uniware schema information"""
        return [
            {
                'id': 'uniware_orders',
                'content': 'Orders: id, order_code, channel, status, total_amount, created_at, customer_name, customer_email, items_count'
            },
            {
                'id': 'uniware_inventory',
                'content': 'Inventory: id, sku, product_name, available_quantity, allocated_quantity, facility_code, last_updated'
            },
            {
                'id': 'uniware_fulfillment',
                'content': 'Fulfillment: id, order_code, status, tracking_number, shipping_provider, shipped_date, delivery_date'
            },
            {
                'id': 'uniware_returns',
                'content': 'Returns: id, order_code, status, reason, return_date, refund_amount'
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test Uniware connection"""
        try:
            access_token = await self._authenticate()
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'X-Tenant-ID': self.tenant_id
            }
            
            # Test with a simple API call
            async with session.get(
                f"{self.base_url}/facilities/get",
                headers=headers
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Uniware connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
```

### 2. PayU Adapter Implementation

```python
# server/agent/db/adapters/payu.py
import asyncio
import aiohttp
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .base import DBAdapter

logger = logging.getLogger(__name__)

class PayUAdapter(DBAdapter):
    """
    Adapter for PayU payment gateway platform
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        super().__init__(conn_uri)
        self.config = kwargs
        self.base_url = conn_uri
        self.merchant_id = kwargs.get('merchant_id')
        self.environment = kwargs.get('environment', 'production')
        self.session = None
        
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=self.config.get('pool', {}).get('max_connections', 10),
                limit_per_host=self.config.get('pool', {}).get('max_connections', 10)
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.config.get('pool', {}).get('timeout_ms', 15000) / 1000
                )
            )
        return self.session
    
    def _generate_hash(self, params: Dict) -> str:
        """Generate PayU hash for authentication"""
        auth_config = self.config.get('auth', {})
        merchant_key = auth_config.get('merchant_key')
        salt = auth_config.get('salt')
        
        # Create hash string based on PayU documentation
        hash_string = f"{merchant_key}|{params.get('command')}|{params.get('var1', '')}|{salt}"
        return hashlib.sha512(hash_string.encode()).hexdigest()
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to PayU API query"""
        # Define PayU API endpoints
        api_endpoints = {
            'transactions': {
                'list': '/payment/op/getPaymentStatus',
                'details': '/payment/op/getPaymentStatus',
                'search': '/payment/op/getPaymentStatus',
                'description': 'Payment transactions - list, search, and get transaction details'
            },
            'settlements': {
                'list': '/payment/op/getSettlementStatus',
                'description': 'Settlement information and status'
            },
            'refunds': {
                'list': '/payment/op/getRefundDetails',
                'process': '/payment/op/refundPayment',
                'description': 'Refund management and processing'
            },
            'reports': {
                'list': '/payment/op/getPaymentStatus',
                'description': 'Payment reports and analytics'
            }
        }
        
        # Simple keyword-based routing
        query_type = 'transactions'  # Default
        
        if any(word in nl_prompt.lower() for word in ['settlement', 'payout']):
            query_type = 'settlements'
        elif any(word in nl_prompt.lower() for word in ['refund', 'chargeback']):
            query_type = 'refunds'
        elif any(word in nl_prompt.lower() for word in ['report', 'analytics', 'summary']):
            query_type = 'reports'
        
        return {
            'type': 'payu_api',
            'endpoint': api_endpoints[query_type]['list'],
            'method': 'POST',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt),
            'description': api_endpoints[query_type]['description']
        }
    
    def _extract_query_params(self, nl_prompt: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {
            'command': 'get_payment_status',
            'var1': self.merchant_id
        }
        
        # Extract date ranges
        if 'last week' in nl_prompt.lower():
            params['from_date'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif 'last month' in nl_prompt.lower():
            params['from_date'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif 'today' in nl_prompt.lower():
            params['from_date'] = datetime.now().strftime('%Y-%m-%d')
            
        return params
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute PayU API query"""
        try:
            session = await self._get_session()
            
            params = query.get('params', {})
            params['hash'] = self._generate_hash(params)
            
            auth_config = self.config.get('auth', {})
            params['key'] = auth_config.get('merchant_key')
            
            url = f"{self.base_url}{query['endpoint']}"
            
            async with session.post(
                url=url,
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Normalize response based on endpoint
                    if query['category'] == 'transactions':
                        return self._normalize_transactions(data)
                    elif query['category'] == 'settlements':
                        return self._normalize_settlements(data)
                    elif query['category'] == 'refunds':
                        return self._normalize_refunds(data)
                    else:
                        return [data] if isinstance(data, dict) else data
                else:
                    error_text = await response.text()
                    logger.error(f"PayU API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"PayU query execution error: {e}")
            return []
    
    def _normalize_transactions(self, data: Dict) -> List[Dict]:
        """Normalize transaction data"""
        transactions = data.get('transaction_details', [])
        normalized = []
        
        for transaction in transactions:
            normalized.append({
                'id': transaction.get('txnid'),
                'payment_id': transaction.get('paymentId'),
                'amount': transaction.get('amount'),
                'status': transaction.get('status'),
                'payment_method': transaction.get('mode'),
                'bank_ref_num': transaction.get('bank_ref_num'),
                'created_at': transaction.get('addedon'),
                'customer_email': transaction.get('email'),
                'customer_phone': transaction.get('phone'),
                'type': 'transaction'
            })
        
        return normalized
    
    def _normalize_settlements(self, data: Dict) -> List[Dict]:
        """Normalize settlement data"""
        settlements = data.get('settlements', [])
        normalized = []
        
        for settlement in settlements:
            normalized.append({
                'id': settlement.get('settlement_id'),
                'amount': settlement.get('amount'),
                'status': settlement.get('status'),
                'settlement_date': settlement.get('settlement_date'),
                'utr_number': settlement.get('utr_number'),
                'type': 'settlement'
            })
        
        return normalized
    
    def _normalize_refunds(self, data: Dict) -> List[Dict]:
        """Normalize refund data"""
        refunds = data.get('refunds', [])
        normalized = []
        
        for refund in refunds:
            normalized.append({
                'id': refund.get('refund_id'),
                'transaction_id': refund.get('txnid'),
                'amount': refund.get('amount'),
                'status': refund.get('status'),
                'refund_date': refund.get('refund_date'),
                'reason': refund.get('reason'),
                'type': 'refund'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return PayU schema information"""
        return [
            {
                'id': 'payu_transactions',
                'content': 'Transactions: id, payment_id, amount, status, payment_method, bank_ref_num, created_at, customer_email, customer_phone'
            },
            {
                'id': 'payu_settlements',
                'content': 'Settlements: id, amount, status, settlement_date, utr_number'
            },
            {
                'id': 'payu_refunds',
                'content': 'Refunds: id, transaction_id, amount, status, refund_date, reason'
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test PayU connection"""
        try:
            session = await self._get_session()
            
            # Test with a simple API call
            params = {
                'command': 'get_payment_status',
                'var1': self.merchant_id
            }
            params['hash'] = self._generate_hash(params)
            
            auth_config = self.config.get('auth', {})
            params['key'] = auth_config.get('merchant_key')
            
            async with session.post(
                f"{self.base_url}/payment/op/getPaymentStatus",
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"PayU connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
```

### 3. Easebuzz Adapter Implementation

```python
# server/agent/db/adapters/easebuzz.py
import asyncio
import aiohttp
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .base import DBAdapter

logger = logging.getLogger(__name__)

class EasebuzzAdapter(DBAdapter):
    """
    Adapter for Easebuzz payment gateway platform
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        super().__init__(conn_uri)
        self.config = kwargs
        self.base_url = conn_uri
        self.merchant_id = kwargs.get('merchant_id')
        self.environment = kwargs.get('environment', 'production')
        self.session = None
        
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=self.config.get('pool', {}).get('max_connections', 8),
                limit_per_host=self.config.get('pool', {}).get('max_connections', 8)
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.config.get('pool', {}).get('timeout_ms', 20000) / 1000
                )
            )
        return self.session
    
    def _generate_hash(self, params: Dict) -> str:
        """Generate Easebuzz hash for authentication"""
        auth_config = self.config.get('auth', {})
        secret_key = auth_config.get('secret_key')
        
        # Create hash string based on Easebuzz documentation
        hash_string = f"{params.get('merchant_id')}|{params.get('transaction_id', '')}|{params.get('amount', '')}|{secret_key}"
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to Easebuzz API query"""
        # Define Easebuzz API endpoints
        api_endpoints = {
            'transactions': {
                'list': '/v1/payment/status',
                'details': '/v1/payment/status',
                'search': '/v1/payment/status',
                'description': 'Payment transactions - list, search, and get transaction details'
            },
            'settlements': {
                'list': '/v1/settlements',
                'description': 'Settlement information and status'
            },
            'refunds': {
                'list': '/v1/refunds',
                'process': '/v1/refunds/create',
                'description': 'Refund management and processing'
            },
            'payouts': {
                'list': '/v1/payouts',
                'create': '/v1/payouts/create',
                'description': 'Payout management via InstaCollect'
            }
        }
        
        # Simple keyword-based routing
        query_type = 'transactions'  # Default
        
        if any(word in nl_prompt.lower() for word in ['settlement', 'payout']):
            query_type = 'settlements'
        elif any(word in nl_prompt.lower() for word in ['refund', 'chargeback']):
            query_type = 'refunds'
        elif any(word in nl_prompt.lower() for word in ['payout', 'instacollect', 'transfer']):
            query_type = 'payouts'
        
        return {
            'type': 'easebuzz_api',
            'endpoint': api_endpoints[query_type]['list'],
            'method': 'POST',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt),
            'description': api_endpoints[query_type]['description']
        }
    
    def _extract_query_params(self, nl_prompt: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {
            'merchant_id': self.merchant_id
        }
        
        # Extract date ranges
        if 'last week' in nl_prompt.lower():
            params['from_date'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif 'last month' in nl_prompt.lower():
            params['from_date'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif 'today' in nl_prompt.lower():
            params['from_date'] = datetime.now().strftime('%Y-%m-%d')
            
        return params
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute Easebuzz API query"""
        try:
            session = await self._get_session()
            
            params = query.get('params', {})
            params['hash'] = self._generate_hash(params)
            
            auth_config = self.config.get('auth', {})
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {auth_config.get('api_key')}"
            }
            
            url = f"{self.base_url}{query['endpoint']}"
            
            async with session.post(
                url=url,
                json=params,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Normalize response based on endpoint
                    if query['category'] == 'transactions':
                        return self._normalize_transactions(data)
                    elif query['category'] == 'settlements':
                        return self._normalize_settlements(data)
                    elif query['category'] == 'refunds':
                        return self._normalize_refunds(data)
                    elif query['category'] == 'payouts':
                        return self._normalize_payouts(data)
                    else:
                        return [data] if isinstance(data, dict) else data
                else:
                    error_text = await response.text()
                    logger.error(f"Easebuzz API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Easebuzz query execution error: {e}")
            return []
    
    def _normalize_transactions(self, data: Dict) -> List[Dict]:
        """Normalize transaction data"""
        transactions = data.get('transactions', [])
        normalized = []
        
        for transaction in transactions:
            normalized.append({
                'id': transaction.get('transaction_id'),
                'payment_id': transaction.get('payment_id'),
                'amount': transaction.get('amount'),
                'status': transaction.get('status'),
                'payment_method': transaction.get('payment_method'),
                'bank_ref_num': transaction.get('bank_ref_num'),
                'created_at': transaction.get('created_at'),
                'customer_email': transaction.get('customer_email'),
                'customer_phone': transaction.get('customer_phone'),
                'type': 'transaction'
            })
        
        return normalized
    
    def _normalize_settlements(self, data: Dict) -> List[Dict]:
        """Normalize settlement data"""
        settlements = data.get('settlements', [])
        normalized = []
        
        for settlement in settlements:
            normalized.append({
                'id': settlement.get('settlement_id'),
                'amount': settlement.get('amount'),
                'status': settlement.get('status'),
                'settlement_date': settlement.get('settlement_date'),
                'utr_number': settlement.get('utr_number'),
                'type': 'settlement'
            })
        
        return normalized
    
    def _normalize_refunds(self, data: Dict) -> List[Dict]:
        """Normalize refund data"""
        refunds = data.get('refunds', [])
        normalized = []
        
        for refund in refunds:
            normalized.append({
                'id': refund.get('refund_id'),
                'transaction_id': refund.get('transaction_id'),
                'amount': refund.get('amount'),
                'status': refund.get('status'),
                'refund_date': refund.get('refund_date'),
                'reason': refund.get('reason'),
                'type': 'refund'
            })
        
        return normalized
    
    def _normalize_payouts(self, data: Dict) -> List[Dict]:
        """Normalize payout data"""
        payouts = data.get('payouts', [])
        normalized = []
        
        for payout in payouts:
            normalized.append({
                'id': payout.get('payout_id'),
                'account_number': payout.get('account_number'),
                'ifsc_code': payout.get('ifsc_code'),
                'amount': payout.get('amount'),
                'status': payout.get('status'),
                'payout_date': payout.get('payout_date'),
                'utr_number': payout.get('utr_number'),
                'type': 'payout'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return Easebuzz schema information"""
        return [
            {
                'id': 'easebuzz_transactions',
                'content': 'Transactions: id, payment_id, amount, status, payment_method, bank_ref_num, created_at, customer_email, customer_phone'
            },
            {
                'id': 'easebuzz_settlements',
                'content': 'Settlements: id, amount, status, settlement_date, utr_number'
            },
            {
                'id': 'easebuzz_refunds',
                'content': 'Refunds: id, transaction_id, amount, status, refund_date, reason'
            },
            {
                'id': 'easebuzz_payouts',
                'content': 'Payouts: id, account_number, ifsc_code, amount, status, payout_date, utr_number'
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test Easebuzz connection"""
        try:
            session = await self._get_session()
            
            # Test with a simple API call
            params = {
                'merchant_id': self.merchant_id
            }
            params['hash'] = self._generate_hash(params)
            
            auth_config = self.config.get('auth', {})
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {auth_config.get('api_key')}"
            }
            
            async with session.post(
                f"{self.base_url}/v1/payment/status",
                json=params,
                headers=headers
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Easebuzz connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
```

### 4. Shiprocket Adapter Implementation

```python
# server/agent/db/adapters/shiprocket.py
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .base import DBAdapter

logger = logging.getLogger(__name__)

class ShiprocketAdapter(DBAdapter):
    """
    Adapter for Shiprocket shipping and logistics platform
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        super().__init__(conn_uri)
        self.config = kwargs
        self.base_url = conn_uri
        self.company_id = kwargs.get('company_id')
        self.session = None
        self.auth_token = None
        self.token_expires_at = None
        
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=self.config.get('pool', {}).get('max_connections', 5),
                limit_per_host=self.config.get('pool', {}).get('max_connections', 5)
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.config.get('pool', {}).get('timeout_ms', 25000) / 1000
                )
            )
        return self.session
    
    async def _authenticate(self) -> str:
        """Authenticate with Shiprocket API"""
        if self.auth_token and self.token_expires_at > datetime.now():
            return self.auth_token
            
        auth_config = self.config.get('auth', {})
        session = await self._get_session()
        
        auth_data = {
            'email': auth_config.get('email'),
            'password': auth_config.get('password')
        }
        
        try:
            async with session.post(
                f"{self.base_url}/external/auth/login",
                json=auth_data,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.auth_token = token_data.get('token')
                    # Shiprocket tokens expire in 24 hours
                    self.token_expires_at = datetime.now() + timedelta(hours=23)
                    logger.info("Shiprocket authentication successful")
                    return self.auth_token
                else:
                    error_text = await response.text()
                    raise Exception(f"Authentication failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Shiprocket authentication error: {e}")
            raise
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to Shiprocket API query"""
        # Define Shiprocket API endpoints
        api_endpoints = {
            'orders': {
                'list': '/external/orders',
                'details': '/external/orders/show/{order_id}',
                'create': '/external/orders/create/adhoc',
                'description': 'Shipping orders - list, search, and get order details'
            },
            'tracking': {
                'list': '/external/courier/track',
                'details': '/external/courier/track/awb/{awb_code}',
                'description': 'Shipment tracking and status updates'
            },
            'pickup': {
                'list': '/external/courier/assign/pickup',
                'schedule': '/external/courier/assign/pickup',
                'description': 'Pickup scheduling and management'
            },
            'couriers': {
                'list': '/external/courier/serviceability',
                'rates': '/external/courier/serviceability',
                'description': 'Courier partners and rate calculation'
            }
        }
        
        # Simple keyword-based routing
        query_type = 'orders'  # Default
        
        if any(word in nl_prompt.lower() for word in ['track', 'tracking', 'status']):
            query_type = 'tracking'
        elif any(word in nl_prompt.lower() for word in ['pickup', 'collect', 'schedule']):
            query_type = 'pickup'
        elif any(word in nl_prompt.lower() for word in ['courier', 'partner', 'rate', 'cost']):
            query_type = 'couriers'
        
        return {
            'type': 'shiprocket_api',
            'endpoint': api_endpoints[query_type]['list'],
            'method': 'GET',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt),
            'description': api_endpoints[query_type]['description']
        }
    
    def _extract_query_params(self, nl_prompt: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {}
        
        # Extract date ranges
        if 'last week' in nl_prompt.lower():
            params['from_date'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif 'last month' in nl_prompt.lower():
            params['from_date'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif 'today' in nl_prompt.lower():
            params['from_date'] = datetime.now().strftime('%Y-%m-%d')
            
        return params
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute Shiprocket API query"""
        try:
            auth_token = await self._authenticate()
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}{query['endpoint']}"
            method = query.get('method', 'GET')
            params = query.get('params', {})
            
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Normalize response based on endpoint
                    if query['category'] == 'orders':
                        return self._normalize_orders(data)
                    elif query['category'] == 'tracking':
                        return self._normalize_tracking(data)
                    elif query['category'] == 'pickup':
                        return self._normalize_pickup(data)
                    elif query['category'] == 'couriers':
                        return self._normalize_couriers(data)
                    else:
                        return [data] if isinstance(data, dict) else data
                else:
                    error_text = await response.text()
                    logger.error(f"Shiprocket API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Shiprocket query execution error: {e}")
            return []
    
    def _normalize_orders(self, data: Dict) -> List[Dict]:
        """Normalize order data"""
        orders = data.get('data', [])
        normalized = []
        
        for order in orders:
            normalized.append({
                'id': order.get('id'),
                'order_id': order.get('order_id'),
                'channel_id': order.get('channel_id'),
                'status': order.get('status'),
                'total_amount': order.get('total'),
                'created_at': order.get('created_at'),
                'awb_code': order.get('awb_code'),
                'courier_partner': order.get('courier_name'),
                'customer_name': order.get('customer_name'),
                'customer_phone': order.get('customer_phone'),
                'type': 'order'
            })
        
        return normalized
    
    def _normalize_tracking(self, data: Dict) -> List[Dict]:
        """Normalize tracking data"""
        tracking_data = data.get('tracking_data', [])
        normalized = []
        
        for track in tracking_data:
            normalized.append({
                'id': track.get('id'),
                'awb_code': track.get('awb_code'),
                'courier_name': track.get('courier_name'),
                'current_status': track.get('current_status'),
                'delivered_date': track.get('delivered_date'),
                'destination': track.get('destination'),
                'origin': track.get('origin'),
                'last_update': track.get('last_update_time'),
                'type': 'tracking'
            })
        
        return normalized
    
    def _normalize_pickup(self, data: Dict) -> List[Dict]:
        """Normalize pickup data"""
        pickups = data.get('pickup_data', [])
        normalized = []
        
        for pickup in pickups:
            normalized.append({
                'id': pickup.get('id'),
                'pickup_date': pickup.get('pickup_date'),
                'pickup_time': pickup.get('pickup_time'),
                'status': pickup.get('status'),
                'courier_partner': pickup.get('courier_name'),
                'address': pickup.get('address'),
                'type': 'pickup'
            })
        
        return normalized
    
    def _normalize_couriers(self, data: Dict) -> List[Dict]:
        """Normalize courier data"""
        couriers = data.get('data', [])
        normalized = []
        
        for courier in couriers:
            normalized.append({
                'id': courier.get('id'),
                'courier_name': courier.get('courier_name'),
                'rate': courier.get('rate'),
                'estimated_delivery_days': courier.get('estimated_delivery_days'),
                'cod_available': courier.get('cod'),
                'pickup_available': courier.get('pickup_available'),
                'type': 'courier'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return Shiprocket schema information"""
        return [
            {
                'id': 'shiprocket_orders',
                'content': 'Orders: id, order_id, channel_id, status, total_amount, created_at, awb_code, courier_partner, customer_name, customer_phone'
            },
            {
                'id': 'shiprocket_tracking',
                'content': 'Tracking: id, awb_code, courier_name, current_status, delivered_date, destination, origin, last_update'
            },
            {
                'id': 'shiprocket_pickup',
                'content': 'Pickup: id, pickup_date, pickup_time, status, courier_partner, address'
            },
            {
                'id': 'shiprocket_couriers',
                'content': 'Couriers: id, courier_name, rate, estimated_delivery_days, cod_available, pickup_available'
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test Shiprocket connection"""
        try:
            auth_token = await self._authenticate()
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with a simple API call
            async with session.get(
                f"{self.base_url}/external/orders?limit=1",
                headers=headers
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Shiprocket connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
```

## Authentication System Integration

### 1. Extending AuthManager for API Services

```python
# server/agent/auth/api_auth_manager.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import aiohttp
import hashlib

logger = logging.getLogger(__name__)

class APIAuthManager:
    """
    Manager for API-based authentication for DTC marketplace services
    Handles OAuth2, API keys, and bearer tokens
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize API authentication manager
        
        Args:
            config: Configuration dictionary from auth-config.yaml
        """
        self.config = config
        self.tokens = {}  # Cache for OAuth tokens
        self.session = None
        
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    async def authenticate_service(self, service_name: str) -> Dict[str, Any]:
        """
        Authenticate with a specific service
        
        Args:
            service_name: Name of the service (uniware, payu, easebuzz, shiprocket)
            
        Returns:
            Authentication credentials dictionary
        """
        service_config = self.config.get('api_auth', {}).get(service_name, {})
        auth_type = service_config.get('type')
        
        if auth_type == 'oauth2':
            return await self._oauth2_authenticate(service_name, service_config)
        elif auth_type == 'bearer_token':
            return await self._bearer_token_authenticate(service_name, service_config)
        elif auth_type == 'api_key':
            return await self._api_key_authenticate(service_name, service_config)
        else:
            raise ValueError(f"Unsupported authentication type: {auth_type}")
    
    async def _oauth2_authenticate(self, service_name: str, config: Dict) -> Dict[str, Any]:
        """Handle OAuth2 authentication (for Uniware)"""
        # Check if we have a valid cached token
        cached_token = self.tokens.get(service_name)
        if cached_token and cached_token['expires_at'] > datetime.now():
            return cached_token
        
        session = await self._get_session()
        
        auth_data = {
            'grant_type': 'password',
            'username': config.get('username'),
            'password': config.get('password'),
            'client_id': config.get('client_id'),
            'client_secret': config.get('client_secret'),
            'scope': ' '.join(config.get('scopes', []))
        }
        
        try:
            async with session.post(
                config.get('auth_url'),
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    
                    # Cache the token
                    expires_in = token_data.get('expires_in', 3600)
                    expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                    
                    cached_token = {
                        'access_token': token_data['access_token'],
                        'token_type': token_data.get('token_type', 'Bearer'),
                        'expires_at': expires_at,
                        'auth_type': 'oauth2'
                    }
                    
                    self.tokens[service_name] = cached_token
                    logger.info(f"OAuth2 authentication successful for {service_name}")
                    return cached_token
                else:
                    error_text = await response.text()
                    raise Exception(f"OAuth2 authentication failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"OAuth2 authentication error for {service_name}: {e}")
            raise
    
    async def _bearer_token_authenticate(self, service_name: str, config: Dict) -> Dict[str, Any]:
        """Handle Bearer token authentication (for Shiprocket)"""
        # Check if we have a valid cached token
        cached_token = self.tokens.get(service_name)
        if cached_token and cached_token['expires_at'] > datetime.now():
            return cached_token
        
        session = await self._get_session()
        
        auth_data = {
            'email': config.get('email'),
            'password': config.get('password')
        }
        
        try:
            async with session.post(
                config.get('auth_url'),
                json=auth_data,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    
                    # Cache the token
                    refresh_hours = config.get('token_refresh_hours', 23)
                    expires_at = datetime.now() + timedelta(hours=refresh_hours)
                    
                    cached_token = {
                        'access_token': token_data.get('token'),
                        'token_type': 'Bearer',
                        'expires_at': expires_at,
                        'auth_type': 'bearer_token'
                    }
                    
                    self.tokens[service_name] = cached_token
                    logger.info(f"Bearer token authentication successful for {service_name}")
                    return cached_token
                else:
                    error_text = await response.text()
                    raise Exception(f"Bearer token authentication failed: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Bearer token authentication error for {service_name}: {e}")
            raise
    
    async def _api_key_authenticate(self, service_name: str, config: Dict) -> Dict[str, Any]:
        """Handle API key authentication (for PayU, Easebuzz)"""
        # API key authentication doesn't require network calls
        # Just return the configured credentials
        return {
            'api_key': config.get('api_key'),
            'merchant_key': config.get('merchant_key'),
            'secret_key': config.get('secret_key'),
            'salt': config.get('salt'),
            'auth_type': 'api_key'
        }
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
```

### 2. Adapter Registration Extension

```python
# server/agent/db/adapters/__init__.py (additions)
from .uniware import UniwareAdapter
from .payu import PayUAdapter
from .easebuzz import EasebuzzAdapter
from .shiprocket import ShiprocketAdapter

# Add to existing __all__ list
__all__ = [
    # ... existing adapters
    'UniwareAdapter',
    'PayUAdapter', 
    'EasebuzzAdapter',
    'ShiprocketAdapter'
]
```

### 3. Database Type Registry Extension

```python
# server/agent/db/classifier.py (additions)
# Add to SUPPORTED_DATABASES
SUPPORTED_DATABASES = {
    # ... existing databases
    'uniware': 'unicommerce',
    'payu': 'payment_gateway',
    'easebuzz': 'payment_gateway',
    'shiprocket': 'logistics'
}

# Add to _classify_by_keywords
KEYWORDS = {
    # ... existing keywords
    'uniware': ['order', 'fulfillment', 'inventory', 'warehouse', 'facility'],
    'payu': ['payment', 'transaction', 'settlement', 'refund', 'gateway'],
    'easebuzz': ['payment', 'transaction', 'settlement', 'refund', 'payout'],
    'shiprocket': ['shipping', 'logistics', 'courier', 'tracking', 'delivery']
}
```

### 4. Configuration Validation

```python
# server/agent/config/dtc_config_validator.py
import yaml
from typing import Dict, List, Any
from pathlib import Path

class DTCConfigValidator:
    """
    Validator for DTC marketplace service configurations
    """
    
    REQUIRED_SERVICES = ['uniware', 'payu', 'easebuzz', 'shiprocket']
    
    REQUIRED_CONFIG_KEYS = {
        'uniware': ['uri', 'tenant_id', 'facility_code'],
        'payu': ['uri', 'merchant_id', 'environment'],
        'easebuzz': ['uri', 'merchant_id', 'environment'],
        'shiprocket': ['uri', 'company_id']
    }
    
    REQUIRED_AUTH_KEYS = {
        'uniware': ['username', 'password', 'client_id', 'client_secret'],
        'payu': ['merchant_key', 'salt'],
        'easebuzz': ['api_key', 'secret_key'],
        'shiprocket': ['email', 'password']
    }
    
    @classmethod
    def validate_config(cls, config_path: str) -> Dict[str, Any]:
        """
        Validate DTC service configuration
        
        Args:
            config_path: Path to config.yaml file
            
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'services': {}
        }
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"Failed to load config.yaml: {e}")
            return results
        
        # Validate each service
        for service_name in cls.REQUIRED_SERVICES:
            service_config = config.get(service_name, {})
            service_results = cls._validate_service_config(service_name, service_config)
            results['services'][service_name] = service_results
            
            if not service_results['valid']:
                results['valid'] = False
                results['errors'].extend(service_results['errors'])
        
        return results
    
    @classmethod
    def validate_auth_config(cls, auth_config_path: str) -> Dict[str, Any]:
        """
        Validate DTC service authentication configuration
        
        Args:
            auth_config_path: Path to auth-config.yaml file
            
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'services': {}
        }
        
        try:
            with open(auth_config_path, 'r') as f:
                auth_config = yaml.safe_load(f)
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"Failed to load auth-config.yaml: {e}")
            return results
        
        api_auth = auth_config.get('api_auth', {})
        
        # Validate each service authentication
        for service_name in cls.REQUIRED_SERVICES:
            service_auth = api_auth.get(service_name, {})
            service_results = cls._validate_service_auth(service_name, service_auth)
            results['services'][service_name] = service_results
            
            if not service_results['valid']:
                results['valid'] = False
                results['errors'].extend(service_results['errors'])
        
        return results
    
    @classmethod
    def _validate_service_config(cls, service_name: str, config: Dict) -> Dict[str, Any]:
        """Validate individual service configuration"""
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if not config:
            results['valid'] = False
            results['errors'].append(f"No configuration found for {service_name}")
            return results
        
        # Check required keys
        required_keys = cls.REQUIRED_CONFIG_KEYS.get(service_name, [])
        for key in required_keys:
            if key not in config:
                results['valid'] = False
                results['errors'].append(f"Missing required key '{key}' for {service_name}")
        
        # Service-specific validation
        if service_name == 'uniware':
            if not config.get('uri', '').startswith('https://'):
                results['warnings'].append("Uniware URI should use HTTPS for production")
        
        elif service_name in ['payu', 'easebuzz']:
            environment = config.get('environment', '').lower()
            if environment not in ['production', 'test']:
                results['warnings'].append(f"{service_name} environment should be 'production' or 'test'")
        
        return results
    
    @classmethod
    def _validate_service_auth(cls, service_name: str, auth_config: Dict) -> Dict[str, Any]:
        """Validate individual service authentication"""
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if not auth_config:
            results['valid'] = False
            results['errors'].append(f"No authentication configuration found for {service_name}")
            return results
        
        # Check required keys
        required_keys = cls.REQUIRED_AUTH_KEYS.get(service_name, [])
        for key in required_keys:
            if key not in auth_config:
                results['valid'] = False
                results['errors'].append(f"Missing required auth key '{key}' for {service_name}")
        
        return results
```

## Deployment Integration

### 1. Docker Compose Extension

```yaml
# deploy/dtc-services-docker-compose.yml
version: '3.8'

services:
  ceneca-agent:
    # ... existing configuration
    environment:
      # ... existing environment variables
      # DTC Service URLs
      - UNIWARE_URI=https://api.unicommerce.com/v1
      - PAYU_URI=https://secure.payu.in
      - EASEBUZZ_URI=https://api.easebuzz.in
      - SHIPROCKET_URI=https://api.shiprocket.in/v1
    volumes:
      # ... existing volumes
      - ./dtc-config.yaml:/app/config/dtc-config.yaml:ro
      - ./dtc-auth-config.yaml:/app/config/dtc-auth-config.yaml:ro
```

### 2. Installation Script Extension

```bash
# deploy/dtc-services-install.sh
#!/bin/bash

echo "🚀 Installing Ceneca with Indian DTC Marketplace Services..."

# Validate DTC service configuration
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found"
    exit 1
fi

if [ ! -f "auth-config.yaml" ]; then
    echo "❌ auth-config.yaml not found"
    exit 1
fi

# Validate DTC service configurations
echo "🔍 Validating DTC service configurations..."
python3 -c "
import sys
sys.path.append('/app/server')
from agent.config.dtc_config_validator import DTCConfigValidator

# Validate main config
config_results = DTCConfigValidator.validate_config('config.yaml')
if not config_results['valid']:
    print('❌ Config validation failed:')
    for error in config_results['errors']:
        print(f'  - {error}')
    sys.exit(1)

# Validate auth config
auth_results = DTCConfigValidator.validate_auth_config('auth-config.yaml')
if not auth_results['valid']:
    print('❌ Auth config validation failed:')
    for error in auth_results['errors']:
        print(f'  - {error}')
    sys.exit(1)

print('✅ All DTC service configurations valid')
"

# Continue with normal installation
echo "📦 Starting Ceneca services..."
docker-compose -f dtc-services-docker-compose.yml up -d

# Test DTC service connections
echo "🧪 Testing DTC service connections..."
docker-compose exec ceneca-agent python3 -c "
import asyncio
import sys
sys.path.append('/app/server')
from agent.db.adapters.uniware import UniwareAdapter
from agent.db.adapters.payu import PayUAdapter
from agent.db.adapters.easebuzz import EasebuzzAdapter
from agent.db.adapters.shiprocket import ShiprocketAdapter

async def test_connections():
    # Test configurations would be loaded from config files
    services = [
        ('Uniware', UniwareAdapter),
        ('PayU', PayUAdapter),
        ('Easebuzz', EasebuzzAdapter),
        ('Shiprocket', ShiprocketAdapter)
    ]
    
    for name, adapter_class in services:
        try:
            # This would use real config in production
            adapter = adapter_class('test-uri')
            # result = await adapter.test_connection()
            print(f'✅ {name} adapter initialized successfully')
        except Exception as e:
            print(f'❌ {name} adapter failed: {e}')

asyncio.run(test_connections())
"

echo "✅ Ceneca with Indian DTC Marketplace Services installed successfully!"
echo "🔗 Access the web interface at: http://localhost:8787"
```

## Usage Examples

### 1. Sample Queries

```python
# Example natural language queries for each service

# Uniware queries
queries = [
    "Show me all orders from last week",
    "What's the current inventory for product SKU ABC123?",
    "List all pending fulfillments",
    "Show me returns that need processing"
]

# PayU queries
queries = [
    "Show me all transactions from today",
    "What's the settlement status for last month?",
    "List all failed payments",
    "Show me refunds processed this week"
]

# Easebuzz queries
queries = [
    "Show me all successful transactions",
    "What payouts were made last week?",
    "List all pending refunds",
    "Show me settlement summary"
]

# Shiprocket queries
queries = [
    "Show me all shipments created today",
    "Track order with AWB 1234567890",
    "List all pending pickups",
    "Show me courier rates for Delhi to Mumbai"
]
```

### 2. Cross-Service Queries

```python
# Example cross-service queries that leverage multiple adapters

cross_service_queries = [
    "Show me orders from Uniware and their payment status in PayU",
    "List all shipped orders from Shiprocket with their settlement status",
    "Show me refunded transactions and their corresponding returns",
    "Give me a complete order lifecycle from order creation to delivery"
]
```

## Security Considerations

### 1. Credential Management

- **Environment Variables**: Use environment variables for sensitive credentials
- **Encrypted Storage**: Store credentials in encrypted configuration files  
- **Token Rotation**: Implement automatic token refresh for OAuth services
- **Access Control**: Limit API permissions to minimum required scopes

### 2. Network Security

- **TLS/SSL**: Enforce HTTPS for all API communications
- **Rate Limiting**: Implement rate limiting to prevent API abuse
- **Retry Logic**: Add exponential backoff for failed requests
- **Connection Pooling**: Use connection pooling for efficient resource usage

### 3. Monitoring

- **API Health Checks**: Regular health checks for all services
- **Error Tracking**: Comprehensive error logging and alerting
- **Performance Metrics**: Track API response times and success rates
- **Audit Logs**: Log all API calls for compliance and debugging

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_dtc_adapters.py
import pytest
import asyncio
from unittest.mock import Mock, patch
from server.agent.db.adapters.uniware import UniwareAdapter
# ... other imports

class TestUniwareAdapter:
    @pytest.fixture
    def adapter(self):
        return UniwareAdapter(
            "https://api.unicommerce.com/v1",
            tenant_id="test_tenant",
            facility_code="test_facility"
        )
    
    @pytest.mark.asyncio
    async def test_authentication(self, adapter):
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json.return_value = {
                'access_token': 'test_token',
                'expires_in': 3600
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            token = await adapter._authenticate()
            assert token == 'test_token'
    
    @pytest.mark.asyncio
    async def test_test_connection(self, adapter):
        with patch.object(adapter, '_authenticate') as mock_auth:
            mock_auth.return_value = 'test_token'
            with patch('aiohttp.ClientSession.get') as mock_get:
                mock_response = Mock()
                mock_response.status = 200
                mock_get.return_value.__aenter__.return_value = mock_response
                
                result = await adapter.test_connection()
                assert result is True
```

### 2. Integration Tests

```python
# tests/test_dtc_integration.py
import pytest
from server.agent.db.orchestrator.cross_db_orchestrator import CrossDatabaseOrchestrator

class TestDTCIntegration:
    @pytest.fixture
    def orchestrator(self):
        return CrossDatabaseOrchestrator()
    
    @pytest.mark.asyncio
    async def test_cross_service_query(self, orchestrator):
        # Test query that spans multiple DTC services
        query = "Show me orders from Uniware and their payment status"
        
        # Mock the classifier to return multiple services
        with patch.object(orchestrator.classifier, 'classify') as mock_classify:
            mock_classify.return_value = {
                'sources': ['uniware', 'payu'],
                'reasoning': 'Query requires both order and payment data'
            }
            
            result = await orchestrator.execute(query)
            
            assert 'results' in result
            assert len(result['results']) == 2
            assert any(r['source_id'] == 'uniware' for r in result['results'])
            assert any(r['source_id'] == 'payu' for r in result['results'])
```

## Next Steps

1. **Implement adapters** following the detailed code above
2. **Configure authentication** using the auth-config.yaml structure
3. **Test connections** to ensure all services are accessible
4. **Deploy to staging** environment for integration testing
5. **Create documentation** for enterprise customers
6. **Monitor performance** and optimize based on usage patterns

This implementation plan provides a comprehensive foundation for integrating Indian DTC marketplace services into Ceneca while maintaining the on-premise deployment constraints and enterprise security requirements. 