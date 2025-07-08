const express = require('express');
const chatController = require('../controllers/chatController');
const router = express.Router();

// Start a new conversation
router.post('/start', chatController.startConversation);

// Send a message in a conversation
router.post('/message', chatController.sendMessage);

// Send a message in a conversation with streaming
router.post('/message/stream', chatController.sendMessageStream);

// Get conversation history
router.get('/conversation/:conversationId', chatController.getConversation);

// Generate deployment files
router.post('/generate-files', chatController.generateFiles);

// Download deployment package
router.get('/download/:conversationId', chatController.downloadDeploymentPackage);

// Get deployment template information (for debugging/testing)
router.get('/templates', chatController.getTemplateInfo);

// Health check for chat system
router.get('/health', chatController.healthCheck);

module.exports = router; 