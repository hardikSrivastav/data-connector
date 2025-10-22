const express = require('express');
const router = express.Router();
const axios = require('axios');

const TEMPLATE_SERVICE_URL = process.env.TEMPLATE_SERVICE_URL || 'http://localhost:8501';

// Create deployment session and redirect to template editor
router.post('/create', async (req, res) => {
  try {
    const { userId, deploymentType, requirements, context } = req.body;
    
    if (!userId || !deploymentType) {
      return res.status(400).json({
        success: false,
        error: 'userId and deploymentType are required'
      });
    }
    
    // Prepare callback URL for deployment completion
    const callbackUrl = `${process.env.MAIN_APP_URL || 'http://localhost:3001'}/api/deployment/webhook`;
    
    // Create session handoff request
    const handoffRequest = {
      user_id: userId,
      deployment_type: deploymentType,
      requirements: requirements || {},
      callback_url: callbackUrl,
      context: context || {}
    };
    
    // Call template service integration API
    const response = await axios.post(
      `${TEMPLATE_SERVICE_URL}/api/integration/handoff`,
      handoffRequest,
      {
        headers: {
          'Content-Type': 'application/json'
        },
        timeout: 10000
      }
    );
    
    const { session_id, editor_url, success, message } = response.data;
    
    if (success) {
      // Store session info in database for tracking
      // TODO: Add database storage for deployment sessions
      console.log(`Created deployment session ${session_id} for user ${userId}`);
      
      res.json({
        success: true,
        sessionId: session_id,
        editorUrl: editor_url,
        message: message
      });
    } else {
      res.status(500).json({
        success: false,
        error: message
      });
    }
    
  } catch (error) {
    console.error('Error creating deployment session:', error.message);
    
    res.status(500).json({
      success: false,
      error: 'Failed to create deployment session',
      details: error.response?.data || error.message
    });
  }
});

// Webhook endpoint for deployment completion notifications
router.post('/webhook', async (req, res) => {
  try {
    const {
      session_id,
      user_id,
      status,
      generated_files,
      metadata,
      download_url
    } = req.body;
    
    console.log(`Received deployment completion webhook for session ${session_id}`);
    console.log(`Status: ${status}, User: ${user_id}`);
    
    // TODO: Store deployment completion in database
    // TODO: Send notification to user (email, in-app notification)
    // TODO: Update user's deployment history
    
    if (status === 'completed') {
      console.log(`Deployment completed successfully for user ${user_id}`);
      console.log(`Generated ${generated_files?.length || 0} files`);
      console.log(`Download URL: ${download_url}`);
      
      // Here you could:
      // 1. Save deployment record to database
      // 2. Send email notification to user
      // 3. Update user dashboard
      // 4. Log analytics event
      
    } else if (status === 'failed') {
      console.log(`Deployment failed for user ${user_id}`);
      // Handle failure case
    }
    
    // Acknowledge webhook receipt
    res.json({
      success: true,
      message: 'Webhook processed successfully',
      received_at: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Error processing deployment webhook:', error.message);
    
    res.status(500).json({
      success: false,
      error: 'Failed to process webhook',
      details: error.message
    });
  }
});

// Get deployment session status
router.get('/status/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    
    const response = await axios.get(
      `${TEMPLATE_SERVICE_URL}/api/integration/status/${sessionId}`,
      { timeout: 5000 }
    );
    
    res.json({
      success: true,
      ...response.data
    });
    
  } catch (error) {
    console.error('Error getting deployment status:', error.message);
    
    if (error.response?.status === 404) {
      res.status(404).json({
        success: false,
        error: 'Deployment session not found'
      });
    } else {
      res.status(500).json({
        success: false,
        error: 'Failed to get deployment status',
        details: error.response?.data || error.message
      });
    }
  }
});

// Download deployment files
router.get('/download/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    
    // Proxy download request to template service
    const response = await axios.get(
      `${TEMPLATE_SERVICE_URL}/api/sessions/${sessionId}/workspace`,
      {
        timeout: 30000,
        responseType: 'stream'
      }
    );
    
    // Set appropriate headers for file download
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition', `attachment; filename="deployment-${sessionId}.json"`);
    
    // Pipe the response
    response.data.pipe(res);
    
  } catch (error) {
    console.error('Error downloading deployment files:', error.message);
    
    res.status(500).json({
      success: false,
      error: 'Failed to download deployment files',
      details: error.response?.data || error.message
    });
  }
});

module.exports = router;