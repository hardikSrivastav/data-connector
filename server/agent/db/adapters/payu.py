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
        
        # Credentials management
        self.credentials = None
        self._load_credentials()
        
    def _load_credentials(self):
        """Load PayU credentials from file"""
        try:
            # Get credentials directory
            home_dir = Path.home()
            credentials_dir = home_dir / ".data-connector"
            credentials_file = credentials_dir / "payu_credentials.json"
            
            if credentials_file.exists():
                with open(credentials_file, 'r') as f:
                    self.credentials = json.load(f)
                logger.info("Loaded PayU credentials")
            else:
                logger.info(f"PayU credentials file not found: {credentials_file}")
                
        except Exception as e:
            logger.error(f"Error loading PayU credentials: {e}")
            self.credentials = None
    
    def _save_credentials(self, credentials: Dict):
        """Save PayU credentials to file"""
        try:
            # Get credentials directory
            home_dir = Path.home()
            credentials_dir = home_dir / ".data-connector"
            credentials_dir.mkdir(exist_ok=True)
            credentials_file = credentials_dir / "payu_credentials.json"
            
            with open(credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            logger.info("Saved PayU credentials")
            
        except Exception as e:
            logger.error(f"Error saving PayU credentials: {e}")
    
    def reset_authentication(self) -> bool:
        """
        Reset PayU authentication by clearing stored credentials and removing credentials file
        
        Returns:
            bool: True if reset was successful, False otherwise
        """
        try:
            # Clear in-memory credentials
            self.credentials = None
            self.auth_config = {}
            
            # Remove credentials file
            home_dir = Path.home()
            credentials_file = home_dir / ".data-connector" / "payu_credentials.json"
            
            if credentials_file.exists():
                credentials_file.unlink()
                logger.info("Removed PayU credentials file")
            
            # Close session if exists
            if self.session:
                asyncio.create_task(self.session.close())
                self.session = None
            
            logger.info("PayU authentication reset successful")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting PayU authentication: {e}")
            return False
    
    async def authenticate(self, merchant_key: str, salt: str, merchant_id: Optional[str] = None, environment: str = "test"):
        """
        Authenticate with PayU using merchant credentials
        
        Args:
            merchant_key: PayU merchant key
            salt: PayU salt for hash generation
            merchant_id: PayU merchant ID (optional)
            environment: test or production
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
            
            # Add delay to avoid rate limiting
            await asyncio.sleep(1)
            
            # Test the credentials with a simple API call
            session = await self._get_session()
            
            # Use verify_payment for authentication testing with a proper transaction ID format
            # This is more reliable for authentication than get_transaction_details
            params = {
                'command': 'verify_payment',
                'key': merchant_key,
                'var1': f"TXN{actual_merchant_id}{int(datetime.now().timestamp())}"  # Generate a proper transaction ID
            }
            
            # Log the parameters for debugging
            logger.debug(f"Authentication parameters: {params}")
            
            # Generate hash for verification
            hash_string = f"{merchant_key}|verify_payment|{params['var1']}|{salt}"
            params['hash'] = hashlib.sha512(hash_string.encode()).hexdigest()
            
            # Use the correct PayU API endpoint
            test_url = f"{self.base_url}/merchant/postservice.php?form=2"
            
            logger.info(f"Testing PayU authentication with URL: {test_url}")
            logger.debug(f"Parameters: {params}")
            
            async with session.post(
                test_url,
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                
                response_text = await response.text()
                logger.debug(f"Response status: {response.status}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Response content type: {response.headers.get('content-type', 'unknown')}")
                logger.debug(f"Response preview: {response_text[:500]}")
                
                if response.status == 200:
                    # Check if response is JSON (either by content-type or by checking if it starts with {)
                    content_type = response.headers.get('content-type', '').lower()
                    response_starts_with_json = response_text.strip().startswith('{')
                    
                    if 'application/json' in content_type or response_starts_with_json:
                        try:
                            # Use json.loads() directly to avoid content-type issues
                            import json
                            data = json.loads(response_text)
                            
                            # Check if authentication was successful
                            if data.get('status') == 0 and 'invalid' in data.get('msg', '').lower():
                                logger.error("PayU authentication failed: Invalid credentials")
                                logger.error(f"PayU error message: {data.get('msg')}")
                                return False
                            elif data.get('status') == 1:
                                # Save credentials on successful authentication
                                self.credentials = credentials
                                self.auth_config = credentials
                                self._save_credentials(credentials)
                                
                                logger.info("PayU authentication successful")
                                return True
                            elif data.get('status') == 0 and 'transaction' in data.get('msg', '').lower():
                                # Transaction not found is actually a successful authentication
                                # It means our credentials and hash are valid, just the transaction doesn't exist
                                logger.info("PayU authentication successful (transaction not found, but credentials valid)")
                                self.credentials = credentials
                                self.auth_config = credentials
                                self._save_credentials(credentials)
                                return True
                            else:
                                logger.warning(f"Unexpected PayU response status: {data.get('status')}")
                                logger.warning(f"PayU response: {data}")
                                return False
                            
                        except Exception as json_error:
                            logger.error(f"Failed to parse JSON response: {json_error}")
                            logger.error(f"Response text: {response_text}")
                            return False
                    else:
                        # Handle HTML response (might be an error page)
                        logger.warning(f"Received HTML response instead of JSON. Content-Type: {content_type}")
                        logger.warning(f"Response preview: {response_text[:200]}")
                        
                        # Check if it's an error page
                        if 'error' in response_text.lower() or 'invalid' in response_text.lower():
                            logger.error("PayU authentication failed: Received error page")
                            return False
                        
                        # If it's not clearly an error, we'll assume it's successful
                        # (some PayU endpoints might return HTML for successful responses)
                        logger.info("PayU authentication successful (HTML response)")
                        self.credentials = credentials
                        self.auth_config = credentials
                        self._save_credentials(credentials)
                        return True
                elif response.status == 429:
                    logger.error("PayU rate limit exceeded. Please wait before retrying.")
                    return False
                else:
                    logger.error(f"PayU authentication failed: HTTP {response.status}")
                    logger.error(f"Response text: {response_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"PayU authentication error: {e}")
            return False
    
    async def _authenticate(self) -> Optional[str]:
        """Internal authentication method that returns credentials if valid"""
        if not self.credentials:
            logger.error("No PayU credentials available")
            return None
            
        # Check if credentials are expired (24 hours)
        if 'authenticated_at' in self.credentials:
            auth_time = datetime.fromisoformat(self.credentials['authenticated_at'])
            if datetime.now() - auth_time > timedelta(hours=24):
                logger.warning("PayU credentials expired")
                return None
        
        # Update auth_config with loaded credentials
        self.auth_config = self.credentials
        return self.credentials.get('merchant_key')

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
        
        command = params.get('command')
        
        # Create hash string based on PayU documentation
        # For verify_payment: key|command|var1|salt
        # For other commands: key|command|salt (if no var1)
        var1 = params.get('var1', '')
        
        if var1:
            hash_string = f"{merchant_key}|{command}|{var1}|{salt}"
        else:
            hash_string = f"{merchant_key}|{command}|{salt}"
            
        return hashlib.sha512(hash_string.encode()).hexdigest()
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to PayU API query"""
        schema_chunks = kwargs.get('schema_chunks', [])
        
        # Define PayU API endpoints
        api_endpoints = {
            'transactions': {
                'endpoint': '/merchant/postservice.php?form=2',
                'command': 'get_transaction_details',
                'description': 'Payment transactions - list, search, and get transaction details'
            },
            'settlements': {
                'endpoint': '/merchant/postservice.php?form=3',
                'command': 'get_settlement_status',
                'description': 'Settlement information and status'
            },
            'refunds': {
                'endpoint': '/merchant/postservice.php?form=4',
                'command': 'get_refund_details',
                'description': 'Refund management and processing'
            },
            'reports': {
                'endpoint': '/merchant/postservice.php?form=2',
                'command': 'get_transaction_details',
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
                
                response_text = await response.text()
                
                if response.status == 200:
                    # Check if response is JSON
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' in content_type or response_text.strip().startswith('{'):
                        try:
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
                                
                        except Exception as json_error:
                            logger.error(f"Failed to parse JSON response: {json_error}")
                            logger.error(f"Response text: {response_text}")
                            return []
                    else:
                        # Handle HTML response
                        logger.warning(f"Received HTML response instead of JSON. Content-Type: {content_type}")
                        logger.warning(f"Response preview: {response_text[:200]}")
                        
                        # Check if it's an error page
                        if 'error' in response_text.lower() or 'invalid' in response_text.lower():
                            logger.error("PayU API error: Received error page")
                            return []
                        
                        # If it's not clearly an error, return empty result
                        logger.warning("PayU API returned HTML response - treating as no data")
                        return []
                else:
                    logger.error(f"PayU HTTP error: {response.status}")
                    logger.error(f"Response text: {response_text}")
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
        """Return PayU schema information for the LLM"""
        return [
            {
                'id': 'payu_transactions',
                'content': '''PayU Transactions: Contains payment transaction information
                Fields: id, payment_id, amount, status (success/failure/pending), payment_method, bank_ref_num, 
                created_at, updated_at, customer_email, customer_phone, product_info, card_num, issuing_bank
                
                Use for: Payment tracking, transaction analysis, customer payments, payment method analysis
                Example queries: "Show successful transactions", "Failed payments today", "Transactions by amount"'''
            },
            {
                'id': 'payu_settlements',
                'content': '''PayU Settlements: Contains settlement and payout information
                Fields: id, amount, status, settlement_date, utr_number, bank_name, account_no, created_at
                
                Use for: Settlement tracking, payout analysis, bank transfer status
                Example queries: "Show recent settlements", "Settlement amounts", "UTR tracking"'''
            },
            {
                'id': 'payu_refunds',
                'content': '''PayU Refunds: Contains refund and chargeback information
                Fields: id, transaction_id, payment_id, amount, status, refund_date, reason, bank_ref_num, created_at
                
                Use for: Refund tracking, chargeback analysis, customer service
                Example queries: "Show pending refunds", "Refunds by reason", "Customer refund history"'''
            }
        ]
    
    async def test_connection(self) -> bool:
        """Test PayU connection"""
        try:
            session = await self._get_session()
            
            # Test the connection with a simple API call
            transaction_id = f"TXN{self.auth_config.get('merchant_id')}{int(datetime.now().timestamp())}"
            params = {
                'command': 'verify_payment',
                'key': self.auth_config.get('merchant_key'),
                'var1': transaction_id
            }
            
            # Generate hash
            hash_string = f"{self.auth_config.get('merchant_key')}|verify_payment|{transaction_id}|{self.auth_config.get('salt')}"
            params['hash'] = hashlib.sha512(hash_string.encode()).hexdigest()
            
            # Use the correct PayU API endpoint
            test_url = f"{self.base_url}/merchant/postservice.php?form=2"
            
            async with session.post(
                test_url,
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                
                response_text = await response.text()
                success = response.status == 200
                
                if success:
                    # Check if response is JSON
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' in content_type or response_text.strip().startswith('{'):
                        try:
                            data = await response.json()
                            # PayU returns status=1 for success, status=0 for error
                            if data.get('status') == 0 and 'hash' in data.get('msg', '').lower():
                                logger.error("PayU connection test failed: Invalid hash/authentication")
                                return False
                            logger.info("PayU connection test successful")
                        except Exception as json_error:
                            logger.warning(f"PayU connection test: received non-JSON response: {json_error}")
                            # If it's not JSON but HTTP 200, assume it's successful
                            return True
                    else:
                        # Handle HTML response
                        logger.warning(f"PayU connection test: received HTML response. Content-Type: {content_type}")
                        # If it's not clearly an error, assume success
                        if 'error' in response_text.lower() or 'invalid' in response_text.lower():
                            logger.error("PayU connection test failed: Received error page")
                            return False
                        logger.info("PayU connection test successful (HTML response)")
                        return True
                else:
                    logger.error(f"PayU connection test failed: HTTP {response.status}")
                    logger.error(f"Response text: {response_text}")
                return success
                
        except Exception as e:
            logger.error(f"PayU connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None 