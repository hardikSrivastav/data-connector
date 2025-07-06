const express = require('express');
const chatController = require('../controllers/chatController');
const router = express.Router();

// Start a new conversation
router.post('/start', chatController.startConversation);

// Send a message in a conversation
router.post('/message', chatController.sendMessage);

// Get conversation history
router.get('/conversation/:conversationId', chatController.getConversation);

// Generate deployment files
router.post('/generate-files', chatController.generateFiles);

// Health check for chat system
router.get('/health', chatController.healthCheck);

module.exports = router; 