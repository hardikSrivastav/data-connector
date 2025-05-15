const Razorpay = require('razorpay');

// Initialize Razorpay with the API keys
const razorpayInstance = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID || 'rzp_test_Lpk9B9aflaSSbu',
  key_secret: process.env.RAZORPAY_KEY_SECRET || 'KaUCdOrSUX70UJunkRr3097i'
});

// Fixed waitlist cost in INR (paisa)
// ₹375 = $5 (approximately)
// Note: Razorpay uses smallest currency unit (paisa for INR), so 375 INR = 37500 paisa
const WAITLIST_COST = 37500;

module.exports = {
  razorpayInstance,
  WAITLIST_COST
}; 