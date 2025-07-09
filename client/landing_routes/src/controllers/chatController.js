const { v4: uuidv4 } = require('uuid');
const { BedrockRuntimeClient, InvokeModelCommand, InvokeModelWithResponseStreamCommand } = require('@aws-sdk/client-bedrock-runtime');
const DeploymentGenerator = require('../services/deploymentGenerator');
const BedrockToolsAgent = require('../services/bedrockToolsAgent');
const PromptRenderer = require('../services/promptRenderer');

// Redis-based persistence services
const sessionManager = require('../services/sessionManager');
const conversationStorage = require('../services/conversationStorage');
const redisService = require('../services/redisService');

// Initialize AWS Bedrock client (keeping for fallback)
const bedrock = new BedrockRuntimeClient({
  region: process.env.AWS_REGION || 'ap-south-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

// Model ID for Claude 3 Haiku (Messages API) - Stable and fast
const MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0';

// Initialize deployment generator
const deploymentGenerator = new DeploymentGenerator();

// Initialize agents
const bedrockToolsAgent = new BedrockToolsAgent();

// Initialize prompt renderer
const promptRenderer = new PromptRenderer();

// Initialize all systems on server start
(async () => {
  try {
    await deploymentGenerator.initialize();
    console.log('Deployment generator ready for conversations');
    
    // Try to initialize Bedrock Tools agent (uses existing AWS creds)
    try {
      await bedrockToolsAgent.initialize();
      console.log('Bedrock Tools agent ready for conversations');
    } catch (error) {
      console.warn('Bedrock Tools agent failed to initialize:', error.message);
    }
  } catch (error) {
    console.error('Failed to initialize systems:', error);
  }
})();

/**
 * Get detailed template analysis for introspection
 */
exports.getTemplateIntrospection = async (req, res) => {
  try {
    await deploymentGenerator.ensureInitialized();
    const analysis = await deploymentGenerator.getTemplateAnalysis();
    
    res.json({
      success: true,
      data: analysis
    });
  } catch (error) {
    console.error('Error getting template introspection:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to analyze templates'
    });
  }
};

/**
 * Enhanced system prompt that understands deployment templates and extracts requirements
 * Now conversation-aware to only ask about relevant databases
 * Enhanced with Bedrock tool capabilities
 * Uses Jinja templating for better maintainability
 */
async function getSystemPrompt(userInfo, userMessage = null) {
  // Get available tools information
  let availableTools = [];
  try {
    if (bedrockToolsAgent.isInitialized) {
      availableTools = bedrockToolsAgent.getAvailableTools();
    }
  } catch (error) {
    console.warn('Could not get tools info:', error.message);
  }

  // Extract contextual requirements from user message
  let contextualRequirements = null;
  if (userMessage) {
    try {
      contextualRequirements = promptRenderer.extractContextualRequirements(userMessage);
    } catch (error) {
      console.warn('Could not extract contextual requirements:', error.message);
    }
  }

  // Render the system prompt using Jinja template
  try {
    return promptRenderer.renderDeploymentAssistant({
      availableTools,
      userInfo,
      userMessage,
      contextualRequirements
    });
  } catch (error) {
    console.error('Error rendering system prompt:', error);
    // Fallback to basic prompt if template fails
    return `You are a deployment configuration assistant for Ceneca. Your job is to systematically configure a COMPLETE deployment package by transparently introspecting and updating existing template files in the deploy-reference folder.

AVAILABLE TOOLS:
${availableTools.map(tool => `- ${tool.name}: ${tool.description.trim()}`).join('\n')}

GOAL: Complete deployment package ready for download, not just answering one question.

USER CONTEXT:
${JSON.stringify(userInfo)}`;
  }
}



/**
 * Start a new conversation or recover existing one
 */
exports.startConversation = async (req, res) => {
  const { userInfo, conversationId: existingConversationId } = req.body;
  
  try {
    // If conversation ID provided, try to recover existing session
    if (existingConversationId) {
      const sessionValidation = await sessionManager.validateSession(existingConversationId);
      
      if (sessionValidation.valid) {
        const existingConversation = await conversationStorage.loadConversation(existingConversationId);
        
        if (existingConversation) {
          console.log(`Recovered existing conversation: ${existingConversationId}`);
          
          return res.json({
            success: true,
            data: {
              conversationId: existingConversationId,
              message: 'Welcome back! Your conversation has been restored.',
              isRecovered: true,
              messageCount: existingConversation.messages.length,
              extractedConfig: existingConversation.extractedConfig
            }
          });
        }
      }
      
      // If recovery failed, log the reason and create new conversation
      console.log(`Failed to recover conversation ${existingConversationId}: ${sessionValidation.reason || 'conversation not found'}`);
    }

    // Create new session and conversation
    const sessionResult = await sessionManager.createSession(userInfo);
    const conversationId = sessionResult.conversationId;
    const systemPrompt = await getSystemPrompt(userInfo);
    
    // Initialize conversation with enhanced context
    const conversationData = {
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
    };

    // Save conversation to storage
    await conversationStorage.saveConversation(conversationId, conversationData);

    const welcomeMessage = `Hi! I'm here to help you set up Ceneca for your infrastructure. I'll ask you some questions about your setup to create a personalized deployment package.

To get started, could you tell me about your current data infrastructure? What databases are you using, and what's your primary use case for Ceneca?`;

    res.json({
      success: true,
      data: {
        conversationId,
        message: welcomeMessage,
        isRecovered: false,
        storageType: redisService.isAvailable() ? 'redis' : 'memory'
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
    // Validate session and load conversation
    const sessionValidation = await sessionManager.validateSession(conversationId);
    if (!sessionValidation.valid) {
      return res.status(404).json({
        success: false,
        message: `Session invalid: ${sessionValidation.reason}`
      });
    }

    const conversation = await conversationStorage.loadConversation(conversationId);
    if (!conversation) {
      return res.status(404).json({
        success: false,
        message: 'Conversation not found'
      });
    }
    
    // Add user message
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date()
    };

    await conversationStorage.addMessage(conversationId, userMessage);

    // Update conversation object for processing
    conversation.messages.push(userMessage);

    // Regenerate system prompt based on user's first message to filter relevant requirements
    let systemPrompt = conversation.systemPrompt;
    if (conversation.messages.length === 1) {
      // This is the first user message, regenerate system prompt with filtered requirements
      systemPrompt = await getSystemPrompt(conversation.userInfo, message);
      await conversationStorage.updateConversation(conversationId, { systemPrompt });
      conversation.systemPrompt = systemPrompt;
    }

    // Build conversation context for AI
    const conversationHistory = [
      { role: 'system', content: systemPrompt },
      ...conversation.messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    ];

    // Get AI response using tools-capable agents (priority order)
    let response;
    if (bedrockToolsAgent.isInitialized) {
      // Use Bedrock Tools agent (preferred - uses existing AWS creds)
      response = await bedrockToolsAgent.processMessage(
        systemPrompt,
        message,
        conversation.messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      );
    } else {
      // Fallback to basic Bedrock (no tools)
      console.log('Bedrock Tools agent not available, falling back to basic Bedrock');
      const aiResponse = await invokeBedrockModel(conversationHistory);
      response = {
        content: aiResponse,
        toolCalls: []
      };
    }
    
    // Add AI response to conversation storage
    const assistantMessage = {
      role: 'assistant',
      content: response.content,
      timestamp: new Date(),
      toolCalls: response.toolCalls || []
    };

    await conversationStorage.addMessage(conversationId, assistantMessage);

    // Extract configuration from the conversation
    const extractedConfig = deploymentGenerator.conversationExtractor.extractFromConversation(
      [...conversation.messages, assistantMessage], 
      conversation.extractedConfig
    );
    
    // Update extracted config in storage
    await conversationStorage.updateExtractedConfig(conversationId, extractedConfig);

    res.json({
      success: true,
      data: {
        message: response.content,
        extractedConfig: extractedConfig,
        conversationId: conversationId,
        toolCalls: response.toolCalls || [],
        storageType: redisService.isAvailable() ? 'redis' : 'memory'
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
    // Validate session and load conversation
    const sessionValidation = await sessionManager.validateSession(conversationId);
    if (!sessionValidation.valid) {
      return res.status(404).json({
        success: false,
        message: `Session invalid: ${sessionValidation.reason}`
      });
    }

    const conversation = await conversationStorage.loadConversation(conversationId);
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
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date()
    };

    await conversationStorage.addMessage(conversationId, userMessage);

    // Update conversation object for processing
    conversation.messages.push(userMessage);

    // Regenerate system prompt based on user's first message to filter relevant requirements
    let systemPrompt = conversation.systemPrompt;
    if (conversation.messages.length === 1) {
      // This is the first user message, regenerate system prompt with filtered requirements
      systemPrompt = await getSystemPrompt(conversation.userInfo, message);
      await conversationStorage.updateConversation(conversationId, { systemPrompt });
      conversation.systemPrompt = systemPrompt;
    }

    // Build conversation context for AI
    const conversationHistory = [
      { role: 'system', content: systemPrompt },
      ...conversation.messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    ];

    let fullContent = '';
    let hasError = false;
    
    try {
      // Stream AI response using tools-capable agents (priority order)
      let response;
      if (bedrockToolsAgent.isInitialized) {
        // Use Bedrock Tools agent streaming
        response = await bedrockToolsAgent.processMessageStream(
          systemPrompt,
          message,
          conversation.messages.map(msg => ({
            role: msg.role,
            content: msg.content
          })),
          (data) => {
            // Handle different types of data from the agent
            if (typeof data === 'string') {
              // Regular content chunk
              if (data.includes('[TOOL CALL]')) {
                // Tool call notification
                const toolMatch = data.match(/\[TOOL CALL\] (.+?): (.+)/);
                if (toolMatch) {
                  res.write(`data: ${JSON.stringify({
                    type: 'tool_call',
                    toolName: toolMatch[1],
                    toolArgs: toolMatch[2]
                  })}\n\n`);
                }
              } else if (data.includes('[TOOL RESULT]')) {
                // Tool result notification
                const resultMatch = data.match(/\[TOOL RESULT\] (.+)/);
                if (resultMatch) {
                  res.write(`data: ${JSON.stringify({
                    type: 'tool_result',
                    result: resultMatch[1]
                  })}\n\n`);
                }
              } else {
                // Regular content
                fullContent += data;
                res.write(`data: ${JSON.stringify({
                  type: 'chunk',
                  content: data,
                  fullContent: fullContent
                })}\n\n`);
              }
            }
          }
        );
      } else {
        // Fallback to basic Bedrock streaming
        console.log('Bedrock Tools agent not available, falling back to basic Bedrock streaming');
        await streamBedrockModel(conversationHistory, (chunk) => {
          fullContent += chunk;
          res.write(`data: ${JSON.stringify({
            type: 'chunk',
            content: chunk,
            fullContent: fullContent
          })}\n\n`);
        });
        response = {
          content: fullContent,
          toolCalls: []
        };
      }
      
      // Add AI response to conversation storage
      const assistantMessage = {
        role: 'assistant',
        content: response.content,
        timestamp: new Date(),
        toolCalls: response.toolCalls || []
      };

      await conversationStorage.addMessage(conversationId, assistantMessage);

      // Extract configuration from the conversation
      const extractedConfig = deploymentGenerator.conversationExtractor.extractFromConversation(
        [...conversation.messages, assistantMessage], 
        conversation.extractedConfig
      );
      
      // Update extracted config in storage
      await conversationStorage.updateExtractedConfig(conversationId, extractedConfig);

      // Send completion message
      res.write(`data: ${JSON.stringify({
        type: 'complete',
        message: response.content,
        extractedConfig: extractedConfig,
        conversationId: conversationId,
        toolCalls: response.toolCalls || [],
        storageType: redisService.isAvailable() ? 'redis' : 'memory'
      })}\n\n`);
      
    } catch (streamError) {
      console.error('Streaming error:', streamError);
      hasError = true;
      res.write(`data: ${JSON.stringify({
        type: 'error',
        message: 'Failed to get AI response'
      })}\n\n`);
    }
    
    res.end();

  } catch (error) {
    console.error('Error in stream message:', error);
    try {
      res.write(`data: ${JSON.stringify({
        type: 'error',
        message: 'Failed to process message'
      })}\n\n`);
      res.end();
    } catch (endError) {
      console.error('Error ending response:', endError);
    }
  }
};

/**
 * Generate deployment files from conversation
 */
exports.generateFiles = async (req, res) => {
  const { conversationId } = req.body;
  
  try {
    // Validate session and load conversation
    const sessionValidation = await sessionManager.validateSession(conversationId);
    if (!sessionValidation.valid) {
      return res.status(404).json({
        success: false,
        message: `Session invalid: ${sessionValidation.reason}`
      });
    }

    const conversation = await conversationStorage.loadConversation(conversationId);
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

    // Store the generated package in conversation storage
    const deploymentPath = `deploy-packages/${conversationId}`;
    await conversationStorage.updateGeneratedPackage(
      conversationId, 
      result.deploymentPackage, 
      deploymentPath
    );

    res.json({
      success: true,
      data: {
        message: `Successfully generated ${Object.keys(result.deploymentPackage.files).length} deployment files`,
        filesGenerated: Object.keys(result.deploymentPackage.files),
        confidence: result.extractedConfig.confidence,
        metadata: result.metadata,
        deploymentPath: deploymentPath,
        storageType: redisService.isAvailable() ? 'redis' : 'memory'
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
    // Validate session and load conversation
    const sessionValidation = await sessionManager.validateSession(conversationId);
    if (!sessionValidation.valid) {
      return res.status(404).json({
        success: false,
        message: `Session invalid: ${sessionValidation.reason}`
      });
    }

    const conversation = await conversationStorage.loadConversation(conversationId);
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
# Storage: ${redisService.isAvailable() ? 'Redis' : 'Memory'}

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
    // Validate session and load conversation
    const sessionValidation = await sessionManager.validateSession(conversationId);
    if (!sessionValidation.valid) {
      return res.status(404).json({
        success: false,
        message: `Session invalid: ${sessionValidation.reason}`
      });
    }

    const conversation = await conversationStorage.loadConversation(conversationId);
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
        lastUpdated: conversation.lastUpdated,
        deploymentPath: conversation.deploymentPath,
        storageType: redisService.isAvailable() ? 'redis' : 'memory'
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
 * Test Bedrock tools functionality
 */
exports.testTools = async (req, res) => {
  try {
    // Try Bedrock Tools agent first
    if (bedrockToolsAgent.isInitialized) {
      const tools = bedrockToolsAgent.getAvailableTools();
      
      // Create a simple test message to trigger tool usage
      const testResult = await bedrockToolsAgent.processMessage(
        'You are a test assistant. Use the list_deployment_files tool to show available files.',
        'List the available deployment files',
        []
      );

      return res.json({
        success: true,
        data: {
          message: 'Bedrock Tools test completed',
          agent: 'bedrock-tools',
          result: testResult.content,
          toolCalls: testResult.toolCalls,
          availableTools: tools.map(t => t.name)
        }
      });
    }

    // No tools agents available
    return res.status(503).json({
      success: false,
      message: 'Bedrock Tools agent not initialized. AWS credentials required.',
      suggestion: 'Try the /test-tools-direct endpoint to test tools directly.'
    });

  } catch (error) {
    console.error('Error testing tools:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to test tools: ' + error.message
    });
  }
};

/**
 * Test tools directly without any agent
 */
exports.testToolsDirect = async (req, res) => {
  try {
    const { 
      IntrospectFileTool, 
      EditFileTool, 
      ListDeploymentFilesTool, 
      CreateDeploymentFileTool 
    } = require('../services/langgraphTools');

    // Test the tools directly
    const listTool = new ListDeploymentFilesTool();
    const introspectTool = new IntrospectFileTool();

    // Test listing files
    const listResult = await listTool._call('{}');
    
    // Test introspecting a file (if any are found)
    let introspectResult = 'No files to introspect';
    if (listResult.includes('config.yaml')) {
      introspectResult = await introspectTool._call('{"filePath": "config.yaml"}');
    }

    res.json({
      success: true,
      data: {
        message: 'Direct tools test completed',
        listResult: listResult,
        introspectResult: introspectResult.substring(0, 500) + '...', // Truncate for readability
        toolsAvailable: [
          'introspect_file',
          'edit_file', 
          'list_deployment_files',
          'create_deployment_file'
        ]
      }
    });

  } catch (error) {
    console.error('Error testing tools directly:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to test tools directly: ' + error.message
    });
  }
};

/**
 * Session management endpoints
 * Handles both GET (conversationId in params) and POST (conversationId in body) formats
 */
exports.validateSession = async (req, res) => {
  // Handle both GET and POST formats
  const conversationId = req.params.conversationId || req.body.conversationId;
  
  if (!conversationId) {
    return res.status(400).json({
      success: false,
      message: 'Conversation ID is required'
    });
  }
  
  try {
    const validation = await sessionManager.validateSession(conversationId);
    
    if (validation.valid) {
      // Load full conversation data for frontend restoration
      const conversation = await conversationStorage.loadConversation(conversationId);
      const sessionInfo = await sessionManager.getSessionInfo(conversationId);
      
      if (conversation) {
        res.json({
          success: true,
          conversation: conversation,
          sessionInfo: sessionInfo
        });
      } else {
        // Session exists but conversation data not found
        res.status(404).json({
          success: false,
          message: 'Conversation data not found'
        });
      }
    } else {
      res.status(404).json({
        success: false,
        valid: false,
        reason: validation.reason
      });
    }
  } catch (error) {
    console.error('Error validating session:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to validate session'
    });
  }
};

/**
 * List active sessions (for debugging/monitoring)
 */
exports.listSessions = async (req, res) => {
  try {
    const sessions = await sessionManager.getActiveSessions();
    const stats = await sessionManager.getSessionStats();
    
    res.json({
      success: true,
      data: {
        sessions: sessions,
        stats: stats
      }
    });
  } catch (error) {
    console.error('Error listing sessions:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to list sessions'
    });
  }
};

/**
 * Cleanup expired sessions manually
 */
exports.cleanupSessions = async (req, res) => {
  try {
    const sessionsCleaned = await sessionManager.cleanupExpiredSessions();
    const conversationsCleaned = await conversationStorage.cleanupOldConversations();
    
    res.json({
      success: true,
      data: {
        message: `Cleanup completed: ${sessionsCleaned} sessions, ${conversationsCleaned} conversations`,
        sessionsCleaned: sessionsCleaned,
        conversationsCleaned: conversationsCleaned
      }
    });
  } catch (error) {
    console.error('Error during cleanup:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to cleanup sessions'
    });
  }
};

/**
 * Health check for chat system
 */
exports.healthCheck = async (req, res) => {
  try {
    // Check if systems are initialized
    const deploymentInitialized = deploymentGenerator.isInitialized;
    const bedrockToolsInitialized = bedrockToolsAgent.isInitialized;
    
    // Get Redis and session statistics
    const redisStatus = redisService.getStatus();
    const sessionStats = await sessionManager.getSessionStats();
    const storageStats = await conversationStorage.getStorageStats();

    // Get basic system info
    const systemInfo = {
      chatSystem: 'operational',
      deploymentGenerator: deploymentInitialized ? 'initialized' : 'initializing',
      bedrockToolsAgent: bedrockToolsInitialized ? 'initialized' : 'initializing',
      toolsAvailable: bedrockToolsInitialized,
      
      // Redis and storage information
      redis: redisStatus,
      sessions: sessionStats,
      storage: storageStats,
      
      timestamp: new Date().toISOString()
    };

    if (deploymentInitialized) {
      // Get template information if available
      try {
        const templates = await deploymentGenerator.getAvailableTemplates();
        systemInfo.templatesLoaded = Object.keys(templates).length;
      } catch (error) {
        systemInfo.templatesLoaded = 'error loading';
      }
    }

    // Get tools information from available agents
    if (bedrockToolsInitialized) {
      try {
        const tools = bedrockToolsAgent.getAvailableTools();
        systemInfo.bedrockTools = tools.length;
        systemInfo.bedrockToolNames = tools.map(t => t.name);
        systemInfo.primaryAgent = 'bedrock-tools';
      } catch (error) {
        systemInfo.bedrockTools = 'error loading';
      }
    }

    if (!systemInfo.primaryAgent) {
      systemInfo.primaryAgent = 'basic-bedrock';
    }

    // Determine overall health based on critical systems
    const isHealthy = systemInfo.chatSystem === 'operational' && 
                     (redisStatus.connected || redisStatus.fallbackMode);

    res.json({
      success: true,
      status: isHealthy ? 'healthy' : 'degraded',
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