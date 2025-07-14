"""
Shiprocket Adapter for querying shipping and logistics data
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

class ShiprocketAdapter(DBAdapter):
    """
    Adapter for Shiprocket shipping and logistics platform
    
    This adapter handles bearer token authentication and provides comprehensive
    shipping, tracking, pickup, and courier data access.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize Shiprocket adapter
        
        Args:
            conn_uri: Shiprocket API base URL
            **kwargs: Additional arguments including:
                company_id: Shiprocket company ID
                auth: Authentication configuration dict
        """
        super().__init__(conn_uri)
        self.base_url = conn_uri.rstrip("/")
        self.company_id = kwargs.get('company_id')
        self.auth_config = kwargs.get('auth', {})
        
        # Session and authentication management
        self.session = None
        self.auth_token = None
        self.token_expires_at = None
        
        # Credentials file for storing tokens
        self.credentials_file = os.path.join(
            str(Path.home()), 
            ".data-connector", 
            "shiprocket_credentials.json"
        )
        
        # Load existing credentials if available
        self._load_credentials()
        
    def _load_credentials(self) -> bool:
        """Load stored Shiprocket credentials if available"""
        try:
            if not os.path.exists(self.credentials_file):
                logger.info(f"Shiprocket credentials file not found: {self.credentials_file}")
                return False
                
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
                
            if 'auth_token' in credentials:
                self.auth_token = credentials.get('auth_token')
                expires_str = credentials.get('expires_at')
                
                if expires_str:
                    self.token_expires_at = datetime.fromisoformat(expires_str)
                    
                logger.info("Loaded Shiprocket credentials")
                return True
            else:
                logger.warning("No auth token found in credentials file")
                return False
                
        except Exception as e:
            logger.error(f"Error loading Shiprocket credentials: {str(e)}")
            return False
    
    def _save_credentials(self, auth_token: str):
        """Save Shiprocket credentials to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
            
            # Shiprocket tokens expire in 24 hours
            expires_at = datetime.now() + timedelta(hours=23)
            
            credentials = {
                'auth_token': auth_token,
                'expires_at': expires_at.isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
                
            logger.info("Saved Shiprocket credentials")
            
        except Exception as e:
            logger.error(f"Error saving Shiprocket credentials: {str(e)}")
    
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=8,
                limit_per_host=8,
                keepalive_timeout=30
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=40)  # Shiprocket can be slower
            )
        return self.session
    
    async def _authenticate(self) -> str:
        """Authenticate with Shiprocket API"""
        # Check if we have a valid cached token
        if (self.auth_token and self.token_expires_at and 
            self.token_expires_at > datetime.now()):
            return self.auth_token
            
        session = await self._get_session()
        
        auth_data = {
            'email': self.auth_config.get('email'),
            'password': self.auth_config.get('password')
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
                    
                    # Update expiry time (Shiprocket tokens expire in 24 hours)
                    self.token_expires_at = datetime.now() + timedelta(hours=23)
                    
                    # Save credentials
                    self._save_credentials(self.auth_token)
                    
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
        schema_chunks = kwargs.get('schema_chunks', [])
        
        # Define Shiprocket API endpoints
        api_endpoints = {
            'orders': {
                'endpoint': '/external/orders',
                'description': 'Shipping orders - list, search, and get order details'
            },
            'tracking': {
                'endpoint': '/external/courier/track',
                'description': 'Shipment tracking and status updates'
            },
            'pickup': {
                'endpoint': '/external/courier/assign/pickup',
                'description': 'Pickup scheduling and management'
            },
            'couriers': {
                'endpoint': '/external/courier/serviceability',
                'description': 'Courier partners and rate calculation'
            },
            'ndr': {
                'endpoint': '/external/ndr',
                'description': 'Non-Delivery Report management'
            }
        }
        
        # Simple keyword-based routing
        query_type = 'orders'  # Default
        
        prompt_lower = nl_prompt.lower()
        if any(word in prompt_lower for word in ['track', 'tracking', 'status', 'delivery']):
            query_type = 'tracking'
        elif any(word in prompt_lower for word in ['pickup', 'collect', 'schedule']):
            query_type = 'pickup'
        elif any(word in prompt_lower for word in ['courier', 'partner', 'rate', 'cost', 'service']):
            query_type = 'couriers'
        elif any(word in prompt_lower for word in ['ndr', 'non-delivery', 'failed delivery', 'rto']):
            query_type = 'ndr'
        
        endpoint_config = api_endpoints[query_type]
        
        return {
            'type': 'shiprocket_api',
            'endpoint': endpoint_config['endpoint'],
            'method': 'GET',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt),
            'description': endpoint_config['description']
        }
    
    def _extract_query_params(self, nl_prompt: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {}
        
        # Extract date ranges
        prompt_lower = nl_prompt.lower()
        
        if 'last week' in prompt_lower:
            params['from_date'] = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            params['to_date'] = datetime.now().strftime('%Y-%m-%d')
        elif 'last month' in prompt_lower:
            params['from_date'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            params['to_date'] = datetime.now().strftime('%Y-%m-%d')
        elif 'today' in prompt_lower:
            params['from_date'] = datetime.now().strftime('%Y-%m-%d')
            params['to_date'] = datetime.now().strftime('%Y-%m-%d')
        elif 'yesterday' in prompt_lower:
            yesterday = datetime.now() - timedelta(days=1)
            params['from_date'] = yesterday.strftime('%Y-%m-%d')
            params['to_date'] = yesterday.strftime('%Y-%m-%d')
        
        # Extract status filters
        if 'pending' in prompt_lower:
            params['status'] = 'PENDING'
        elif 'shipped' in prompt_lower or 'in transit' in prompt_lower:
            params['status'] = 'SHIPPED'
        elif 'delivered' in prompt_lower:
            params['status'] = 'DELIVERED'
        elif 'cancelled' in prompt_lower or 'canceled' in prompt_lower:
            params['status'] = 'CANCELLED'
        
        # Extract specific tracking numbers or AWB codes
        import re
        awb_match = re.search(r'\b([A-Z0-9]{10,})\b', nl_prompt.upper())
        if awb_match:
            params['awb_code'] = awb_match.group(1)
        
        # Limit results for performance
        params['per_page'] = 100
            
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
            
            logger.info(f"Executing Shiprocket API call: {method} {url}")
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
                    elif category == 'tracking':
                        return self._normalize_tracking(data)
                    elif category == 'pickup':
                        return self._normalize_pickup(data)
                    elif category == 'couriers':
                        return self._normalize_couriers(data)
                    elif category == 'ndr':
                        return self._normalize_ndr(data)
                    else:
                        # Return raw data if no specific normalizer
                        return [data] if isinstance(data, dict) else data
                        
                elif response.status == 401:
                    # Token expired, clear it and retry once
                    self.auth_token = None
                    self.token_expires_at = None
                    logger.warning("Shiprocket token expired, retrying authentication")
                    raise Exception("Authentication token expired")
                else:
                    error_text = await response.text()
                    logger.error(f"Shiprocket API error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Shiprocket query execution error: {e}")
            return []
    
    def _normalize_orders(self, data: Dict) -> List[Dict]:
        """Normalize order data from Shiprocket API response"""
        orders = data.get('data', [])
        normalized = []
        
        for order in orders:
            normalized.append({
                'id': order.get('id'),
                'order_id': order.get('order_id'),
                'channel_id': order.get('channel_id'),
                'channel_name': order.get('channel_name'),
                'status': order.get('status'),
                'total_amount': order.get('total', order.get('total_amount')),
                'created_at': order.get('created_at'),
                'updated_at': order.get('updated_at'),
                'awb_code': order.get('awb_code'),
                'courier_partner': order.get('courier_name'),
                'customer_name': order.get('customer_name'),
                'customer_phone': order.get('customer_phone'),
                'customer_email': order.get('customer_email'),
                'shipping_address': order.get('shipping_address'),
                'billing_address': order.get('billing_address'),
                'weight': order.get('weight'),
                'type': 'order',
                'source': 'shiprocket'
            })
        
        return normalized
    
    def _normalize_tracking(self, data: Dict) -> List[Dict]:
        """Normalize tracking data from Shiprocket API response"""
        tracking_data = data.get('tracking_data', data.get('data', []))
        if isinstance(tracking_data, dict):
            tracking_data = [tracking_data]
            
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
                'expected_delivery': track.get('edd'),
                'tracking_url': track.get('tracking_url'),
                'type': 'tracking',
                'source': 'shiprocket'
            })
        
        return normalized
    
    def _normalize_pickup(self, data: Dict) -> List[Dict]:
        """Normalize pickup data from Shiprocket API response"""
        pickups = data.get('data', data.get('pickup_data', []))
        if isinstance(pickups, dict):
            pickups = [pickups]
            
        normalized = []
        for pickup in pickups:
            normalized.append({
                'id': pickup.get('id'),
                'pickup_token': pickup.get('pickup_token'),
                'pickup_date': pickup.get('pickup_date'),
                'pickup_time': pickup.get('pickup_time'),
                'status': pickup.get('status'),
                'courier_partner': pickup.get('courier_name'),
                'address': pickup.get('address'),
                'pincode': pickup.get('pincode'),
                'contact_person': pickup.get('contact_person'),
                'phone': pickup.get('phone'),
                'type': 'pickup',
                'source': 'shiprocket'
            })
        
        return normalized
    
    def _normalize_couriers(self, data: Dict) -> List[Dict]:
        """Normalize courier data from Shiprocket API response"""
        couriers = data.get('data', [])
        normalized = []
        
        for courier in couriers:
            normalized.append({
                'id': courier.get('id'),
                'courier_name': courier.get('courier_name'),
                'rate': courier.get('rate'),
                'estimated_delivery_days': courier.get('etd'),
                'cod_available': courier.get('cod'),
                'pickup_available': courier.get('pickup_available'),
                'rating': courier.get('rating'),
                'freight_charge': courier.get('freight_charge'),
                'cod_charges': courier.get('cod_charges'),
                'type': 'courier',
                'source': 'shiprocket'
            })
        
        return normalized
    
    def _normalize_ndr(self, data: Dict) -> List[Dict]:
        """Normalize NDR (Non-Delivery Report) data from Shiprocket API response"""
        ndr_data = data.get('data', [])
        normalized = []
        
        for ndr in ndr_data:
            normalized.append({
                'id': ndr.get('id'),
                'awb_code': ndr.get('awb_code'),
                'order_id': ndr.get('order_id'),
                'ndr_reason': ndr.get('ndr_reason'),
                'ndr_date': ndr.get('ndr_date'),
                'status': ndr.get('status'),
                'courier_name': ndr.get('courier_name'),
                'customer_phone': ndr.get('customer_phone'),
                'rescheduled_date': ndr.get('rescheduled_date'),
                'type': 'ndr',
                'source': 'shiprocket'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return Shiprocket schema information for the LLM"""
        return [
            {
                'id': 'shiprocket_orders',
                'content': '''Shiprocket Orders: Contains shipping order information
                Fields: id, order_id, channel_id, channel_name, status (PENDING/SHIPPED/DELIVERED/CANCELLED), 
                total_amount, created_at, updated_at, awb_code, courier_partner, customer_name, customer_phone, 
                customer_email, shipping_address, billing_address, weight
                
                Use for: Order tracking, shipping analysis, customer orders, courier performance
                Example queries: "Show orders shipped today", "Orders by courier partner", "Pending shipments"'''
            },
            {
                'id': 'shiprocket_tracking',
                'content': '''Shiprocket Tracking: Contains shipment tracking information
                Fields: id, awb_code, courier_name, current_status, delivered_date, destination, origin, 
                last_update, expected_delivery, tracking_url
                
                Use for: Shipment tracking, delivery status, logistics analysis
                Example queries: "Track AWB 1234567890", "Delivered shipments today", "Delayed deliveries"'''
            },
            {
                'id': 'shiprocket_pickup',
                'content': '''Shiprocket Pickup: Contains pickup scheduling information
                Fields: id, pickup_token, pickup_date, pickup_time, status, courier_partner, address, 
                pincode, contact_person, phone
                
                Use for: Pickup management, scheduling analysis, courier coordination
                Example queries: "Scheduled pickups today", "Pickup status", "Pickups by courier"'''
            },
            {
                'id': 'shiprocket_couriers',
                'content': '''Shiprocket Couriers: Contains courier partner information and rates
                Fields: id, courier_name, rate, estimated_delivery_days, cod_available, pickup_available, 
                rating, freight_charge, cod_charges
                
                Use for: Courier comparison, rate analysis, service availability
                Example queries: "Cheapest courier rates", "COD enabled couriers", "Fastest delivery options"'''
            },
            {
                'id': 'shiprocket_ndr',
                'content': '''Shiprocket NDR: Contains Non-Delivery Report information
                Fields: id, awb_code, order_id, ndr_reason, ndr_date, status, courier_name, 
                customer_phone, rescheduled_date
                
                Use for: Failed delivery analysis, customer service, logistics optimization
                Example queries: "NDR reports today", "Failed deliveries by reason", "Rescheduled deliveries"'''
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test Shiprocket connection"""
        try:
            # Try to authenticate
            auth_token = await self._authenticate()
            if not auth_token:
                return False
                
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with a simple API call
            async with session.get(
                f"{self.base_url}/external/orders?per_page=1",
                headers=headers
            ) as response:
                success = response.status == 200
                if success:
                    logger.info("Shiprocket connection test successful")
                else:
                    error_text = await response.text()
                    logger.error(f"Shiprocket connection test failed: {response.status} - {error_text}")
                return success
                
        except Exception as e:
            logger.error(f"Shiprocket connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None 