"""
Easebuzz Adapter for querying payment gateway data
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

class EasebuzzAdapter(DBAdapter):
    """
    Adapter for Easebuzz payment gateway platform
    
    This adapter handles API key authentication and provides comprehensive
    payment, settlement, refund, and payout data access.
    """
    
    def __init__(self, conn_uri: str, **kwargs):
        """
        Initialize Easebuzz adapter
        
        Args:
            conn_uri: Easebuzz API base URL
            **kwargs: Additional arguments including:
                merchant_id: Easebuzz merchant ID
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
                limit=12,
                limit_per_host=12,
                keepalive_timeout=30
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    def _generate_hash(self, params: Dict) -> str:
        """Generate Easebuzz hash for authentication"""
        secret_key = self.auth_config.get('secret_key')
        
        # Create hash string based on Easebuzz documentation
        # For transaction queries: merchant_id|transaction_id|amount|secret_key
        merchant_id = params.get('merchant_id', self.merchant_id)
        transaction_id = params.get('transaction_id', '')
        amount = params.get('amount', '')
        
        hash_string = f"{merchant_id}|{transaction_id}|{amount}|{secret_key}"
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to Easebuzz API query"""
        schema_chunks = kwargs.get('schema_chunks', [])
        
        # Define Easebuzz API endpoints
        api_endpoints = {
            'transactions': {
                'endpoint': '/v1/payment/status',
                'description': 'Payment transactions - list, search, and get transaction details'
            },
            'settlements': {
                'endpoint': '/v1/settlements',
                'description': 'Settlement information and status'
            },
            'refunds': {
                'endpoint': '/v1/refunds',
                'description': 'Refund management and processing'
            },
            'payouts': {
                'endpoint': '/v1/payouts',
                'description': 'Payout management via InstaCollect'
            }
        }
        
        # Simple keyword-based routing
        query_type = 'transactions'  # Default
        
        prompt_lower = nl_prompt.lower()
        if any(word in prompt_lower for word in ['settlement', 'payout', 'settle']):
            query_type = 'settlements'
        elif any(word in prompt_lower for word in ['refund', 'chargeback', 'reversal']):
            query_type = 'refunds'
        elif any(word in prompt_lower for word in ['payout', 'instacollect', 'transfer']):
            query_type = 'payouts'
        
        endpoint_config = api_endpoints[query_type]
        
        return {
            'type': 'easebuzz_api',
            'endpoint': endpoint_config['endpoint'],
            'method': 'POST',
            'category': query_type,
            'params': self._extract_query_params(nl_prompt),
            'description': endpoint_config['description']
        }
    
    def _extract_query_params(self, nl_prompt: str) -> Dict:
        """Extract query parameters from natural language"""
        params = {
            'merchant_id': self.merchant_id
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
            params['status'] = 'failed'
        elif 'pending' in prompt_lower:
            params['status'] = 'pending'
            
        return params
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute Easebuzz API query"""
        try:
            session = await self._get_session()
            
            params = query.get('params', {})
            
            # Generate hash for authentication
            params['hash'] = self._generate_hash(params)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {self.auth_config.get('api_key')}"
            }
            
            url = f"{self.base_url}{query['endpoint']}"
            
            logger.info(f"Executing Easebuzz API call: POST {url}")
            logger.debug(f"Params: {params}")
            
            async with session.post(
                url=url,
                json=params,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check Easebuzz response status
                    if data.get('status') == 'success' or data.get('status') == 1:
                        # Normalize response based on endpoint category
                        category = query.get('category', 'unknown')
                        if category == 'transactions':
                            return self._normalize_transactions(data)
                        elif category == 'settlements':
                            return self._normalize_settlements(data)
                        elif category == 'refunds':
                            return self._normalize_refunds(data)
                        elif category == 'payouts':
                            return self._normalize_payouts(data)
                        else:
                            # Return raw data if no specific normalizer
                            return [data] if isinstance(data, dict) else data
                    else:
                        # Easebuzz API returned error
                        error_msg = data.get('message', data.get('msg', 'Unknown Easebuzz error'))
                        logger.error(f"Easebuzz API error: {error_msg}")
                        return []
                else:
                    error_text = await response.text()
                    logger.error(f"Easebuzz HTTP error: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Easebuzz query execution error: {e}")
            return []
    
    def _normalize_transactions(self, data: Dict) -> List[Dict]:
        """Normalize transaction data from Easebuzz API response"""
        transactions = data.get('data', data.get('transactions', []))
        if isinstance(transactions, dict):
            transactions = [transactions]
            
        normalized = []
        for transaction in transactions:
            normalized.append({
                'id': transaction.get('transaction_id'),
                'payment_id': transaction.get('payment_id'),
                'amount': float(transaction.get('amount', 0)),
                'status': transaction.get('status'),
                'payment_method': transaction.get('payment_method'),
                'bank_ref_num': transaction.get('bank_ref_num'),
                'created_at': transaction.get('created_at'),
                'updated_at': transaction.get('updated_at'),
                'customer_email': transaction.get('customer_email', transaction.get('email')),
                'customer_phone': transaction.get('customer_phone', transaction.get('phone')),
                'product_info': transaction.get('product_info'),
                'issuing_bank': transaction.get('issuing_bank'),
                'pg_type': transaction.get('pg_type'),
                'type': 'transaction',
                'source': 'easebuzz'
            })
        
        return normalized
    
    def _normalize_settlements(self, data: Dict) -> List[Dict]:
        """Normalize settlement data from Easebuzz API response"""
        settlements = data.get('data', data.get('settlements', []))
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
                'source': 'easebuzz'
            })
        
        return normalized
    
    def _normalize_refunds(self, data: Dict) -> List[Dict]:
        """Normalize refund data from Easebuzz API response"""
        refunds = data.get('data', data.get('refunds', []))
        if isinstance(refunds, dict):
            refunds = [refunds]
            
        normalized = []
        for refund in refunds:
            normalized.append({
                'id': refund.get('refund_id'),
                'transaction_id': refund.get('transaction_id'),
                'payment_id': refund.get('payment_id'),
                'amount': float(refund.get('amount', 0)),
                'status': refund.get('status'),
                'refund_date': refund.get('refund_date'),
                'reason': refund.get('reason'),
                'bank_ref_num': refund.get('bank_ref_num'),
                'created_at': refund.get('created_at'),
                'type': 'refund',
                'source': 'easebuzz'
            })
        
        return normalized
    
    def _normalize_payouts(self, data: Dict) -> List[Dict]:
        """Normalize payout data from Easebuzz API response"""
        payouts = data.get('data', data.get('payouts', []))
        if isinstance(payouts, dict):
            payouts = [payouts]
            
        normalized = []
        for payout in payouts:
            normalized.append({
                'id': payout.get('payout_id'),
                'beneficiary_name': payout.get('beneficiary_name'),
                'account_number': payout.get('account_number'),
                'ifsc_code': payout.get('ifsc_code'),
                'amount': float(payout.get('amount', 0)),
                'status': payout.get('status'),
                'payout_date': payout.get('payout_date'),
                'utr_number': payout.get('utr_number'),
                'bank_name': payout.get('bank_name'),
                'created_at': payout.get('created_at'),
                'type': 'payout',
                'source': 'easebuzz'
            })
        
        return normalized
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Dynamically introspect Easebuzz schema by calling actual APIs"""
        schema_docs = []
        
        try:
            session = await self._get_session()
            
            # Test different Easebuzz API endpoints to discover schema
            endpoints_to_test = [
                {
                    'id': 'easebuzz_transactions',
                    'name': 'Easebuzz Transactions',
                    'endpoint': '/v1/payment/status',
                    'description': 'Payment transaction information and status'
                },
                {
                    'id': 'easebuzz_settlements',
                    'name': 'Easebuzz Settlements',
                    'endpoint': '/v1/settlements',
                    'description': 'Settlement and payout information'
                },
                {
                    'id': 'easebuzz_refunds',
                    'name': 'Easebuzz Refunds',
                    'endpoint': '/v1/refunds',
                    'description': 'Refund and chargeback information'
                },
                {
                    'id': 'easebuzz_payouts',
                    'name': 'Easebuzz Payouts',
                    'endpoint': '/v1/payouts',
                    'description': 'Payout and transfer information via InstaCollect'
                }
            ]
            
            for endpoint_info in endpoints_to_test:
                try:
                    # Make a test API call to discover response structure
                    params = {
                        'merchant_id': self.merchant_id or 'test_merchant'
                    }
                    params['hash'] = self._generate_hash(params)
                    
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f"Bearer {self.auth_config.get('api_key', 'test_key')}"
                    }
                    
                    async with session.post(
                        f"{self.base_url}{endpoint_info['endpoint']}",
                        json=params,
                        headers=headers
                    ) as response:
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                
                                # Extract actual field structure from API response
                                fields = self._extract_fields_from_response(data, endpoint_info['endpoint'])
                                
                                content = f"""{endpoint_info['name']}: {endpoint_info['description']}
                                
Available Fields: {', '.join(fields)}

API Endpoint: {endpoint_info['endpoint']}
Method: POST
Response Format: JSON
Authentication: Bearer Token + Hash
Merchant ID: {self.merchant_id}

Use for: {endpoint_info['description']}
Example queries: "Show {endpoint_info['name'].lower()}", "Recent {endpoint_info['name'].lower()}", "{endpoint_info['name']} by status"

Note: This schema was discovered by calling the actual Easebuzz API at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                                
                                schema_docs.append({
                                    'id': endpoint_info['id'],
                                    'content': content
                                })
                                
                                logger.info(f"Successfully introspected Easebuzz {endpoint_info['name']} schema")
                                
                            except json.JSONDecodeError:
                                logger.warning(f"Easebuzz {endpoint_info['name']} returned non-JSON response")
                                
                                # Create basic schema from documentation
                                content = f"""{endpoint_info['name']}: {endpoint_info['description']}
                                
API Endpoint: {endpoint_info['endpoint']}
Method: POST
Status: API endpoint exists but returned non-JSON response
Authentication: Bearer Token + Hash

Note: Schema structure needs valid authentication for full introspection. This was discovered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                                
                                schema_docs.append({
                                    'id': endpoint_info['id'],
                                    'content': content
                                })
                                
                        elif response.status == 401:
                            logger.warning(f"Easebuzz {endpoint_info['name']} API returned 401 - authentication issue")
                            
                            content = f"""{endpoint_info['name']}: {endpoint_info['description']}
                            
API Endpoint: {endpoint_info['endpoint']}
Method: POST
Status: Authentication required
Authentication: Bearer Token + SHA256 Hash
Merchant ID: {self.merchant_id}

Note: Valid API key and hash required for schema introspection. Discovered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                            
                            schema_docs.append({
                                'id': endpoint_info['id'],
                                'content': content
                            })
                            
                        else:
                            logger.warning(f"Easebuzz {endpoint_info['name']} API returned {response.status}")
                            
                except Exception as e:
                    logger.warning(f"Error introspecting Easebuzz {endpoint_info['name']}: {e}")
                    
            # If no schemas were discovered, provide basic API structure
            if not schema_docs:
                schema_docs.append({
                    'id': 'easebuzz_api_structure',
                    'content': f"""Easebuzz API Structure: Payment gateway endpoints
                    
Base URL: {self.base_url}
Authentication: Bearer Token + SHA256 Hash
Merchant ID: {self.merchant_id}
Available Endpoints:
- /v1/payment/status (transactions)
- /v1/settlements (settlements)
- /v1/refunds (refunds)
- /v1/payouts (payouts via InstaCollect)

Hash Format: merchant_id|transaction_id|amount|secret_key (SHA256)
Required Headers: Authorization: Bearer <api_key>, Content-Type: application/json

Note: Full schema introspection requires valid API key and secret. Discovered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                })
                
        except Exception as e:
            logger.error(f"Error during Easebuzz schema introspection: {e}")
            # Fallback to basic structure
            schema_docs.append({
                'id': 'easebuzz_error_fallback',
                'content': f"""Easebuzz API (Connection Error): Payment gateway endpoints
                
Error: {str(e)}
Base URL: {self.base_url}
Status: Unable to connect for schema introspection

Note: This indicates a connection or authentication issue. Check credentials and network connectivity."""
            })
            
        return schema_docs
    
    def _extract_fields_from_response(self, data: Dict, endpoint: str) -> List[str]:
        """Extract field names from actual Easebuzz API response"""
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
        
        # Add common Easebuzz fields based on endpoint type
        if 'payment' in endpoint:
            fields.update(['transaction_id', 'amount', 'status', 'customer_email', 'payment_method'])
        elif 'settlements' in endpoint:
            fields.update(['settlement_id', 'amount', 'status', 'settlement_date', 'utr_number'])
        elif 'refunds' in endpoint:
            fields.update(['refund_id', 'transaction_id', 'amount', 'status', 'refund_date'])
        elif 'payouts' in endpoint:
            fields.update(['payout_id', 'beneficiary_name', 'account_number', 'amount', 'status'])
            
        return sorted(list(fields))
    
    async def test_connection(self) -> bool:
        """Test Easebuzz connection"""
        try:
            session = await self._get_session()
            
            # Test with a simple API call
            params = {
                'merchant_id': self.merchant_id
            }
            params['hash'] = self._generate_hash(params)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {self.auth_config.get('api_key')}"
            }
            
            async with session.post(
                f"{self.base_url}/v1/payment/status",
                json=params,
                headers=headers
            ) as response:
                success = response.status == 200
                if success:
                    # Check if Easebuzz returned a valid response
                    try:
                        data = await response.json()
                        # Check if authentication was valid
                        if data.get('status') == 'error' and 'authentication' in data.get('message', '').lower():
                            logger.error("Easebuzz connection test failed: Invalid authentication")
                            return False
                        logger.info("Easebuzz connection test successful")
                    except:
                        logger.warning("Easebuzz connection test: received non-JSON response")
                else:
                    error_text = await response.text()
                    logger.error(f"Easebuzz connection test failed: {response.status} - {error_text}")
                return success
                
        except Exception as e:
            logger.error(f"Easebuzz connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None 