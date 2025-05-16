const express = require('express');
const waitlistController = require('../controllers/waitlistController');
const router = express.Router();

// Register for waitlist
router.post('/register', waitlistController.register);

// Get waitlist status by ID
router.get('/status/:userId', waitlistController.getStatus);

// Check waitlist status by email (POST)
router.post('/check-status', waitlistController.checkStatusByEmail);

module.exports = router; 