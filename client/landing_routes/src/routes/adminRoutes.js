const express = require('express');
const adminController = require('../controllers/adminController');
const router = express.Router();

// Admin routes (authentication removed)
router.get('/waitlist', adminController.getWaitlist);
router.patch('/waitlist/:id', adminController.updateWaitlist);

module.exports = router; 