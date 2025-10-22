# Complete Razorpay Integration Guide

## 📋 Overview
This guide covers the complete Razorpay payment gateway integration flow: backend order creation → frontend payment UI → backend verification → database persistence.

---

## 🔧 Part 1: Backend Setup (Node.js/Express)

### Step 1: Install Dependencies
```bash
npm install razorpay crypto
```

### Step 2: Configure Razorpay (`config/razorpay.js`)
```javascript
const Razorpay = require('razorpay');

const razorpayInstance = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID,      // Get from Razorpay Dashboard
  key_secret: process.env.RAZORPAY_KEY_SECRET // Keep this secret!
});

// Define your payment amount (in smallest currency unit)
// For INR: 1 Rupee = 100 paise
// For USD: 1 Dollar = 100 cents
const PAYMENT_AMOUNT = 37500; // ₹375 = 37500 paise

module.exports = { razorpayInstance, PAYMENT_AMOUNT };
```

### Step 3: Database Models
Create a Payment model to track transactions:

```javascript
// models/Payment.js
const { DataTypes } = require('sequelize');
const { sequelize } = require('../config/database');
const User = require('./User');

const Payment = sequelize.define('Payment', {
  id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  userId: {
    type: DataTypes.UUID,
    allowNull: false,
    references: {
      model: User,
      key: 'id'
    }
  },
  razorpayPaymentId: {
    type: DataTypes.STRING,
    allowNull: true  // Set after successful payment
  },
  razorpayOrderId: {
    type: DataTypes.STRING,
    allowNull: false,
    unique: true
  },
  amount: {
    type: DataTypes.INTEGER,
    allowNull: false
  },
  currency: {
    type: DataTypes.STRING,
    allowNull: false,
    defaultValue: 'INR'
  },
  status: {
    type: DataTypes.ENUM('created', 'attempted', 'paid', 'failed', 'refunded'),
    allowNull: false,
    defaultValue: 'created'
  },
  paymentDate: {
    type: DataTypes.DATE,
    allowNull: true
  },
  createdAt: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW
  },
  updatedAt: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW
  }
}, {
  tableName: 'payments',
  timestamps: true
});

// Define associations
Payment.belongsTo(User, { foreignKey: 'userId' });
User.hasMany(Payment, { foreignKey: 'userId' });

module.exports = Payment;
```

### Step 4: Payment Controller (`controllers/paymentController.js`)

**Create Order Endpoint:**
```javascript
const crypto = require('crypto');
const User = require('../models/User');
const Payment = require('../models/Payment');
const { razorpayInstance, PAYMENT_AMOUNT } = require('../config/razorpay');
const { sequelize } = require('../config/database');

/**
 * Create a new order for Razorpay
 */
exports.createOrder = async (req, res) => {
  const { userId } = req.body;
  
  try {
    // Verify user exists
    const user = await User.findByPk(userId);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found'
      });
    }
    
    // Create a Razorpay order with a shorter receipt ID
    const timestamp = Date.now().toString().substr(-10);
    const shortUserId = userId.split('-')[0]; // Take just the first part of the UUID
    
    const options = {
      amount: PAYMENT_AMOUNT,  // Amount in smallest currency unit
      currency: 'INR',
      receipt: `wl_${shortUserId}_${timestamp}`, // Unique receipt ID
      notes: {
        userId: userId,
        purpose: 'Waitlist Registration'
      }
    };
    
    const order = await razorpayInstance.orders.create(options);
    
    // Create payment record
    await Payment.create({
      userId,
      razorpayOrderId: order.id,
      amount: PAYMENT_AMOUNT,
      currency: 'INR',
      status: 'created'
    });
    
    return res.status(200).json({
      success: true,
      data: {
        orderId: order.id,
        amount: order.amount,
        currency: order.currency,
        keyId: process.env.RAZORPAY_KEY_ID  // Send public key to frontend
      }
    });
  } catch (error) {
    console.error('Error creating Razorpay order:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to create payment order',
      error: error.message
    });
  }
};
```

**Verify Payment Endpoint (CRITICAL FOR SECURITY):**
```javascript
/**
 * Verify and process Razorpay payment
 */
exports.verifyPayment = async (req, res) => {
  const { razorpayOrderId, razorpayPaymentId, razorpaySignature } = req.body;
  
  // Start a transaction
  const transaction = await sequelize.transaction();
  
  try {
    // STEP 1: Verify the signature (prevents fraud)
    const generatedSignature = crypto
      .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET)
      .update(razorpayOrderId + '|' + razorpayPaymentId)
      .digest('hex');
    
    if (generatedSignature !== razorpaySignature) {
      await transaction.rollback();
      return res.status(400).json({
        success: false,
        message: 'Invalid payment signature - possible fraud attempt'
      });
    }
    
    // STEP 2: Find payment record in database
    const payment = await Payment.findOne({
      where: { razorpayOrderId },
      include: [{ model: User }]
    });
    
    if (!payment) {
      await transaction.rollback();
      return res.status(404).json({
        success: false,
        message: 'Payment record not found'
      });
    }
    
    // STEP 3: Update payment status
    await payment.update({
      razorpayPaymentId,
      status: 'paid',
      paymentDate: new Date()
    }, { transaction });
    
    // STEP 4: Perform post-payment actions
    // (e.g., grant access, send email, update user status)
    // Example: Update waitlist status
    const waitlist = await Waitlist.findOne({
      where: { userId: payment.userId }
    });
    
    if (waitlist) {
      await waitlist.update({
        status: 'pending'
      }, { transaction });
    }
    
    await transaction.commit();
    
    return res.status(200).json({
      success: true,
      data: {
        userId: payment.userId,
        status: 'paid',
        message: 'Payment verified successfully'
      }
    });
  } catch (error) {
    await transaction.rollback();
    console.error('Error verifying payment:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to verify payment',
      error: error.message
    });
  }
};
```

### Step 5: Routes (`routes/paymentRoutes.js`)
```javascript
const express = require('express');
const paymentController = require('../controllers/paymentController');
const router = express.Router();

// Create order
router.post('/create-order', paymentController.createOrder);

// Verify payment
router.post('/verify', paymentController.verifyPayment);

module.exports = router;
```

### Step 6: Register Routes in Main App
```javascript
// app.js or server.js
const paymentRoutes = require('./routes/paymentRoutes');

app.use('/api/payments', paymentRoutes);
```

---

## 🎨 Part 2: Frontend Setup (React/Next.js)

### Step 1: TypeScript Declarations
```typescript
// Add to your component or global.d.ts
declare global {
  interface Window {
    Razorpay: any;
  }
}
```

### Step 2: Payment Modal Component (`components/PaymentModal.tsx`)
```typescript
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
  userDetails: {
    name: string;
    email: string;
    company: string;
  };
}

export default function PaymentModal({ 
  isOpen, 
  onClose, 
  userId, 
  userDetails 
}: PaymentModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const router = useRouter();

  // Load Razorpay script
  useEffect(() => {
    setIsMounted(true);
    
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    document.body.appendChild(script);

    return () => {
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, []);

  const handlePayment = async () => {
    if (!userId) {
      toast.error("Unable to process payment. Please try registering again.");
      onClose();
      return;
    }

    setIsLoading(true);

    try {
      // 1. Create order on backend
      const orderResponse = await fetch('/api/payments/create-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ userId }),
      });

      const orderData = await orderResponse.json();
      
      if (!orderData.success) {
        throw new Error(orderData.message || 'Could not create payment order');
      }

      // 2. Initialize Razorpay checkout
      const options = {
        key: orderData.data.keyId,
        amount: orderData.data.amount,
        currency: orderData.data.currency,
        name: "Your Company Name",
        description: "Waitlist Registration Fee",
        order_id: orderData.data.orderId,
        handler: function (response: any) {
          handlePaymentSuccess(response);
        },
        prefill: {
          name: userDetails.name,
          email: userDetails.email,
          contact: ""
        },
        notes: {
          address: userDetails.company
        },
        theme: {
          color: "#7b35b8"  // Your brand color
        }
      };

      const razorpayInstance = new window.Razorpay(options);
      razorpayInstance.open();
      
      // Handle payment failure
      razorpayInstance.on('payment.failed', function (response: any) {
        toast.error("Payment failed. Please try again.");
        setIsLoading(false);
      });
    } catch (error) {
      console.error("Payment initialization error:", error);
      toast.error("Could not initialize payment. Please try again.");
      setIsLoading(false);
    }
  };

  const handlePaymentSuccess = async (response: any) => {
    try {
      // Verify payment with backend
      const verifyResponse = await fetch('/api/payments/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          razorpayOrderId: response.razorpay_order_id,
          razorpayPaymentId: response.razorpay_payment_id,
          razorpaySignature: response.razorpay_signature,
          userId: userId
        }),
      });

      const verifyData = await verifyResponse.json();
      
      if (verifyData.success) {
        toast.success("Payment successful! You've been added to our waitlist.");
        onClose();
        // Signal to parent component that payment was successful
        window.dispatchEvent(new CustomEvent('payment_success'));
      } else {
        toast.error("Payment verification failed. Please contact support.");
      }
    } catch (error) {
      console.error("Payment verification error:", error);
      toast.error("Payment verification failed. Please contact support.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isMounted || !isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="relative bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl max-w-md w-full p-6">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
        >
          <X size={20} />
          <span className="sr-only">Close</span>
        </button>
        
        <div className="flex flex-col gap-2 text-center sm:text-left mb-4">
          <h2 className="text-2xl font-bold">Complete Your Registration</h2>
          <p className="text-base text-muted-foreground">
            A one-time payment of ₹375 (approx. $5) is required to join our waitlist.
          </p>
        </div>
        
        <div className="space-y-4 py-4">
          <div className="rounded-lg bg-background/60 p-4 border border-muted">
            <h3 className="font-medium mb-2">Waitlist Benefits</h3>
            <ul className="space-y-2 text-sm">
              <li className="flex items-start">
                <span className="mr-2">✓</span>
                <span>First month free</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">✓</span>
                <span>Personalised onboarding</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">✓</span>
                <span>Direct feedback channel</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">✓</span>
                <span>Exclusive product development updates</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">✓</span>
                <span>Early access to our platform</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            onClick={handlePayment}
            disabled={isLoading}
            className="w-full h-10 text-base"
          >
            {isLoading ? "Processing..." : "Pay ₹375 to Join Waitlist"}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
```

### Step 3: Next.js API Routes (Optional Proxy)

**Create Order API Route (`app/api/payments/create-order/route.ts`):**
```typescript
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    if (!body.userId) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'User ID is required'
        },
        { status: 400 }
      );
    }
    
    // Call backend API to create order
    const response = await fetch(`${API_BASE_URL}/payments/create-order`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ userId: body.userId }),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error creating order:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to create payment order'
      },
      { status: 500 }
    );
  }
}
```

**Verify Payment API Route (`app/api/payments/verify/route.ts`):**
```typescript
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    if (!body.razorpayOrderId || !body.razorpayPaymentId || !body.razorpaySignature) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'Missing verification parameters'
        },
        { status: 400 }
      );
    }
    
    // Ensure we have userId to connect payment to right user
    if (!body.userId) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'User ID is required for payment verification'
        },
        { status: 400 }
      );
    }
    
    // Call backend API to verify payment
    const response = await fetch(`${API_BASE_URL}/payments/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        razorpayOrderId: body.razorpayOrderId,
        razorpayPaymentId: body.razorpayPaymentId,
        razorpaySignature: body.razorpaySignature,
        userId: body.userId
      }),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error verifying payment:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to verify payment'
      },
      { status: 500 }
    );
  }
}
```

---

## 🔒 Part 3: Security Best Practices

### 1. Environment Variables
```bash
# .env file (NEVER commit this!)
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxx

# Optional webhook secret
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxx
```

**Add to `.gitignore`:**
```
.env
.env.local
```

### 2. Signature Verification (MANDATORY)
**Always verify the signature on your backend**. Never trust the frontend payment status alone.

```javascript
const crypto = require('crypto');

const verifySignature = (orderId, paymentId, signature, secret) => {
  const generated = crypto
    .createHmac('sha256', secret)
    .update(orderId + '|' + paymentId)
    .digest('hex');
  
  return generated === signature;
};
```

**Why this is critical:**
- Prevents attackers from faking successful payments
- Ensures payment data hasn't been tampered with
- Required by Razorpay for PCI compliance

### 3. HTTPS Only
- Always use HTTPS in production
- Razorpay will reject non-HTTPS callbacks
- Use Let's Encrypt for free SSL certificates

### 4. Payment Status Double-Check (Optional but Recommended)
```javascript
// Query Razorpay API to verify payment status
const verifyPaymentStatus = async (paymentId) => {
  try {
    const payment = await razorpayInstance.payments.fetch(paymentId);
    
    if (payment.status !== 'captured') {
      throw new Error('Payment not captured');
    }
    
    return payment;
  } catch (error) {
    console.error('Error fetching payment:', error);
    throw error;
  }
};
```

### 5. Rate Limiting
Add rate limiting to prevent abuse:

```javascript
const rateLimit = require('express-rate-limit');

const paymentLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // Limit each IP to 5 requests per windowMs
  message: 'Too many payment attempts, please try again later'
});

router.post('/create-order', paymentLimiter, paymentController.createOrder);
```

### 6. Input Validation
```javascript
const { body, validationResult } = require('express-validator');

router.post('/create-order', [
  body('userId').isUUID().withMessage('Invalid user ID format'),
  (req, res, next) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ 
        success: false, 
        errors: errors.array() 
      });
    }
    next();
  }
], paymentController.createOrder);
```

---

## 🚀 Part 4: Going Live

### Step 1: Get Live Credentials
1. Complete KYC on Razorpay Dashboard
   - Submit business documents
   - Verify bank account
   - Wait for approval (usually 24-48 hours)
2. Get Live API keys from Dashboard
3. Update environment variables

### Step 2: Test Mode vs Live Mode
```javascript
// config/razorpay.js
const Razorpay = require('razorpay');

const isProduction = process.env.NODE_ENV === 'production';

const razorpayInstance = new Razorpay({
  key_id: isProduction 
    ? process.env.RAZORPAY_LIVE_KEY_ID 
    : process.env.RAZORPAY_TEST_KEY_ID,
  key_secret: isProduction
    ? process.env.RAZORPAY_LIVE_KEY_SECRET
    : process.env.RAZORPAY_TEST_KEY_SECRET
});

module.exports = { razorpayInstance };
```

### Step 3: Webhooks (Recommended for Production)
Set up webhooks for real-time payment status updates:

**Configure Webhook URL in Razorpay Dashboard:**
```
https://yourdomain.com/api/webhooks/razorpay
```

**Webhook Endpoint:**
```javascript
// routes/webhookRoutes.js
const crypto = require('crypto');
const Payment = require('../models/Payment');

exports.handleWebhook = async (req, res) => {
  const secret = process.env.RAZORPAY_WEBHOOK_SECRET;
  
  // Verify webhook signature
  const signature = req.headers['x-razorpay-signature'];
  const body = JSON.stringify(req.body);
  
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(body)
    .digest('hex');
  
  if (signature !== expectedSignature) {
    return res.status(400).json({ error: 'Invalid signature' });
  }
  
  const event = req.body.event;
  const payment = req.body.payload.payment.entity;
  
  // Handle different events
  try {
    switch(event) {
      case 'payment.captured':
        // Payment successful
        await Payment.update(
          { status: 'paid', paymentDate: new Date() },
          { where: { razorpayPaymentId: payment.id } }
        );
        console.log(`Payment captured: ${payment.id}`);
        break;
        
      case 'payment.failed':
        // Payment failed
        await Payment.update(
          { status: 'failed' },
          { where: { razorpayOrderId: payment.order_id } }
        );
        console.log(`Payment failed: ${payment.id}`);
        break;
        
      case 'payment.authorized':
        // Payment authorized but not captured
        await Payment.update(
          { status: 'attempted' },
          { where: { razorpayOrderId: payment.order_id } }
        );
        break;
        
      case 'refund.created':
        // Refund initiated
        await Payment.update(
          { status: 'refunded' },
          { where: { razorpayPaymentId: payment.payment_id } }
        );
        console.log(`Refund created for: ${payment.payment_id}`);
        break;
    }
    
    res.status(200).json({ success: true });
  } catch (error) {
    console.error('Webhook processing error:', error);
    res.status(500).json({ error: 'Webhook processing failed' });
  }
};

// Register route
router.post('/webhooks/razorpay', express.raw({ type: 'application/json' }), handleWebhook);
```

### Step 4: Monitoring and Logging
```javascript
// utils/paymentLogger.js
const winston = require('winston');

const paymentLogger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.File({ filename: 'payment-errors.log', level: 'error' }),
    new winston.transports.File({ filename: 'payments.log' })
  ]
});

module.exports = paymentLogger;

// Usage in controller
const paymentLogger = require('../utils/paymentLogger');

exports.createOrder = async (req, res) => {
  try {
    // ... order creation logic
    
    paymentLogger.info('Order created', {
      userId: userId,
      orderId: order.id,
      amount: order.amount
    });
    
  } catch (error) {
    paymentLogger.error('Order creation failed', {
      userId: userId,
      error: error.message,
      stack: error.stack
    });
  }
};
```

---

## 🧪 Testing

### Test Cards (Test Mode Only)

**Successful Payments:**
- Card: `4111 1111 1111 1111`
- CVV: Any 3 digits
- Expiry: Any future date
- Name: Any name

**Failed Payments:**
- Card: `4111 1111 1111 1112`

**Specific Error Codes:**
- Card: `5104 0600 0000 0008` - Insufficient funds
- Card: `4000 0000 0000 0002` - Declined by bank

### Testing Checklist

**Backend:**
- [ ] Order creation endpoint returns valid order ID
- [ ] Payment record is created in database with 'created' status
- [ ] Signature verification correctly validates genuine signatures
- [ ] Signature verification rejects invalid signatures
- [ ] Payment record updates to 'paid' on successful verification
- [ ] Webhook endpoint processes events correctly

**Frontend:**
- [ ] Razorpay script loads successfully
- [ ] Modal opens with correct amount
- [ ] User details pre-fill correctly
- [ ] Successful payment triggers verification
- [ ] Failed payment shows error message
- [ ] Modal closes after successful payment

**Integration:**
- [ ] End-to-end flow completes successfully
- [ ] Database reflects payment status correctly
- [ ] User receives confirmation (email/UI)
- [ ] Payment shows in Razorpay Dashboard

### Manual Testing Script
```bash
# 1. Start your server
npm run dev

# 2. Test order creation
curl -X POST http://localhost:3001/api/payments/create-order \
  -H "Content-Type: application/json" \
  -d '{"userId": "test-user-id"}'

# Expected response:
# {
#   "success": true,
#   "data": {
#     "orderId": "order_xxxxx",
#     "amount": 37500,
#     "currency": "INR",
#     "keyId": "rzp_test_xxxxx"
#   }
# }

# 3. Test signature verification (use actual values from step 2)
curl -X POST http://localhost:3001/api/payments/verify \
  -H "Content-Type: application/json" \
  -d '{
    "razorpayOrderId": "order_xxxxx",
    "razorpayPaymentId": "pay_xxxxx",
    "razorpaySignature": "generated_signature"
  }'
```

---

## 🎯 Quick Start Checklist

### Initial Setup
- [ ] Sign up on [Razorpay Dashboard](https://dashboard.razorpay.com)
- [ ] Get test API keys from Dashboard → Settings → API Keys
- [ ] Install `razorpay` npm package: `npm install razorpay`
- [ ] Create `.env` file with keys (add to `.gitignore`)
- [ ] Set up database with Payment model

### Backend Implementation
- [ ] Create `config/razorpay.js` with instance configuration
- [ ] Create `models/Payment.js` with payment schema
- [ ] Create `controllers/paymentController.js` with:
  - [ ] `createOrder` endpoint
  - [ ] `verifyPayment` endpoint with signature verification
- [ ] Create `routes/paymentRoutes.js` and register routes
- [ ] Test endpoints with curl/Postman

### Frontend Implementation
- [ ] Add Razorpay script loader in component
- [ ] Add TypeScript declarations for `window.Razorpay`
- [ ] Create payment modal component
- [ ] Implement `handlePayment` function
- [ ] Implement `handlePaymentSuccess` function
- [ ] Add error handling for payment failures

### Testing
- [ ] Test with Razorpay test cards
- [ ] Verify database updates correctly
- [ ] Test signature verification with tampered data
- [ ] Test payment failure scenarios
- [ ] Check Razorpay Dashboard for payment records

### Production
- [ ] Complete KYC on Razorpay
- [ ] Get live API keys
- [ ] Update environment variables for production
- [ ] Set up webhooks (optional but recommended)
- [ ] Add monitoring and logging
- [ ] Test with small real payment
- [ ] Monitor first few transactions closely

---

## 💡 Key Concepts

### Amount in Smallest Currency Unit
Razorpay always expects amounts in the smallest currency unit:
- **INR:** 1 Rupee = 100 paise → ₹375 = 37500 paise
- **USD:** 1 Dollar = 100 cents → $5 = 500 cents

### Order vs Payment
- **Order:** Created on your backend before payment
- **Payment:** Created by Razorpay when user completes checkout
- One order can have multiple payment attempts

### Signature Verification
```
signature = HMAC_SHA256(order_id + "|" + payment_id, secret)
```
This ensures the payment data hasn't been tampered with.

### Payment Lifecycle
```
created → attempted → paid/failed → (optionally) refunded
```

---

## 🔗 Useful Resources

- [Razorpay Official Documentation](https://razorpay.com/docs/)
- [Razorpay Node.js SDK](https://github.com/razorpay/razorpay-node)
- [Razorpay API Reference](https://razorpay.com/docs/api/)
- [Razorpay Dashboard](https://dashboard.razorpay.com)
- [Test Cards & Modes](https://razorpay.com/docs/payments/payments/test-card-details/)
- [Webhooks Guide](https://razorpay.com/docs/webhooks/)

---

## 🐛 Common Issues & Solutions

### Issue: "Invalid key_id or key_secret"
**Solution:** Verify your API keys are correct and not expired. Make sure you're using test keys in test mode.

### Issue: Signature verification failing
**Solution:** 
- Ensure you're using the correct key_secret
- Check the order of concatenation: `order_id + "|" + payment_id`
- Verify you're using HMAC SHA256

### Issue: Amount mismatch
**Solution:** Remember Razorpay uses smallest currency unit (paise for INR). Multiply rupees by 100.

### Issue: Payment success but not reflecting in database
**Solution:** 
- Check signature verification is passing
- Ensure payment update transaction completes successfully
- Check database connection and logs
- Implement webhooks for reliable status updates

### Issue: Razorpay modal not opening
**Solution:**
- Verify Razorpay script loaded: `console.log(window.Razorpay)`
- Check for JavaScript errors in console
- Ensure order creation succeeded and returned valid order_id

### Issue: CORS errors when calling backend
**Solution:**
```javascript
// Add CORS middleware
const cors = require('cors');
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true
}));
```

---

## 📊 Database Schema Reference

### Payments Table
```sql
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  razorpay_payment_id VARCHAR(255),
  razorpay_order_id VARCHAR(255) NOT NULL UNIQUE,
  amount INTEGER NOT NULL,
  currency VARCHAR(10) NOT NULL DEFAULT 'INR',
  status VARCHAR(20) NOT NULL DEFAULT 'created',
  payment_date TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CHECK (status IN ('created', 'attempted', 'paid', 'failed', 'refunded'))
);

CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_razorpay_order_id ON payments(razorpay_order_id);
CREATE INDEX idx_payments_status ON payments(status);
```

---

## 🎨 Customization Options

### Razorpay Checkout Theme
```javascript
const options = {
  // ... other options
  theme: {
    color: "#7b35b8",           // Primary color
    backdrop_color: "#000000",   // Backdrop color (with transparency)
    hide_topbar: false          // Hide the topbar
  }
};
```

### Payment Methods
```javascript
const options = {
  // ... other options
  method: {
    netbanking: true,
    card: true,
    wallet: true,
    upi: true,
    emi: false  // Disable EMI
  }
};
```

### Custom Fields
```javascript
const options = {
  // ... other options
  notes: {
    custom_field_1: "value",
    custom_field_2: "value"
  }
};
```

---

## 📝 Example: Ceneca Implementation

This guide is based on Ceneca's waitlist payment implementation with the following specifics:

- **Amount:** ₹375 (37500 paise) - Waitlist registration fee
- **Use Case:** One-time payment to join product waitlist
- **Stack:** 
  - Backend: Node.js/Express with Sequelize ORM
  - Frontend: Next.js 13+ with TypeScript
  - Database: PostgreSQL
- **Features:**
  - Transaction-based payment updates
  - User association with payments
  - Waitlist status updates on payment
  - Next.js API route proxying for security

---

## 🔐 Security Notes

1. **Never expose `key_secret` to frontend** - Only send `key_id`
2. **Always verify signature on backend** - Frontend can be manipulated
3. **Use HTTPS in production** - Required by Razorpay
4. **Store keys in environment variables** - Never hardcode
5. **Implement rate limiting** - Prevent abuse
6. **Log all payment attempts** - For audit trail
7. **Use webhooks for critical updates** - More reliable than client callbacks
8. **Validate all inputs** - Prevent injection attacks
9. **Use transactions for database updates** - Ensure data consistency
10. **Monitor for suspicious activity** - Multiple failed attempts, unusual patterns

---

**Created:** Based on Ceneca's production implementation  
**Last Updated:** January 2025  
**Status:** Production-ready guide

