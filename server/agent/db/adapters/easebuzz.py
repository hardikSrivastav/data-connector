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
        
        # Credentials management
        self.credentials = None
        self._load_credentials()
        
    def _load_credentials(self):
        """Load Easebuzz credentials from file"""
        try:
            # Get credentials directory
            home_dir = Path.home()
            credentials_dir = home_dir / ".data-connector"
            credentials_file = credentials_dir / "easebuzz_credentials.json"
            
            if credentials_file.exists():
                with open(credentials_file, 'r') as f:
                    self.credentials = json.load(f)
                logger.info("Loaded Easebuzz credentials")
            else:
                logger.info(f"Easebuzz credentials file not found: {credentials_file}")
                
        except Exception as e:
            logger.error(f"Error loading Easebuzz credentials: {e}")
            self.credentials = None
    
    def _save_credentials(self, credentials: Dict):
        """Save Easebuzz credentials to file"""
        try:
            # Get credentials directory
            home_dir = Path.home()
            credentials_dir = home_dir / ".data-connector"
            credentials_dir.mkdir(exist_ok=True)
            credentials_file = credentials_dir / "easebuzz_credentials.json"
            
            with open(credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            logger.info("Saved Easebuzz credentials")
            
        except Exception as e:
            logger.error(f"Error saving Easebuzz credentials: {e}")
    
    async def authenticate(self, merchant_key: str, salt: str, merchant_id: Optional[str] = None, environment: str = "test"):
        """
        Authenticate with Easebuzz using merchant credentials
        
        Args:
            merchant_key: Easebuzz merchant key
            salt: Easebuzz salt for hash generation
            merchant_id: Easebuzz merchant ID (optional)
            environment: test or prod
        """
        try:
            # Store credentials
            actual_merchant_id = merchant_id or self.merchant_id or "default_merchant"
            credentials = {
                'merchant_key': merchant_key,
                'salt': salt,
                'merchant_id': actual_merchant_id,
                'environment': environment,
                'authenticated_at': datetime.now().isoformat()
            }
            
            # Test the credentials with a simple API call
            session = await self._get_session()
            
            # Create a test transaction query
            test_params = {
                'merchant_id': actual_merchant_id,
                'transaction_id': 'test_txn_123',
                'amount': '1.00'
            }
            
            # Generate hash for verification
            hash_string = f"{actual_merchant_id}|test_txn_123|1.00|{salt}"
            test_params['hash'] = hashlib.sha256(hash_string.encode()).hexdigest()
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {merchant_key}"
            }
            
            # Use test endpoint for authentication verification
            test_url = f"{self.base_url}/v1/payment/status"
            
            async with session.post(
                test_url,
                json=test_params,
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if authentication was successful
                    if data.get('status') == 'error' and 'authentication' in data.get('message', '').lower():
                        logger.error("Easebuzz authentication failed: Invalid credentials")
                        return False
                    
                    # Save credentials on successful authentication
                    self.credentials = credentials
                    self.auth_config = credentials
                    self._save_credentials(credentials)
                    
                    logger.info("Easebuzz authentication successful")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Easebuzz authentication failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Easebuzz authentication error: {e}")
            return False
    
    async def _authenticate(self) -> Optional[str]:
        """Internal authentication method that returns credentials if valid"""
        if not self.credentials:
            logger.error("No Easebuzz credentials available")
            return None
            
        # Check if credentials are expired (24 hours)
        if 'authenticated_at' in self.credentials:
            auth_time = datetime.fromisoformat(self.credentials['authenticated_at'])
            if datetime.now() - auth_time > timedelta(hours=24):
                logger.warning("Easebuzz credentials expired")
                return None
        
        # Update auth_config with loaded credentials
        self.auth_config = self.credentials
        return self.credentials.get('merchant_key')

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
        """Return Easebuzz schema information for the LLM"""
        return [
            {
                'id': 'easebuzz_transactions',
                'content': '''Easebuzz Transactions: Contains payment transaction information
                Fields: id, payment_id, amount, status (success/failed/pending), payment_method, bank_ref_num, 
                created_at, updated_at, customer_email, customer_phone, product_info, issuing_bank, pg_type
                
                Use for: Payment tracking, transaction analysis, customer payments, payment method analysis
                Example queries: "Show successful transactions", "Failed payments today", "Transactions by amount"'''
            },
            {
                'id': 'easebuzz_settlements',
                'content': '''Easebuzz Settlements: Contains settlement and payout information
                Fields: id, amount, status, settlement_date, utr_number, bank_name, account_no, created_at
                
                Use for: Settlement tracking, payout analysis, bank transfer status
                Example queries: "Show recent settlements", "Settlement amounts", "UTR tracking"'''
            },
            {
                'id': 'easebuzz_refunds',
                'content': '''Easebuzz Refunds: Contains refund and chargeback information
                Fields: id, transaction_id, payment_id, amount, status, refund_date, reason, bank_ref_num, created_at
                
                Use for: Refund tracking, chargeback analysis, customer service
                Example queries: "Show pending refunds", "Refunds by reason", "Customer refund history"'''
            },
            {
                'id': 'easebuzz_payouts',
                'content': '''Easebuzz Payouts: Contains payout and transfer information via InstaCollect
                Fields: id, beneficiary_name, account_number, ifsc_code, amount, status, payout_date, 
                utr_number, bank_name, created_at
                
                Use for: Payout tracking, bank transfer management, beneficiary analysis
                Example queries: "Show pending payouts", "Payouts by bank", "Transfer status"'''
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