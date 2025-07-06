const { v4: uuidv4 } = require('uuid');
const OpenAI = require('openai');

// Initialize OpenAI (you'll need to add your API key to .env)
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// In-memory storage for conversations (you can migrate to database later)
const conversations = new Map();

/**
 * Start a new conversation
 */
exports.startConversation = async (req, res) => {
  try {
    const conversationId = uuidv4();
    const { userInfo } = req.body; // License key, company info, etc.
    
    // Initialize conversation with system context
    const conversation = {
      id: conversationId,
      userInfo,
      messages: [
        {
          role: 'system',
          content: `You are a deployment configuration assistant for Ceneca, an enterprise data platform. 
          Your job is to help users configure their on-premise deployment by asking questions and providing guidance.
          
          User Info: ${JSON.stringify(userInfo)}
          
          Be conversational, ask follow-up questions, and help them understand their deployment options.
          Focus on: database connections, authentication (SSO), scaling requirements, and security needs.`
        },
        {
          role: 'assistant',
          content: `Hi! I'm here to help you configure your Ceneca deployment. I can see you're setting up for ${userInfo?.company || 'your organization'}. 
          
          Let's start with the basics - what databases are you planning to connect to? Are you using PostgreSQL, MySQL, MongoDB, or something else?`
        }
      ],
      createdAt: new Date(),
      extractedConfig: {}
    };
    
    conversations.set(conversationId, conversation);
    
    return res.status(200).json({
      success: true,
      data: {
        conversationId,
        message: conversation.messages[conversation.messages.length - 1].content
      }
    });
  } catch (error) {
    console.error('Error starting conversation:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to start conversation',
      error: error.message
    });
  }
};

/**
 * Send a message in a conversation
 */
exports.sendMessage = async (req, res) => {
  const { conversationId, message } = req.body;
  
  try {
    const conversation = conversations.get(conversationId);
    if (!conversation) {
      return res.status(404).json({
        success: false,
        message: 'Conversation not found'
      });
    }
    
    // Add user message
    conversation.messages.push({
      role: 'user',
      content: message
    });
    
    // Get AI response
    const response = await openai.chat.completions.create({
      model: 'gpt-4',
      messages: conversation.messages,
      temperature: 0.7,
      max_tokens: 500
    });
    
    const aiResponse = response.choices[0].message.content;
    
    // Add AI response to conversation
    conversation.messages.push({
      role: 'assistant',
      content: aiResponse
    });
    
    // Extract configuration data (basic pattern matching for now)
    extractConfigFromMessage(message, conversation.extractedConfig);
    
    conversations.set(conversationId, conversation);
    
    return res.status(200).json({
      success: true,
      data: {
        message: aiResponse,
        extractedConfig: conversation.extractedConfig
      }
    });
  } catch (error) {
    console.error('Error sending message:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to send message',
      error: error.message
    });
  }
};

/**
 * Get conversation history
 */
exports.getConversation = async (req, res) => {
  const { conversationId } = req.params;
  
  try {
    const conversation = conversations.get(conversationId);
    if (!conversation) {
      return res.status(404).json({
        success: false,
        message: 'Conversation not found'
      });
    }
    
    return res.status(200).json({
      success: true,
      data: {
        conversationId,
        messages: conversation.messages.filter(msg => msg.role !== 'system'),
        extractedConfig: conversation.extractedConfig
      }
    });
  } catch (error) {
    console.error('Error fetching conversation:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to fetch conversation',
      error: error.message
    });
  }
};

/**
 * Generate deployment files based on extracted configuration
 */
exports.generateFiles = async (req, res) => {
  const { conversationId } = req.body;
  
  try {
    const conversation = conversations.get(conversationId);
    if (!conversation) {
      return res.status(404).json({
        success: false,
        message: 'Conversation not found'
      });
    }
    
    // TODO: Implement template processing here
    // For now, return the extracted configuration
    
    return res.status(200).json({
      success: true,
      data: {
        config: conversation.extractedConfig,
        message: 'Configuration extracted successfully. File generation coming soon!'
      }
    });
  } catch (error) {
    console.error('Error generating files:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to generate files',
      error: error.message
    });
  }
};

/**
 * Health check for chat system
 */
exports.healthCheck = async (req, res) => {
  return res.status(200).json({
    success: true,
    message: 'Chat system is healthy',
    data: {
      activeConversations: conversations.size,
      openaiConfigured: !!process.env.OPENAI_API_KEY
    }
  });
};

/**
 * Helper function to extract configuration from user messages
 */
function extractConfigFromMessage(message, config) {
  const lowerMessage = message.toLowerCase();
  
  // Database detection
  if (lowerMessage.includes('postgresql') || lowerMessage.includes('postgres')) {
    config.databases = config.databases || [];
    if (!config.databases.includes('postgresql')) {
      config.databases.push('postgresql');
    }
  }
  
  if (lowerMessage.includes('mongodb') || lowerMessage.includes('mongo')) {
    config.databases = config.databases || [];
    if (!config.databases.includes('mongodb')) {
      config.databases.push('mongodb');
    }
  }
  
  if (lowerMessage.includes('mysql')) {
    config.databases = config.databases || [];
    if (!config.databases.includes('mysql')) {
      config.databases.push('mysql');
    }
  }
  
  // Authentication detection
  if (lowerMessage.includes('okta')) {
    config.auth = 'okta';
  } else if (lowerMessage.includes('azure') || lowerMessage.includes('microsoft')) {
    config.auth = 'azure';
  } else if (lowerMessage.includes('google')) {
    config.auth = 'google';
  } else if (lowerMessage.includes('auth0')) {
    config.auth = 'auth0';
  }
  
  // Environment detection
  if (lowerMessage.includes('production') || lowerMessage.includes('prod')) {
    config.environment = 'production';
  } else if (lowerMessage.includes('development') || lowerMessage.includes('dev')) {
    config.environment = 'development';
  } else if (lowerMessage.includes('staging')) {
    config.environment = 'staging';
  }
  
  // Scale detection
  if (lowerMessage.includes('high traffic') || lowerMessage.includes('thousands')) {
    config.scale = 'high';
  } else if (lowerMessage.includes('small') || lowerMessage.includes('few users')) {
    config.scale = 'small';
  }
} 