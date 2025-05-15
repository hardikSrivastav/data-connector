const crypto = require('crypto');
const User = require('../models/User');
const Payment = require('../models/Payment');
const Waitlist = require('../models/Waitlist');
const { razorpayInstance, WAITLIST_COST } = require('../config/razorpay');
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
      amount: WAITLIST_COST,
      currency: 'INR',
      receipt: `wl_${shortUserId}_${timestamp}`,
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
      amount: WAITLIST_COST,
      currency: 'INR',
      status: 'created'
    });
    
    return res.status(200).json({
      success: true,
      data: {
        orderId: order.id,
        amount: order.amount,
        currency: order.currency,
        keyId: process.env.RAZORPAY_KEY_ID || 'rzp_test_Lpk9B9aflaSSbu'
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

/**
 * Verify and process Razorpay payment
 */
exports.verifyPayment = async (req, res) => {
  const { razorpayOrderId, razorpayPaymentId, razorpaySignature } = req.body;
  
  // Start a transaction
  const transaction = await sequelize.transaction();
  
  try {
    // Verify signature
    const generatedSignature = crypto
      .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET || 'KaUCdOrSUX70UJunkRr3097i')
      .update(razorpayOrderId + '|' + razorpayPaymentId)
      .digest('hex');
    
    if (generatedSignature !== razorpaySignature) {
      await transaction.rollback();
      return res.status(400).json({
        success: false,
        message: 'Invalid payment signature'
      });
    }
    
    // Find and update payment
    const payment = await Payment.findOne({
      where: { razorpayOrderId },
      include: [{ model: User }]
    });
    
    if (!payment) {
      await transaction.rollback();
      return res.status(404).json({
        success: false,
        message: 'Payment not found'
      });
    }
    
    // Update payment status
    await payment.update({
      razorpayPaymentId,
      status: 'paid',
      paymentDate: new Date()
    }, { transaction });
    
    // Find waitlist entry to update status
    const waitlist = await Waitlist.findOne({
      where: { userId: payment.userId }
    });
    
    if (waitlist) {
      await waitlist.update({
        status: 'pending' // Ensure status is set (redundant but explicit)
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