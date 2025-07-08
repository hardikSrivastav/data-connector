const { v4: uuidv4 } = require('uuid');
const { BedrockRuntimeClient, InvokeModelCommand, InvokeModelWithResponseStreamCommand } = require('@aws-sdk/client-bedrock-runtime');
const DeploymentGenerator = require('../services/deploymentGenerator');

// Initialize AWS Bedrock client
const bedrock = new BedrockRuntimeClient({
  region: process.env.AWS_REGION || 'ap-south-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

// Model ID for Claude 3 Haiku (Messages API) - Stable and fast
const MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0';

// In-memory storage for conversations (you can migrate to database later)
const conversations = new Map();

// Initialize deployment generator
const deploymentGenerator = new DeploymentGenerator();

// Initialize deployment generator on server start
(async () => {
  try {
    await deploymentGenerator.initialize();
    console.log('Deployment generator ready for conversations');
  } catch (error) {
    console.error('Failed to initialize deployment generator:', error);
  }
})();

/**
 * Enhanced system prompt that understands deployment templates and extracts requirements
 */
async function getSystemPrompt(userInfo) {
  // Get available template requirements dynamically
  let templateRequirements = {};
  try {
    templateRequirements = await deploymentGenerator.getAvailableTemplates();
  } catch (error) {
    console.warn('Could not load template requirements:', error.message);
  }

  return `You are a technical consultant specializing in Ceneca deployment configuration. Your goal is to help users configure their deployment through natural conversation while intelligently extracting the information needed to fill deployment templates.

PERSONALITY:
- Knowledgeable but not condescending
- Ask clarifying questions when needed
- Explain the "why" behind recommendations
- Adapt to user's technical level

CAPABILITIES:
- Understand infrastructure contexts (databases, auth, networking)
- Recommend best practices for enterprise deployments
- Extract deployment requirements from natural language
- Provide technical explanations for configuration choices

DEPLOYMENT TEMPLATE AWARENESS:
You have access to real deployment templates that need the following information:
${JSON.stringify(templateRequirements, null, 2)}

Your job is to gather this information through natural conversation. When users mention:
- Database names/hosts: Extract connection details
- Authentication providers: Extract SSO configuration
- Domain names: Note for SSL and networking setup
- Team sizes: Recommend appropriate scaling
- Environment types: Suggest production vs development settings

CONVERSATION STYLE:
- Start with understanding their business scenario
- Ask about their existing infrastructure
- Recommend configurations based on their needs
- Explain trade-offs and best practices
- Confirm understanding before proceeding

USER CONTEXT:
${JSON.stringify(userInfo)}

IMPORTANT: Extract technical details naturally without making it feel like a form. Focus on understanding their use case first, then gather the technical requirements.`;
}

/**
 * Start a new conversation
 */
exports.startConversation = async (req, res) => {
  const { userInfo } = req.body;
  
  try {
    const conversationId = uuidv4();
    const systemPrompt = await getSystemPrompt(userInfo);
    
    // Initialize conversation with enhanced context
    conversations.set(conversationId, {
      id: conversationId,
      userInfo,
      messages: [],
      extractedConfig: {
        databases: {},
        authentication: {},
        deployment: {},
        confidence: {}
      },
      systemPrompt,
      createdAt: new Date(),
      lastUpdated: new Date()
    });

    const welcomeMessage = `Hi! I'm here to help you set up Ceneca for your infrastructure. I'll ask you some questions about your setup to create a personalized deployment package.

To get started, could you tell me about your current data infrastructure? What databases are you using, and what's your primary use case for Ceneca?`;

    res.json({
      success: true,
      data: {
        conversationId,
        message: welcomeMessage
      }
    });
  } catch (error) {
    console.error('Error starting conversation:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to start conversation'
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
      content: message,
      timestamp: new Date()
    });

    // Build conversation context for AI
    const conversationHistory = [
      { role: 'system', content: conversation.systemPrompt },
      ...conversation.messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    ];

    // Get AI response
    const response = await invokeBedrockModel(conversationHistory);
    
    // Add AI response to conversation
    conversation.messages.push({
      role: 'assistant',
      content: response,
      timestamp: new Date()
    });

    // Extract configuration from the conversation
    const extractedConfig = deploymentGenerator.conversationExtractor.extractFromConversation(
      conversation.messages, 
      conversation.extractedConfig
    );
    
    conversation.extractedConfig = extractedConfig;
    conversation.lastUpdated = new Date();

    res.json({
      success: true,
      data: {
        message: response,
        extractedConfig: extractedConfig,
        conversationId: conversationId
      }
    });

  } catch (error) {
    console.error('Error sending message:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to send message'
    });
  }
};

/**
 * Send a message with streaming response
 */
exports.sendMessageStream = async (req, res) => {
  const { conversationId, message } = req.body;
  
  try {
    const conversation = conversations.get(conversationId);
    if (!conversation) {
      return res.status(404).json({
        success: false,
        message: 'Conversation not found'
      });
    }

    // Set up SSE headers
    res.writeHead(200, {
      'Content-Type': 'text/plain',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Cache-Control'
    });

    // Add user message
    conversation.messages.push({
      role: 'user',
      content: message,
      timestamp: new Date()
    });

    // Build conversation context
    const conversationHistory = [
      { role: 'system', content: conversation.systemPrompt },
      ...conversation.messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    ];

    // Stream AI response
    let fullResponse = '';
    await streamBedrockModel(conversationHistory, (chunk) => {
      fullResponse += chunk;
      res.write(`data: ${JSON.stringify({ 
        type: 'chunk', 
        content: chunk,
        fullContent: fullResponse 
      })}\n\n`);
    });

    // Add AI response to conversation
    conversation.messages.push({
      role: 'assistant',
      content: fullResponse,
      timestamp: new Date()
    });

    // Extract configuration from the conversation
    const extractedConfig = deploymentGenerator.conversationExtractor.extractFromConversation(
      conversation.messages, 
      conversation.extractedConfig
    );
    
    conversation.extractedConfig = extractedConfig;
    conversation.lastUpdated = new Date();

    // Send completion message
    res.write(`data: ${JSON.stringify({
      type: 'complete',
      message: fullResponse,
      extractedConfig: extractedConfig,
      conversationId: conversationId
    })}\n\n`);

    res.end();

  } catch (error) {
    console.error('Error in streaming message:', error);
    res.write(`data: ${JSON.stringify({
      type: 'error',
      message: 'Failed to process message'
    })}\n\n`);
    res.end();
  }
};

/**
 * Generate deployment files from conversation
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

    // Generate deployment package using the new template-based system
    const result = await deploymentGenerator.generateFromConversation(
      conversation.messages,
      conversation.extractedConfig
    );

    // Store the generated package in conversation for download
    conversation.generatedPackage = result.deploymentPackage;
    conversation.lastUpdated = new Date();

    res.json({
      success: true,
      data: {
        message: `Successfully generated ${Object.keys(result.deploymentPackage.files).length} deployment files`,
        filesGenerated: Object.keys(result.deploymentPackage.files),
        confidence: result.extractedConfig.confidence,
        metadata: result.metadata
      }
    });

  } catch (error) {
    console.error('Error generating deployment files:', error);
    res.status(500).json({
      success: false,
      message: error.message || 'Failed to generate deployment files'
    });
  }
};

/**
 * Download generated deployment package
 */
exports.downloadDeploymentPackage = async (req, res) => {
  const { conversationId } = req.params;
  
  try {
    const conversation = conversations.get(conversationId);
    if (!conversation || !conversation.generatedPackage) {
      return res.status(404).json({
        success: false,
        message: 'Deployment package not found. Please generate files first.'
      });
    }

    const deploymentPackage = conversation.generatedPackage;
    
    // Create a simple multi-file response (in production, you'd create a ZIP)
    let packageContent = `# Ceneca Deployment Package
# Generated on: ${deploymentPackage.metadata.generatedAt}
# Files included: ${Object.keys(deploymentPackage.files).length}

`;

    for (const [filename, content] of Object.entries(deploymentPackage.files)) {
      packageContent += `# ============================================================
# FILE: ${filename}
# ============================================================

${content}

`;
    }

    res.setHeader('Content-Type', 'text/plain');
    res.setHeader('Content-Disposition', `attachment; filename="ceneca-deployment-${conversationId.slice(0, 8)}.txt"`);
    res.send(packageContent);

  } catch (error) {
    console.error('Error downloading deployment package:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to download deployment package'
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

    res.json({
      success: true,
      data: {
        conversationId: conversation.id,
        messages: conversation.messages,
        extractedConfig: conversation.extractedConfig,
        hasGeneratedPackage: !!conversation.generatedPackage,
        createdAt: conversation.createdAt,
        lastUpdated: conversation.lastUpdated
      }
    });
  } catch (error) {
    console.error('Error getting conversation:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to get conversation'
    });
  }
};

/**
 * Get template analysis for debugging
 */
exports.getTemplateInfo = async (req, res) => {
  try {
    const analysis = await deploymentGenerator.getTemplateAnalysis();
    
    res.json({
      success: true,
      data: analysis
    });
  } catch (error) {
    console.error('Error getting template info:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to get template information'
    });
  }
};

/**
 * Health check for chat system
 */
exports.healthCheck = async (req, res) => {
  try {
    // Check if deployment generator is initialized
    const isInitialized = deploymentGenerator.isInitialized;
    
    // Get basic system info
    const systemInfo = {
      chatSystem: 'operational',
      deploymentGenerator: isInitialized ? 'initialized' : 'initializing',
      conversationsActive: conversations.size,
      timestamp: new Date().toISOString()
    };

    if (isInitialized) {
      // Get template information if available
      try {
        const templates = await deploymentGenerator.getAvailableTemplates();
        systemInfo.templatesLoaded = Object.keys(templates).length;
      } catch (error) {
        systemInfo.templatesLoaded = 'error loading';
      }
    }

    res.json({
      success: true,
      status: 'healthy',
      data: systemInfo
    });
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({
      success: false,
      status: 'unhealthy',
      message: error.message
    });
  }
};

/**
 * Invoke Bedrock model for regular response
 */
async function invokeBedrockModel(messages) {
  const params = {
    modelId: MODEL_ID,
    contentType: 'application/json',
    accept: 'application/json',
    body: JSON.stringify({
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: 2000,
      temperature: 0.7,
      top_p: 0.9,
      messages: formatMessagesForAnthropic(messages)
    })
  };

  const command = new InvokeModelCommand(params);
  const response = await bedrock.send(command);
  
  const responseBody = JSON.parse(new TextDecoder().decode(response.body));
  return responseBody.content[0].text;
}

/**
 * Stream Bedrock model response
 */
async function streamBedrockModel(messages, onChunk) {
  const params = {
    modelId: MODEL_ID,
    contentType: 'application/json',
    accept: 'application/json',
    body: JSON.stringify({
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: 2000,
      temperature: 0.7,
      top_p: 0.9,
      messages: formatMessagesForAnthropic(messages)
    })
  };

  const command = new InvokeModelWithResponseStreamCommand(params);
  const response = await bedrock.send(command);

  if (response.body) {
    for await (const chunk of response.body) {
      if (chunk.chunk?.bytes) {
        const chunkData = JSON.parse(new TextDecoder().decode(chunk.chunk.bytes));
        if (chunkData.type === 'content_block_delta' && chunkData.delta?.text) {
          onChunk(chunkData.delta.text);
        }
      }
    }
  }
}

/**
 * Format messages for Anthropic Messages API
 */
function formatMessagesForAnthropic(messages) {
  const formattedMessages = [];
  let systemMessage = '';
  
  // Extract system message and format conversation messages
  for (const message of messages) {
    if (message.role === 'system') {
      systemMessage = message.content;
    } else if (message.role === 'user' || message.role === 'assistant') {
      formattedMessages.push({
        role: message.role,
        content: message.content
      });
    }
  }
  
  // Add system message to the first message if it exists
  if (systemMessage && formattedMessages.length > 0) {
    formattedMessages[0] = {
      ...formattedMessages[0],
      content: `${systemMessage}\n\n${formattedMessages[0].content}`
    };
  }
  
  return formattedMessages;
} 