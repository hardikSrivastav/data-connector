const express = require('express');
const router = express.Router();
const chatController = require('../controllers/chatController');

// Chat endpoints
router.post('/start', chatController.startConversation);
router.post('/message', chatController.sendMessage);
router.post('/message/stream', chatController.sendMessageStream);
router.post('/generate-files', chatController.generateFiles);

// Template introspection endpoint for debugging
router.get('/template-analysis', chatController.getTemplateIntrospection);

// Test LangGraph tools functionality
router.get('/test-tools', chatController.testTools);

// Test tools directly without LangGraph agent
router.get('/test-tools-direct', chatController.testToolsDirect);

module.exports = router; 