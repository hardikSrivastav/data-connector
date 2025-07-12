# Indian DTC Marketplace Services Integration Guide

## Overview

This document provides comprehensive integration guidance for four critical services used in Indian Direct-to-Consumer (DTC) marketplaces:

1. **Uniware (Unicommerce)** - Order and warehouse management
2. **PayU** - Payment gateway and financial services
3. **Easebuzz** - Payment gateway and business solutions
4. **Shiprocket** - Shipping and logistics platform

These integrations follow Ceneca's existing adapter architecture pattern, extending the `DBAdapter` base class to provide unified querying capabilities across operational data sources.

## Architecture Overview

### Adapter Pattern Structure

Each service adapter implements the following core interface:

```python
class ServiceAdapter(DBAdapter):
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Any
    async def execute(self, query: Any) -> List[Dict]
    async def introspect_schema(self) -> List[Dict[str, str]]
    async def test_connection(self) -> bool
```

### Authentication Flow

All services use API-based authentication with token management:

```python
# Common pattern for credential management
credentials_file = os.path.join(
    str(Path.home()), 
    ".data-connector", 
    f"{service_name}_credentials.json"
)
```

## 1. Uniware (Unicommerce) Integration

### Service Overview

**Uniware** is a comprehensive cloud-based order and warehouse management platform that provides:
- Multi-channel order processing
- Inventory management across facilities
- Fulfillment orchestration
- Returns management
- B2B and B2C order handling

### Authentication

**Method**: OAuth 2.0 with token-based authentication

```python
# Authentication endpoint
POST https://{tenant}.unicommerce.com/oauth/token
```

**Required Parameters**:
- `grant_type`: "password"
- `client_id`: "my-trusted-client"
- `username`: Uniware login username
- `password`: Uniware login password

**Response Structure**:
```json
{
    "access_token": "bearer-token-here",
    "token_type": "bearer",
    "refresh_token": "refresh-token-here",
    "expires_in": 41621
}
```

### Key API Endpoints

#### Order Management
```python
# Get orders
POST /services/rest/v1/oms/saleorder/search
# Get specific order
POST /services/rest/v1/oms/saleorder/get
# Create order
POST /services/rest/v1/oms/saleorder/create
# Update order status
POST /services/rest/v1/oms/saleorder/update
```

#### Inventory Management
```python
# Get inventory snapshot
POST /services/rest/v1/inventory/get
# Adjust inventory
POST /services/rest/v1/inventory/adjust
# Check stock levels
POST /services/rest/v1/inventory/snapshot
```

#### Fulfillment Operations
```python
# Create shipping package
POST /services/rest/v1/oms/forward/create
# Generate invoice
POST /services/rest/v1/oms/invoice/create
# Track shipment
POST /services/rest/v1/oms/forward/track
```

### Data Schema Structure

**Order Entity**:
```python
order_schema = {
    "code": "SO1016233",
    "displayOrderCode": "Order-Display-Code",
    "channel": "MARKETPLACE_NAME",
    "status": "PROCESSING|COMPLETE|CANCELLED",
    "customerCode": "customer-identifier",
    "totalAmount": 1250.00,
    "currency": "INR",
    "orderItems": [
        {
            "itemSku": "product-sku-123",
            "quantity": 2,
            "sellingPrice": 625.00,
            "facilityCode": "warehouse-01"
        }
    ],
    "addresses": {
        "billing": {...},
        "shipping": {...}
    }
}
```

**Inventory Entity**:
```python
inventory_schema = {
    "itemSku": "product-sku-123",
    "facilityCode": "warehouse-01",
    "totalStock": 100,
    "availableStock": 85,
    "allocatedStock": 15,
    "inventoryType": "GOOD|DEFECTIVE|RETURNED"
}
```

### Implementation Considerations

1. **Multi-tenant Architecture**: Each client has a separate tenant URL
2. **Rate Limiting**: Implement exponential backoff for API calls
3. **Webhook Support**: Handle real-time order and inventory updates
4. **Error Handling**: Comprehensive error code mapping (refer to response codes documentation)

## 2. PayU Integration

### Service Overview

**PayU** is a leading payment gateway in India providing:
- Multiple payment methods (cards, UPI, wallets, net banking)
- Hosted and custom checkout solutions
- Recurring payments and subscriptions
- Cross-border payment processing
- Advanced fraud detection

### Authentication

**Method**: Merchant Key and Salt-based authentication

```python
# Test Environment
base_url = "https://test.payu.in"
# Production Environment  
base_url = "https://secure.payu.in"
```

**Authentication Parameters**:
- `merchant_key`: Provided by PayU
- `salt`: Secret key for hash generation
- `hash`: SHA-512 hash of transaction parameters

### Key API Endpoints

#### Payment Processing
```python
# Create payment
POST /_payment
# Verify payment
POST /merchant/postservice?form=2
# Refund payment
POST /merchant/postservice?form=1
# Get transaction details
POST /merchant/postservice?form=3
```

#### Subscription Management
```python
# Create subscription
POST /merchant/postservice?form=5
# Cancel subscription
POST /merchant/postservice?form=6
# Get subscription details
POST /merchant/postservice?form=7
```

### Data Schema Structure

**Payment Entity**:
```python
payment_schema = {
    "txnid": "unique-transaction-id",
    "amount": "1000.00",
    "productinfo": "Product Description",
    "firstname": "Customer Name",
    "email": "customer@example.com",
    "phone": "9876543210",
    "surl": "https://success-url.com",
    "furl": "https://failure-url.com",
    "key": "merchant-key",
    "hash": "generated-hash"
}
```

**Transaction Response**:
```python
transaction_schema = {
    "mihpayid": "payu-transaction-id",
    "mode": "CC|DC|NB|UPI",
    "status": "success|failure|pending",
    "unmappedstatus": "captured|bounced|pending",
    "key": "merchant-key",
    "txnid": "transaction-id",
    "amount": "1000.00",
    "discount": "0.00",
    "net_amount_debit": "1000.00"
}
```

### Implementation Considerations

1. **Hash Generation**: Critical for security - implement proper SHA-512 hashing
2. **Webhook Validation**: Verify webhook authenticity using salt
3. **PCI Compliance**: Follow security guidelines for card data handling
4. **Multi-currency Support**: Handle international transactions

## 3. Easebuzz Integration

### Service Overview

**Easebuzz** provides comprehensive payment and business solutions:
- Payment gateway with multiple payment modes
- Payment links and invoicing
- Wire transfers (NEFT/RTGS/IMPS)
- Virtual account management (InstaCollect)
- Subscription and recurring payments
- Business tax payments

### Authentication

**Method**: API Key and Secret-based authentication

```python
# Test Environment
base_url = "https://testpay.easebuzz.in"
# Production Environment
base_url = "https://pay.easebuzz.in"
```

**Authentication Headers**:
```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
```

### Key API Endpoints

#### Payment Gateway
```python
# Create payment
POST /payment/v1/create
# Payment status
GET /payment/v1/retrieve
# Refund payment
POST /payment/v1/refund
```

#### Payment Links
```python
# Create payment link
POST /payment-link/v1/create
# Get payment link details
GET /payment-link/v1/{link_id}
```

#### Wire Transfers
```python
# Create payout
POST /wire/v1/create
# Check payout status
GET /wire/v1/status/{payout_id}
# Bulk payouts
POST /wire/v1/bulk
```

#### Virtual Accounts (InstaCollect)
```python
# Create virtual account
POST /instacollect/v1/create
# Get collections
GET /instacollect/v1/collections
```

### Data Schema Structure

**Payment Entity**:
```python
payment_schema = {
    "txnid": "unique-transaction-id",
    "amount": 1000.00,
    "firstname": "Customer Name",
    "email": "customer@example.com",
    "phone": "9876543210",
    "productinfo": "Product Description",
    "surl": "https://success-url.com",
    "furl": "https://failure-url.com",
    "udf1": "custom-field-1",
    "udf2": "custom-field-2"
}
```

**Payout Entity**:
```python
payout_schema = {
    "payout_id": "unique-payout-id",
    "amount": 5000.00,
    "beneficiary_name": "Recipient Name",
    "beneficiary_account": "bank-account-number",
    "beneficiary_ifsc": "BANK0001234",
    "transfer_mode": "NEFT|RTGS|IMPS",
    "purpose": "payout-purpose"
}
```

### Implementation Considerations

1. **Webhook Security**: Implement proper signature verification
2. **Rate Limiting**: Respect API rate limits (varies by endpoint)
3. **Error Handling**: Comprehensive error code mapping
4. **Compliance**: Handle KYC and regulatory requirements

## 4. Shiprocket Integration

### Service Overview

**Shiprocket** is India's leading shipping aggregator providing:
- Multi-courier integration (19,000+ pin codes)
- Automated shipping solutions
- Real-time tracking and updates
- Label generation and manifest creation
- Returns management
- International shipping capabilities

### Authentication

**Method**: Token-based authentication with email/password

```python
# Authentication endpoint
POST https://apiv2.shiprocket.in/v1/external/auth/login
```

**Login Payload**:
```python
{
    "email": "user@example.com",
    "password": "password"
}
```

### Key API Endpoints

#### Order Management
```python
# Create order
POST /v1/external/orders/create/adhoc
# Get orders
GET /v1/external/orders
# Cancel order
POST /v1/external/orders/cancel
```

#### Shipping Operations
```python
# Generate AWB
POST /v1/external/courier/assign/awb
# Check serviceability
GET /v1/external/courier/serviceability
# Request pickup
POST /v1/external/courier/generate/pickup
```

#### Tracking
```python
# Track by AWB
GET /v1/external/courier/track/awb/{awb}
# Track by order ID
GET /v1/external/courier/track/order/{order_id}
```

#### Label and Manifest
```python
# Generate label
POST /v1/external/courier/generate/label
# Generate manifest
POST /v1/external/courier/generate/manifest
```

### Data Schema Structure

**Order Entity**:
```python
order_schema = {
    "order_id": "unique-order-id",
    "order_date": "2024-01-15",
    "pickup_location": "warehouse-location",
    "billing_customer_name": "Customer Name",
    "billing_last_name": "Last Name",
    "billing_address": "Complete Address",
    "billing_city": "City",
    "billing_pincode": "110001",
    "billing_state": "Delhi",
    "billing_country": "India",
    "billing_email": "customer@example.com",
    "billing_phone": "9876543210",
    "shipping_is_billing": True,
    "order_items": [
        {
            "name": "Product Name",
            "sku": "product-sku-123",
            "units": 2,
            "selling_price": 500.00,
            "weight": 0.5,
            "length": 10,
            "breadth": 10,
            "height": 5
        }
    ],
    "payment_method": "COD|Prepaid",
    "total_discount": 0.00,
    "sub_total": 1000.00,
    "weight": 1.0,
    "length": 20,
    "breadth": 15,
    "height": 10
}
```

**Shipment Entity**:
```python
shipment_schema = {
    "shipment_id": "shipment-id-123",
    "awb": "tracking-number",
    "courier_name": "Courier Partner",
    "status": "PICKUP_GENERATED|DELIVERED|RTO",
    "tracking_data": [
        {
            "date": "2024-01-15",
            "status": "Order Confirmed",
            "location": "Delhi"
        }
    ]
}
```

### Implementation Considerations

1. **Webhook Integration**: Real-time status updates via webhooks
2. **Rate Calculation**: Dynamic pricing based on weight, dimensions, and distance
3. **Multi-courier Logic**: Intelligent courier selection based on serviceability
4. **Returns Management**: Handle RTO and returns processing

## Adapter Implementation Guide

### Base Adapter Template

```python
class IndianDTCAdapter(DBAdapter):
    """Base adapter for Indian DTC marketplace services"""
    
    def __init__(self, connection_uri: str, service_type: str, **kwargs):
        super().__init__(connection_uri)
        self.service_type = service_type
        self.credentials_file = os.path.join(
            str(Path.home()), 
            ".data-connector", 
            f"{service_type}_credentials.json"
        )
        self.access_token = None
        self.token_expires_at = None
        self._load_credentials()
    
    async def llm_to_query(self, nl_prompt: str, **kwargs) -> Dict:
        """Convert natural language to service-specific query"""
        # Use LLM to understand intent and map to appropriate API calls
        # Examples:
        # "Show me orders from last week" -> GET /orders with date filter
        # "What's the status of order 123?" -> GET /order/123/status
        # "Process refund for transaction ABC" -> POST /refund with txn_id
        
        query_mapping = await self._map_nl_to_api_call(nl_prompt)
        return query_mapping
    
    async def execute(self, query: Dict) -> List[Dict]:
        """Execute API call and return results"""
        endpoint = query.get('endpoint')
        method = query.get('method', 'GET')
        params = query.get('params', {})
        
        response = await self._make_api_request(endpoint, method, params)
        return self._normalize_response(response)
    
    async def introspect_schema(self) -> List[Dict[str, str]]:
        """Return schema information for the service"""
        schema_docs = []
        for entity_type in self.supported_entities:
            schema_docs.append({
                'id': f"{self.service_type}_{entity_type}",
                'content': self._get_entity_schema(entity_type)
            })
        return schema_docs
    
    async def test_connection(self) -> bool:
        """Test service connectivity"""
        try:
            await self._authenticate()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
```

### Service-Specific Implementations

#### Uniware Adapter
```python
class UniwareAdapter(IndianDTCAdapter):
    def __init__(self, connection_uri: str, **kwargs):
        super().__init__(connection_uri, "uniware", **kwargs)
        self.tenant_url = connection_uri
        self.supported_entities = [
            "orders", "inventory", "products", "customers", 
            "shipments", "returns", "facilities"
        ]
    
    async def _authenticate(self):
        """OAuth authentication for Uniware"""
        # Implementation details...
```

#### PayU Adapter
```python
class PayUAdapter(IndianDTCAdapter):
    def __init__(self, connection_uri: str, **kwargs):
        super().__init__(connection_uri, "payu", **kwargs)
        self.merchant_key = kwargs.get('merchant_key')
        self.salt = kwargs.get('salt')
        self.supported_entities = [
            "transactions", "refunds", "subscriptions", 
            "payment_methods", "settlements"
        ]
    
    def _generate_hash(self, params: Dict) -> str:
        """Generate SHA-512 hash for PayU authentication"""
        # Implementation details...
```

#### Easebuzz Adapter
```python
class EasebuzzAdapter(IndianDTCAdapter):
    def __init__(self, connection_uri: str, **kwargs):
        super().__init__(connection_uri, "easebuzz", **kwargs)
        self.api_key = kwargs.get('api_key')
        self.supported_entities = [
            "payments", "payouts", "payment_links", 
            "virtual_accounts", "subscriptions"
        ]
```

#### Shiprocket Adapter
```python
class ShiprocketAdapter(IndianDTCAdapter):
    def __init__(self, connection_uri: str, **kwargs):
        super().__init__(connection_uri, "shiprocket", **kwargs)
        self.supported_entities = [
            "orders", "shipments", "tracking", "couriers", 
            "pickup_locations", "labels", "manifests"
        ]
```

## Configuration and Deployment

### Environment Setup

```yaml
# config.yaml
dtc_services:
  uniware:
    enabled: true
    base_url: "https://{tenant}.unicommerce.com"
    timeout: 30
    retry_attempts: 3
    
  payu:
    enabled: true
    base_url: "https://secure.payu.in"
    test_mode: false
    webhook_validation: true
    
  easebuzz:
    enabled: true
    base_url: "https://pay.easebuzz.in"
    rate_limit: 100  # requests per minute
    
  shiprocket:
    enabled: true
    base_url: "https://apiv2.shiprocket.in"
    webhook_secret: "${SHIPROCKET_WEBHOOK_SECRET}"
```

### Credential Management

```python
# Credential file structure
{
    "service_type": "uniware",
    "credentials": {
        "tenant_url": "https://client.unicommerce.com",
        "username": "api_user@example.com",
        "password": "secure_password",
        "access_token": "current_token",
        "refresh_token": "refresh_token",
        "expires_at": 1640995200
    },
    "settings": {
        "default_facility": "warehouse_01",
        "auto_refresh_token": true
    }
}
```

### Registry Registration

```python
# Add to adapter registry
ADAPTER_REGISTRY.update({
    "uniware": UniwareAdapter,
    "payu": PayUAdapter,
    "easebuzz": EasebuzzAdapter,
    "shiprocket": ShiprocketAdapter
})
```

## Security Considerations

### Data Protection
1. **Encryption**: All API credentials encrypted at rest
2. **Secure Transmission**: TLS 1.2+ for all API communications
3. **Token Management**: Automatic token refresh and secure storage
4. **Audit Logging**: Complete audit trail of all API interactions

### Compliance Requirements
1. **PCI DSS**: For payment-related data handling
2. **Data Localization**: Compliance with Indian data protection laws
3. **KYC Requirements**: Proper customer verification processes
4. **GST Compliance**: Accurate tax calculation and reporting

## Error Handling and Monitoring

### Error Classification
```python
class DTCServiceError(Exception):
    """Base exception for DTC service errors"""
    pass

class AuthenticationError(DTCServiceError):
    """Authentication-related errors"""
    pass

class RateLimitError(DTCServiceError):
    """Rate limit exceeded errors"""
    pass

class ServiceUnavailableError(DTCServiceError):
    """Service temporarily unavailable"""
    pass
```

### Monitoring and Alerts
1. **API Response Times**: Monitor and alert on slow responses
2. **Error Rates**: Track error patterns and failure rates
3. **Token Expiration**: Proactive token refresh monitoring
4. **Webhook Failures**: Alert on webhook delivery failures

## Testing Strategy

### Unit Tests
```python
# Test authentication
async def test_authentication():
    adapter = UniwareAdapter("https://test.unicommerce.com")
    assert await adapter.test_connection()

# Test query execution
async def test_order_query():
    adapter = UniwareAdapter("https://test.unicommerce.com")
    query = await adapter.llm_to_query("Show me all orders from yesterday")
    results = await adapter.execute(query)
    assert len(results) >= 0
```

### Integration Tests
1. **End-to-End Workflows**: Test complete order-to-delivery flows
2. **Webhook Processing**: Verify real-time update handling
3. **Error Scenarios**: Test graceful failure handling
4. **Performance**: Load testing with realistic data volumes

## Best Practices

### API Usage
1. **Rate Limiting**: Implement proper backoff strategies
2. **Idempotency**: Use idempotent operations where possible
3. **Bulk Operations**: Batch requests when supported
4. **Caching**: Cache stable data to reduce API calls

### Data Management
1. **Schema Validation**: Validate all input/output data
2. **Data Transformation**: Normalize data formats across services
3. **Audit Trail**: Maintain complete operation history
4. **Backup Strategy**: Regular backup of configuration and credentials

## Troubleshooting Guide

### Common Issues

#### Authentication Failures
```python
# Check credential validity
if not await adapter.test_connection():
    logger.error("Authentication failed - check credentials")
    # Trigger credential refresh or manual intervention
```

#### Rate Limit Handling
```python
# Implement exponential backoff
async def retry_with_backoff(operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await operation()
        except RateLimitError:
            wait_time = 2 ** attempt
            await asyncio.sleep(wait_time)
    raise Exception("Max retries exceeded")
```

#### Webhook Validation
```python
# Verify webhook authenticity
def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode(), 
        payload.encode(), 
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
```

## Future Enhancements

### Planned Features
1. **AI-Powered Insights**: Advanced analytics across all services
2. **Automated Reconciliation**: Cross-platform data validation
3. **Smart Routing**: Intelligent service selection based on requirements
4. **Predictive Analytics**: Demand forecasting and inventory optimization

### Scalability Considerations
1. **Microservices Architecture**: Service-specific adapters as independent services
2. **Event-Driven Architecture**: Asynchronous processing with message queues
3. **Horizontal Scaling**: Load balancing across multiple adapter instances
4. **Database Sharding**: Partition data by service type or tenant

## Conclusion

This comprehensive integration guide provides the foundation for connecting Ceneca with India's leading DTC marketplace services. By following the established adapter patterns and implementing proper security, monitoring, and error handling, these integrations will provide robust, scalable access to critical business operations data.

The unified query interface allows users to seamlessly analyze data across order management, payments, and logistics platforms, providing unprecedented visibility into their complete business operations.

---

*This document should be regularly updated as services evolve and new features are added. For specific implementation details, refer to the individual service API documentation and the Ceneca adapter development guidelines.* 