const { v4: uuidv4 } = require('uuid');
const { BedrockRuntimeClient, InvokeModelCommand, InvokeModelWithResponseStreamCommand } = require('@aws-sdk/client-bedrock-runtime');

// Initialize AWS Bedrock client
const bedrock = new BedrockRuntimeClient({
  region: process.env.AWS_REGION || 'ap-south-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

// Model ID for Claude 3 Sonnet
const MODEL_ID = 'anthropic.claude-3-sonnet-20240229-v1:0';

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
    
    // Get AI response from AWS Bedrock
    const aiResponse = await callBedrockModel(conversation.messages);
    
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
 * Send a message in a conversation with streaming
 */
exports.sendMessageStream = async (req, res) => {
  const { conversationId, message } = req.body;
  
  console.log('=== SENDMESSAGESTREAM CALLED ===');
  console.log('ConversationId:', conversationId);
  console.log('Message:', message);
  
  try {
    const conversation = conversations.get(conversationId);
    if (!conversation) {
      console.log('ERROR: Conversation not found');
      return res.status(404).json({
        success: false,
        message: 'Conversation not found'
      });
    }
    
    console.log('Current conversation messages before adding user message:', conversation.messages.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' })));
    
    // Add user message
    conversation.messages.push({
      role: 'user',
      content: message
    });
    
    console.log('Current conversation messages after adding user message:', conversation.messages.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' })));
    
    // Set up Server-Sent Events
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Cache-Control'
    });
    
    // Send initial status
    res.write(`data: ${JSON.stringify({
      type: 'status',
      message: 'Starting response generation...'
    })}\n\n`);
    
    let fullResponse = '';
    
    try {
      // Stream AI response from AWS Bedrock
      console.log('=== ABOUT TO CALL STREAMBEDROCK MODEL ===');
      await streamBedrockModel(conversation.messages, (chunk) => {
        console.log(`DEBUG: onChunk called with: "${chunk}"`);
        fullResponse += chunk;
        
        const chunkData = {
          type: 'chunk',
          content: chunk,
          fullContent: fullResponse
        };
        
        console.log(`DEBUG: Sending chunk to client:`, chunkData);
        
        // Send chunk to client
        res.write(`data: ${JSON.stringify(chunkData)}\n\n`);
      });
      
      console.log('DEBUG: Streaming completed, fullResponse length:', fullResponse.length);
      
      // Add complete AI response to conversation
      conversation.messages.push({
        role: 'assistant',
        content: fullResponse
      });
      
      // Extract configuration data
      extractConfigFromMessage(message, conversation.extractedConfig);
      
      conversations.set(conversationId, conversation);
      
      const completionData = {
        type: 'complete',
        message: fullResponse,
        extractedConfig: conversation.extractedConfig
      };
      
      console.log('DEBUG: Sending completion message:', completionData);
      
      // Send completion message
      res.write(`data: ${JSON.stringify(completionData)}\n\n`);
      
    } catch (streamError) {
      console.error('Error in streaming:', streamError);
      const errorData = {
        type: 'error',
        message: `Streaming error: ${streamError.message}`
      };
      
      console.log('DEBUG: Sending error message:', errorData);
      
      res.write(`data: ${JSON.stringify(errorData)}\n\n`);
    }
    
    res.end();
    
  } catch (error) {
    console.error('Error in stream setup:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to start streaming',
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
 * Call AWS Bedrock model with conversation messages
 */
async function callBedrockModel(messages) {
  try {
    // Convert messages to Claude format (exclude system messages for user conversation)
    const filteredMessages = messages.filter(msg => msg.role !== 'system');
    
    console.log('DEBUG: All messages:', messages.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' })));
    console.log('DEBUG: Filtered messages:', filteredMessages.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' })));
    
    // For Claude's Messages API, we need to ensure proper user/assistant alternation
    // If we have an initial assistant message, we need to skip it and start with user message
    let claudeMessages = [];
    
    // If the first non-system message is from assistant, skip it (it's just the welcome message)
    let startIndex = 0;
    if (filteredMessages.length > 0 && filteredMessages[0].role === 'assistant') {
      startIndex = 1;
    }
    
    // Convert remaining messages to Claude format
    for (let i = startIndex; i < filteredMessages.length; i++) {
      const msg = filteredMessages[i];
      claudeMessages.push({
        role: msg.role === 'assistant' ? 'assistant' : 'user',
        content: [
          {
            type: "text",
            text: msg.content
          }
        ]
      });
    }
    
    console.log('DEBUG: Final Claude messages:', claudeMessages.map(m => ({ role: m.role, content: m.content[0].text.substring(0, 50) + '...' })));
    
    // Ensure we have at least one user message
    if (claudeMessages.length === 0 || claudeMessages[0].role !== 'user') {
      claudeMessages = [
        {
          role: 'user',
          content: [
            {
              type: "text",
              text: 'Hello, I need help with my deployment configuration.'
            }
          ]
        },
        ...claudeMessages
      ];
    }

    // Get system message if it exists
    const systemMessage = messages.find(msg => msg.role === 'system');
    const systemContent = systemMessage ? systemMessage.content : '';

    // Prepare the request body for Claude
    const requestBody = {
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: 500,
      temperature: 0.7,
      messages: claudeMessages
    };

    // Add system message if present
    if (systemContent) {
      requestBody.system = systemContent;
    }

    console.log('DEBUG: Final request body being sent to Bedrock:', JSON.stringify(requestBody, null, 2));

    // Create the invoke command
    const command = new InvokeModelCommand({
      modelId: MODEL_ID,
      body: JSON.stringify(requestBody)
    });

    // Call Bedrock
    const response = await bedrock.send(command);
    
    // Parse response
    const responseBody = JSON.parse(new TextDecoder().decode(response.body));
    
    // Extract the assistant's response
    if (responseBody.content && responseBody.content.length > 0) {
      return responseBody.content[0].text;
    } else {
      throw new Error('No content in Bedrock response');
    }
  } catch (error) {
    console.error('Error calling Bedrock model:', error);
    throw new Error(`Bedrock API call failed: ${error.message}`);
  }
}

/**
 * Stream responses from AWS Bedrock model
 */
async function streamBedrockModel(messages, onChunk) {
  try {
    // Convert messages to Claude format (exclude system messages for user conversation)
    const filteredMessages = messages.filter(msg => msg.role !== 'system');
    
    console.log('DEBUG: All messages:', messages.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' })));
    console.log('DEBUG: Filtered messages:', filteredMessages.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' })));
    
    // For Claude's Messages API, we need to ensure proper user/assistant alternation
    // If we have an initial assistant message, we need to skip it and start with user message
    let claudeMessages = [];
    
    // If the first non-system message is from assistant, skip it (it's just the welcome message)
    let startIndex = 0;
    if (filteredMessages.length > 0 && filteredMessages[0].role === 'assistant') {
      startIndex = 1;
    }
    
    // Convert remaining messages to Claude format
    for (let i = startIndex; i < filteredMessages.length; i++) {
      const msg = filteredMessages[i];
      claudeMessages.push({
        role: msg.role === 'assistant' ? 'assistant' : 'user',
        content: [
          {
            type: "text",
            text: msg.content
          }
        ]
      });
    }
    
    console.log('DEBUG: Final Claude messages:', claudeMessages.map(m => ({ role: m.role, content: m.content[0].text.substring(0, 50) + '...' })));
    
    // Ensure we have at least one user message
    if (claudeMessages.length === 0 || claudeMessages[0].role !== 'user') {
      claudeMessages = [
        {
          role: 'user',
          content: [
            {
              type: "text",
              text: 'Hello, I need help with my deployment configuration.'
            }
          ]
        },
        ...claudeMessages
      ];
    }

    // Get system message if it exists
    const systemMessage = messages.find(msg => msg.role === 'system');
    const systemContent = systemMessage ? systemMessage.content : '';

    // Prepare the request body for Claude streaming
    const requestBody = {
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: 500,
      temperature: 0.7,
      messages: claudeMessages
    };

    // Add system message if present
    if (systemContent) {
      requestBody.system = systemContent;
    }

    console.log('DEBUG: Final request body being sent to Bedrock:', JSON.stringify(requestBody, null, 2));

    // Create the streaming invoke command
    const command = new InvokeModelWithResponseStreamCommand({
      modelId: MODEL_ID,
      body: JSON.stringify(requestBody)
    });

    // Call Bedrock with streaming
    const response = await bedrock.send(command);
    
    // Process the streaming response
    if (response.body) {
      console.log('DEBUG: Starting to process streaming response');
      let chunkCount = 0;
      
      for await (const chunk of response.body) {
        chunkCount++;
        console.log(`DEBUG: Processing chunk ${chunkCount}:`, chunk);
        
        if (chunk.chunk && chunk.chunk.bytes) {
          const chunkData = JSON.parse(new TextDecoder().decode(chunk.chunk.bytes));
          console.log(`DEBUG: Chunk ${chunkCount} data:`, chunkData);
          
          // Handle different types of chunks
          if (chunkData.type === 'content_block_delta' && chunkData.delta && chunkData.delta.text) {
            // This is a text chunk from Claude
            const textChunk = chunkData.delta.text;
            console.log(`DEBUG: Found text chunk: "${textChunk}"`);
            onChunk(textChunk);
          } else if (chunkData.type === 'message_delta' && chunkData.delta && chunkData.delta.stop_reason) {
            // This indicates the end of the stream
            console.log('Stream completed with stop reason:', chunkData.delta.stop_reason);
          } else {
            console.log(`DEBUG: Unknown chunk type: ${chunkData.type}`);
          }
        } else {
          console.log(`DEBUG: Chunk ${chunkCount} has no bytes:`, chunk);
        }
      }
      
      console.log(`DEBUG: Finished processing ${chunkCount} chunks`);
    } else {
      throw new Error('No streaming body in Bedrock response');
    }
  } catch (error) {
    console.error('Error streaming from Bedrock model:', error);
    throw new Error(`Bedrock streaming failed: ${error.message}`);
  }
}

/**
 * Health check for chat system
 */
exports.healthCheck = async (req, res) => {
  return res.status(200).json({
    success: true,
    message: 'Chat system is healthy',
    data: {
      activeConversations: conversations.size,
      bedrockConfigured: !!(process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY && process.env.AWS_REGION)
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