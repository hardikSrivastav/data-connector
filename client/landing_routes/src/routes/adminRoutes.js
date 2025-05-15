const express = require('express');
const adminController = require('../controllers/adminController');
const { requireAuth } = require('../middlewares/auth');
const router = express.Router();

// Admin login
router.post('/login', adminController.login);

// Protected admin routes
router.get('/waitlist', requireAuth, adminController.getWaitlist);
router.patch('/waitlist/:id', requireAuth, adminController.updateWaitlist);

module.exports = router; 