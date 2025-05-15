const express = require('express');
const waitlistController = require('../controllers/waitlistController');
const router = express.Router();

// Register for waitlist
router.post('/register', waitlistController.register);

// Get waitlist status
router.get('/status/:userId', waitlistController.getStatus);

module.exports = router; 