const express = require('express');
const paymentController = require('../controllers/paymentController');
const router = express.Router();

// Create order
router.post('/create-order', paymentController.createOrder);

// Verify payment
router.post('/verify', paymentController.verifyPayment);

module.exports = router; 