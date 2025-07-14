"""
PayU Adapter for querying payment gateway data
Integrates with Ceneca's AI analytics system
"""
import asyncio
import aiohttp
import hashlib
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

class PayUAdapter(DBAdapter):
    """
    Adapter for PayU payment gateway platform
    
    This adapter handles hash-based authentication and provides comprehensive
    payment, settlement, and refund data access.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize PayU adapter
        
        Args:
            conn_uri: PayU API base URL
            **kwargs: Additional arguments including:
                merchant_id: PayU merchant ID
                environment: production or test
                auth: Authentication configuration dict
        """
        super().__init__(conn_uri)
        self.base_url = conn_uri.rstrip("/")
        self.merchant_id = kwargs.get('merchant_id')
        self.environment = kwargs.get('environment', 'production')
        self.auth_config = kwargs.get('auth', {})
        
        # Session management
        self.session = None
        
    async def _get_session(self):
        """Initialize aiohttp session if not exists"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=15,
                limit_per_host=15,
                keepalive_timeout=30
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    def _generate_hash(self, params: Dict) -> str:
        """Generate PayU hash for authentication"""
        merchant_key = self.auth_config.get('merchant_key')
        salt = self.auth_config.get('salt')
        
        # Create hash string based on PayU documentation
        # For get_payment_status: key|command|var1|salt
        hash_string = f"{merchant_key}|{params.get('command')}|{params.get('var1', '')}|{salt}"
        return hashlib.sha512(hash_string.encode()).hexdigest()
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to PayU API query"""
        schema_chunks = kwargs.get('schema_chunks', [])
        
        # Define PayU API endpoints
        api_endpoints = {
            'transactions': {
                'endpoint': '/payment/op/getPaymentStatus',
                'command': 'get_payment_status',
                'description': 'Payment transactions - list, search, and get transaction details'
            },
            'settlements': {
                'endpoint': '/payment/op/getSettlementStatus',
                'command': 'get_settlement_status',
                'description': 'Settlement information and status'
            },
            'refunds': {
                'endpoint': '/payment/op/getRefundDetails',
                'command': 'get_refund_details',
                'description': 'Refund management and processing'
            },
            'reports': {
                'endpoint': '/payment/op/getPaymentStatus',
                'command': 'get_payment_status',
                'description': 'Payment reports and analytics'
            }
        }
        
        # Simple keyword-based routing
        query_type = 'transactions'  # Default
        
        prompt_lower = nl_prompt.lower()
        if any(word in prompt_lower for word in ['settlement', 'payout', 'settle']):
            query_type = 'settlements'
        elif any(word in prompt_lower for word in ['refund', 'chargeback', 'reversal']):
            query_type = 'refunds'
        elif any(word in prompt_lower for word in ['report', 'analytics', 'summary']):
            query_type = 'reports'
        
        endpoint_config = api_endpoints[query_type]
        
        return {
            'type': 'payu_api',
            'endpoint': endpoint_config['endpoint'],
            'command': endpoint_config['command'],
            'method': 'POST',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt, endpoint_config['command']),
            'description': endpoint_config['description']
        }
    
    def _extract_query_params(self, nl_prompt: str, command: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {
            'command': command,
            'var1': self.merchant_id
        }
        
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
        if 'success' in prompt_lower or 'successful' in prompt_lower:
            params['status'] = 'success'
        elif 'failed' in prompt_lower or 'failure' in prompt_lower:
            params['status'] = 'failure'
        elif 'pending' in prompt_lower:
            params['status'] = 'pending'
            
        return params
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute PayU API query"""
        try:
            session = await self._get_session()
            
            params = query.get('params', {})
            
            # Generate hash for authentication
            params['hash'] = self._generate_hash(params)
            params['key'] = self.auth_config.get('merchant_key')
            
            url = f"{self.base_url}{query['endpoint']}"
            
            logger.info(f"Executing PayU API call: POST {url}")
            logger.debug(f"Command: {params.get('command')}")
            
            async with session.post(
                url=url,
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check PayU response status
                    if data.get('status') == 1:  # PayU success status
                        # Normalize response based on endpoint category
                        category = query.get('category', 'unknown')
                        if category == 'transactions':
                            return self._normalize_transactions(data)
                        elif category == 'settlements':
                            return self._normalize_settlements(data)
                        elif category == 'refunds':
                            return self._normalize_refunds(data)
                        else:
                            # Return raw data if no specific normalizer
                            return [data] if isinstance(data, dict) else data
                    else:
                        # PayU API returned error
                        error_msg = data.get('msg', 'Unknown PayU error')
                        logger.error(f"PayU API error: {error_msg}")
                        return []
                else:
                    error_text = await response.text()
                    logger.error(f"PayU HTTP error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"PayU query execution error: {e}")
            return []
    
    def _normalize_transactions(self, data: Dict) -> List[Dict]:
        """Normalize transaction data from PayU API response"""
        # PayU returns transaction details in various formats
        transactions = []
        
        # Handle single transaction response
        if 'transaction_details' in data:
            transaction_details = data['transaction_details']
            if isinstance(transaction_details, dict):
                # Single transaction
                transactions = [transaction_details]
            elif isinstance(transaction_details, list):
                # Multiple transactions
                transactions = transaction_details
        
        normalized = []
        for transaction in transactions:
            normalized.append({
                'id': transaction.get('txnid'),
                'payment_id': transaction.get('paymentId', transaction.get('mihpayid')),
                'amount': float(transaction.get('amount', 0)),
                'status': transaction.get('status'),
                'payment_method': transaction.get('mode'),
                'bank_ref_num': transaction.get('bank_ref_num'),
                'created_at': transaction.get('addedon'),
                'updated_at': transaction.get('updated_at'),
                'customer_email': transaction.get('email'),
                'customer_phone': transaction.get('phone'),
                'product_info': transaction.get('productinfo'),
                'card_num': transaction.get('cardnum'),
                'issuing_bank': transaction.get('issuing_bank'),
                'type': 'transaction',
                'source': 'payu'
            })
        
        return normalized
    
    def _normalize_settlements(self, data: Dict) -> List[Dict]:
        """Normalize settlement data from PayU API response"""
        settlements = data.get('settlement_details', data.get('settlements', []))
        if isinstance(settlements, dict):
            settlements = [settlements]
            
        normalized = []
        for settlement in settlements:
            normalized.append({
                'id': settlement.get('settlement_id'),
                'amount': float(settlement.get('amount', 0)),
                'status': settlement.get('status'),
                'settlement_date': settlement.get('settlement_date'),
                'utr_number': settlement.get('utr_number'),
                'bank_name': settlement.get('bank_name'),
                'account_no': settlement.get('account_no'),
                'created_at': settlement.get('created_at'),
                'type': 'settlement',
                'source': 'payu'
            })
        
        return normalized
    
    def _normalize_refunds(self, data: Dict) -> List[Dict]:
        """Normalize refund data from PayU API response"""
        refunds = data.get('refund_details', data.get('refunds', []))
        if isinstance(refunds, dict):
            refunds = [refunds]
            
        normalized = []
        for refund in refunds:
            normalized.append({
                'id': refund.get('refund_id'),
                'transaction_id': refund.get('txnid'),
                'payment_id': refund.get('mihpayid'),
                'amount': float(refund.get('amount', 0)),
                'status': refund.get('status'),
                'refund_date': refund.get('refund_date'),
                'reason': refund.get('reason'),
                'bank_ref_num': refund.get('bank_ref_num'),
                'created_at': refund.get('created_at'),
                'type': 'refund',
                'source': 'payu'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Dynamically introspect PayU schema by calling actual APIs"""
        schema_docs = []
        
        try:
            session = await self._get_session()
            
            # Test different PayU API endpoints to discover schema
            endpoints_to_test = [
                {
                    'id': 'payu_transactions',
                    'name': 'PayU Transactions',
                    'endpoint': '/payment/op/getPaymentStatus',
                    'command': 'get_payment_status',
                    'description': 'Payment transaction information and status'
                },
                {
                    'id': 'payu_settlements',
                    'name': 'PayU Settlements', 
                    'endpoint': '/payment/op/getSettlementStatus',
                    'command': 'get_settlement_status',
                    'description': 'Settlement and payout information'
                },
                {
                    'id': 'payu_refunds',
                    'name': 'PayU Refunds',
                    'endpoint': '/payment/op/getRefundDetails', 
                    'command': 'get_refund_details',
                    'description': 'Refund and chargeback information'
                }
            ]
            
            for endpoint_info in endpoints_to_test:
                try:
                    # Make a test API call to discover response structure
                    params = {
                        'command': endpoint_info['command'],
                        'var1': self.merchant_id or 'test_merchant'
                    }
                    params['hash'] = self._generate_hash(params)
                    params['key'] = self.auth_config.get('merchant_key', 'test_key')
                    
                    async with session.post(
                        f"{self.base_url}{endpoint_info['endpoint']}",
                        data=params,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'}
                    ) as response:
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                
                                # Extract actual field structure from API response
                                fields = self._extract_fields_from_response(data, endpoint_info['command'])
                                
                                content = f"""{endpoint_info['name']}: {endpoint_info['description']}
                                
Available Fields: {', '.join(fields)}

API Endpoint: {endpoint_info['endpoint']}
Command: {endpoint_info['command']}
Response Format: JSON
Authentication: Hash-based (key + command + var1 + salt)

Use for: {endpoint_info['description']}
Example queries: "Show {endpoint_info['name'].lower()}", "Recent {endpoint_info['name'].lower()}", "{endpoint_info['name']} by status"

Note: This schema was discovered by calling the actual PayU API at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                                
                                schema_docs.append({
                                    'id': endpoint_info['id'],
                                    'content': content
                                })
                                
                                logger.info(f"Successfully introspected PayU {endpoint_info['name']} schema")
                                
                            except json.JSONDecodeError:
                                # Handle non-JSON responses (like HTML error pages)
                                logger.warning(f"PayU {endpoint_info['name']} returned non-JSON response")
                                
                                # Create basic schema from documentation
                                content = f"""{endpoint_info['name']}: {endpoint_info['description']}
                                
API Endpoint: {endpoint_info['endpoint']}
Command: {endpoint_info['command']}
Status: API endpoint exists but returned non-JSON response
Authentication: Hash-based (key + command + var1 + salt)

Note: Schema structure needs merchant account for full introspection. This was discovered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                                
                                schema_docs.append({
                                    'id': endpoint_info['id'],
                                    'content': content
                                })
                        else:
                            logger.warning(f"PayU {endpoint_info['name']} API returned {response.status}")
                            
                except Exception as e:
                    logger.warning(f"Error introspecting PayU {endpoint_info['name']}: {e}")
                    
            # If no schemas were discovered, provide basic API structure
            if not schema_docs:
                schema_docs.append({
                    'id': 'payu_api_structure',
                    'content': f"""PayU API Structure: Payment gateway endpoints
                    
Base URL: {self.base_url}
Authentication: Hash-based (SHA512)
Available Endpoints:
- /payment/op/getPaymentStatus (transactions)
- /payment/op/getSettlementStatus (settlements)  
- /payment/op/getRefundDetails (refunds)

Hash Format: merchant_key|command|var1|salt
Required Parameters: key, command, var1, hash

Note: Full schema introspection requires valid merchant credentials. Discovered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                })
                
        except Exception as e:
            logger.error(f"Error during PayU schema introspection: {e}")
            # Fallback to basic structure
            schema_docs.append({
                'id': 'payu_error_fallback',
                'content': f"""PayU API (Connection Error): Payment gateway endpoints
                
Error: {str(e)}
Base URL: {self.base_url}
Status: Unable to connect for schema introspection

Note: This indicates a connection issue. Check credentials and network connectivity."""
            })
            
        return schema_docs
    
    def _extract_fields_from_response(self, data: Dict, command: str) -> List[str]:
        """Extract field names from actual PayU API response"""
        fields = set()
        
        def extract_keys(obj, prefix=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    field_name = f"{prefix}{key}" if prefix else key
                    fields.add(field_name)
                    if isinstance(value, (dict, list)) and len(str(value)) < 1000:  # Avoid deep recursion
                        extract_keys(value, f"{field_name}.")
            elif isinstance(obj, list) and obj:
                # Sample first item in list
                extract_keys(obj[0], prefix)
        
        # Extract fields from the response
        extract_keys(data)
        
        # Add common PayU fields based on command type
        if command == 'get_payment_status':
            fields.update(['txnid', 'amount', 'status', 'email', 'phone', 'productinfo', 'mode'])
        elif command == 'get_settlement_status':
            fields.update(['settlement_id', 'amount', 'status', 'settlement_date', 'utr_number'])
        elif command == 'get_refund_details':
            fields.update(['refund_id', 'txnid', 'amount', 'status', 'refund_date'])
            
        return sorted(list(fields))
    
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
            params['key'] = self.auth_config.get('merchant_key')
            
            async with session.post(
                f"{self.base_url}/payment/op/getPaymentStatus",
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                success = response.status == 200
                if success:
                    # Check if PayU returned a valid response
                    try:
                        data = await response.json()
                        # PayU returns status=1 for success, status=0 for error
                        if data.get('status') == 0 and 'hash' in data.get('msg', '').lower():
                            logger.error("PayU connection test failed: Invalid hash/authentication")
                            return False
                        logger.info("PayU connection test successful")
                    except:
                        logger.warning("PayU connection test: received non-JSON response")
                else:
                    error_text = await response.text()
                    logger.error(f"PayU connection test failed: {response.status} - {error_text}")
                return success
                
        except Exception as e:
            logger.error(f"PayU connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None 