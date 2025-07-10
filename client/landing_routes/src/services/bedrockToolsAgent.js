const { BedrockRuntimeClient, InvokeModelCommand, InvokeModelWithResponseStreamCommand } = require('@aws-sdk/client-bedrock-runtime');
const { 
  IntrospectFileTool, 
  EditFileTool, 
  ListDeploymentFilesTool, 
  CreateDeploymentFileTool 
} = require('./langgraphTools');

class BedrockToolsAgent {
  constructor() {
    this.client = null;
    this.tools = null;
    this.isInitialized = false;
    this.modelId = 'anthropic.claude-3-haiku-20240307-v1:0';
    
    // Token limits for different models
    this.tokenLimits = {
      'anthropic.claude-3-haiku-20240307-v1:0': 200000,  // 200K tokens
      'anthropic.claude-3-sonnet-20240229-v1:0': 200000,
      'anthropic.claude-3-opus-20240229-v1:0': 200000
    };
    
    // Reserve tokens for response and buffer
    this.reservedTokens = 2500; // 2000 for response + 500 buffer
  }

  async initialize() {
    try {
      // Initialize AWS Bedrock client
      this.client = new BedrockRuntimeClient({
        region: process.env.AWS_REGION || 'ap-south-1',
        credentials: {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
        }
      });

      // Initialize tools
      this.tools = [
        new IntrospectFileTool(),
        new EditFileTool(),
        new ListDeploymentFilesTool(),
        new CreateDeploymentFileTool()
      ];

      this.isInitialized = true;
      console.log('Bedrock Tools agent initialized successfully');
    } catch (error) {
      console.error('Failed to initialize Bedrock Tools agent:', error);
      throw error;
    }
  }

  // Rough token estimation (1 token ≈ 4 characters for English text)
  estimateTokens(text) {
    if (typeof text !== 'string') {
      text = JSON.stringify(text);
    }
    return Math.ceil(text.length / 4);
  }

  // Calculate total tokens for a message
  calculateMessageTokens(message) {
    let totalTokens = 0;
    
    if (message.content && Array.isArray(message.content)) {
      for (const content of message.content) {
        if (content.text) {
          totalTokens += this.estimateTokens(content.text);
        } else if (content.type === 'tool_use') {
          totalTokens += this.estimateTokens(JSON.stringify(content));
        } else if (content.type === 'tool_result') {
          totalTokens += this.estimateTokens(content.content || '');
        }
      }
    }
    
    return totalTokens;
  }

  // Calculate total tokens for the entire request
  calculateRequestTokens(systemPrompt, messages, tools) {
    let totalTokens = 0;
    
    // System prompt tokens
    totalTokens += this.estimateTokens(systemPrompt);
    
    // Message tokens
    for (const message of messages) {
      totalTokens += this.calculateMessageTokens(message);
    }
    
    // Tool definition tokens
    totalTokens += this.estimateTokens(JSON.stringify(tools));
    
    return totalTokens;
  }

  // Intelligently slice conversation history to fit within token limits
  sliceConversationHistory(systemPrompt, messages, tools) {
    const maxTokens = this.tokenLimits[this.modelId] || 200000;
    const availableTokens = maxTokens - this.reservedTokens;
    
    // Calculate fixed costs
    const systemTokens = this.estimateTokens(systemPrompt);
    const toolTokens = this.estimateTokens(JSON.stringify(tools));
    const fixedTokens = systemTokens + toolTokens;
    
    const availableForMessages = availableTokens - fixedTokens;
    
    console.log('BedrockToolsAgent: Token management', {
      maxTokens,
      availableTokens,
      systemTokens,
      toolTokens,
      fixedTokens,
      availableForMessages,
      totalMessages: messages.length
    });
    
    // If we have plenty of space, return all messages
    const totalMessageTokens = messages.reduce((sum, msg) => sum + this.calculateMessageTokens(msg), 0);
    if (totalMessageTokens <= availableForMessages) {
      console.log('BedrockToolsAgent: All messages fit within token limit');
      return messages;
    }
    
    // We need to slice - prioritize recent messages
    const slicedMessages = [];
    let currentTokens = 0;
    
    // Start from the end (most recent) and work backwards
    for (let i = messages.length - 1; i >= 0; i--) {
      const messageTokens = this.calculateMessageTokens(messages[i]);
      
      // Always include the last message (current user message)
      if (i === messages.length - 1) {
        slicedMessages.unshift(messages[i]);
        currentTokens += messageTokens;
        continue;
      }
      
      // Check if we can fit this message
      if (currentTokens + messageTokens <= availableForMessages) {
        slicedMessages.unshift(messages[i]);
        currentTokens += messageTokens;
      } else {
        // Try to fit a truncated version if it's a text message
        if (messages[i].content && Array.isArray(messages[i].content)) {
          const textContent = messages[i].content.find(c => c.type === 'text');
          if (textContent && textContent.text) {
            const remainingTokens = availableForMessages - currentTokens;
            const maxChars = Math.max(100, remainingTokens * 4); // At least 100 chars
            
            if (textContent.text.length > maxChars) {
              const truncatedMessage = {
                ...messages[i],
                content: [{
                  type: 'text',
                  text: textContent.text.substring(0, maxChars) + '...[truncated]'
                }]
              };
              
              const truncatedTokens = this.calculateMessageTokens(truncatedMessage);
              if (currentTokens + truncatedTokens <= availableForMessages) {
                slicedMessages.unshift(truncatedMessage);
                currentTokens += truncatedTokens;
              }
            }
          }
        }
        break;
      }
    }
    
    console.log('BedrockToolsAgent: Sliced conversation', {
      originalMessages: messages.length,
      slicedMessages: slicedMessages.length,
      estimatedTokens: currentTokens,
      availableForMessages
    });
    
    return slicedMessages;
  }

  // Convert our custom tools to Bedrock tool format
  getBedrockToolsFormat() {
    return this.tools.map(tool => ({
      name: tool.name,
      description: tool.description.trim(),
      input_schema: {
        type: "object",
        properties: {
          input: {
            type: "string",
            description: "JSON string containing the tool parameters"
          }
        },
        required: ["input"]
      }
    }));
  }

  // Build valid message history with proper role alternation
  buildValidMessageHistory(conversationHistory, newUserMessage) {
    const messages = [];
    
    console.log('BedrockToolsAgent: Building message history from:', conversationHistory.map(m => ({role: m.role, content: m.content.substring(0, 50)})));
    
    // Process conversation history, ensuring role alternation
    for (const msg of conversationHistory) {
      const formattedMsg = {
        role: msg.role === 'assistant' ? 'assistant' : 'user',
        content: [{ type: "text", text: msg.content }]
      };
      
      // Skip consecutive messages with the same role
      if (messages.length === 0 || messages[messages.length - 1].role !== formattedMsg.role) {
        messages.push(formattedMsg);
      } else {
        console.log(`BedrockToolsAgent: Skipping consecutive ${formattedMsg.role} message`);
      }
    }
    
    // Add new user message, ensuring it doesn't create consecutive user messages
    const newMsg = {
      role: 'user',
      content: [{ type: "text", text: newUserMessage }]
    };
    
    if (messages.length === 0 || messages[messages.length - 1].role !== 'user') {
      messages.push(newMsg);
    } else {
      // If the last message was also from user, combine them or replace
      console.log('BedrockToolsAgent: Replacing consecutive user message');
      messages[messages.length - 1] = newMsg;
    }
    
    console.log('BedrockToolsAgent: Final message roles:', messages.map(m => m.role));
    return messages;
  }

  // Validate message role alternation
  validateRoleAlternation(messages) {
    for (let i = 1; i < messages.length; i++) {
      if (messages[i].role === messages[i - 1].role) {
        throw new Error(`Role alternation violated: found consecutive ${messages[i].role} messages at positions ${i-1} and ${i}`);
      }
    }
    return true;
  }

  async processMessage(systemPrompt, userMessage, conversationHistory = []) {
    if (!this.isInitialized) {
      throw new Error('Agent not initialized. Call initialize() first.');
    }

    try {
      // Build message history for Bedrock format with proper role alternation
      const messages = this.buildValidMessageHistory(conversationHistory, userMessage);

      let finalResponse = '';
      let allToolCalls = [];
      let currentMessages = [...messages];
      let fullConversationContent = '';

      // Main conversation loop with tool calling
      while (true) {
        const response = await this.invokeWithTools(systemPrompt, currentMessages);
        
        if (response.stop_reason === 'tool_use') {
          // Extract tool calls
          const toolCalls = response.content.filter(content => content.type === 'tool_use');
          
          // Add tool call text to full content as inline markers
          for (const toolCall of toolCalls) {
            fullConversationContent += `[TOOL:${toolCall.name}:${toolCall.id}]`;
          }
          
          // Execute tools and collect results
          const toolResults = await this.executeTools(toolCalls);
          
          // Create frontend-friendly tool calls with results (don't mutate original)
          const frontendToolCalls = toolCalls.map((toolCall, i) => {
            const toolResult = toolResults[i];
            console.log(`[processMessage] Frontend tool call mapping - Tool: ${toolCall.name}, ID: ${toolCall.id}, Result exists: ${!!toolResult}, Result content: ${toolResult ? toolResult.content?.substring(0, 100) : 'N/A'}`);
            
            return {
              name: toolCall.name,
              id: toolCall.id,
              input: toolCall.input,
              result: toolResult ? toolResult.content : undefined
            };
          });
          
          // Add to allToolCalls for frontend
          allToolCalls.push(...frontendToolCalls);
          
          // Add tool results to full content as inline markers
          for (let i = 0; i < toolResults.length; i++) {
            const toolResult = toolResults[i];
            const toolCall = toolCalls[i];
            fullConversationContent += `[RESULT:${toolCall.name}:${toolCall.id}]`;
          }
          
          // Add assistant message with tool calls to conversation
          currentMessages.push({
            role: 'assistant',
            content: response.content
          });
          
          // Add user message with tool results
          // Ensure we maintain role alternation
          currentMessages.push({
            role: 'user',
            content: toolResults
          });
          
          // Validate before next iteration
          this.validateRoleAlternation(currentMessages);
          
        } else {
          // Final response
          const textContent = response.content.find(content => content.type === 'text');
          finalResponse = textContent ? textContent.text : '';
          
          // Add final response to full content
          fullConversationContent += finalResponse;
          
          // Add final assistant message if we haven't already
          if (currentMessages.length === 0 || currentMessages[currentMessages.length - 1].role !== 'assistant') {
            currentMessages.push({
              role: 'assistant',
              content: response.content
            });
          }
          
          break;
        }
      }

      return {
        content: fullConversationContent, // Include tool calls in the final content
        toolCalls: allToolCalls,
        fullMessages: currentMessages
      };

    } catch (error) {
      console.error('Error processing message with Bedrock Tools:', error);
      throw error;
    }
  }

  async invokeWithTools(systemPrompt, messages) {
    // Validate role alternation
    this.validateRoleAlternation(messages);
    
    // Get tools and apply intelligent slicing
    const tools = this.getBedrockToolsFormat();
    const slicedMessages = this.sliceConversationHistory(systemPrompt, messages, tools);
    
    // Add validation and debugging
    console.log('BedrockToolsAgent: Invoking with messages (roles):', slicedMessages.map(m => m.role));
    
    // Validate message format
    for (const message of slicedMessages) {
      if (!message.content || !Array.isArray(message.content)) {
        throw new Error(`Invalid message format: content must be an array. Got: ${JSON.stringify(message)}`);
      }
      for (const content of message.content) {
        if (content.type === undefined) {
          throw new Error(`Invalid content format: missing type field. Got: ${JSON.stringify(content)}`);
        }
      }
    }

    const params = {
      modelId: this.modelId,
      contentType: 'application/json',
      accept: 'application/json',
      body: JSON.stringify({
        anthropic_version: "bedrock-2023-05-31",
        max_tokens: 2000,
        temperature: 0.7,
        system: systemPrompt,
        messages: slicedMessages,
        tools: tools
      })
    };

    const command = new InvokeModelCommand(params);
    const response = await this.client.send(command);
    
    const responseBody = JSON.parse(new TextDecoder().decode(response.body));
    return responseBody;
  }

  async executeTools(toolCalls) {
    const toolResults = [];
    
    for (const toolCall of toolCalls) {
      try {
        console.log(`Executing tool: ${toolCall.name}`, toolCall.input);
        
        // Find the corresponding tool
        const tool = this.tools.find(t => t.name === toolCall.name);
        if (!tool) {
          toolResults.push({
            type: 'tool_result',
            tool_use_id: toolCall.id,
            content: `Error: Tool ${toolCall.name} not found`
          });
          continue;
        }

        // Execute the tool - handle input parsing more robustly
        let toolInput;
        if (toolCall.input && toolCall.input.input) {
          // Input is nested (from Bedrock's expected format)
          toolInput = toolCall.input.input;
        } else if (typeof toolCall.input === 'string') {
          // Input is already a string
          toolInput = toolCall.input;
        } else {
          // Input is an object, stringify it
          toolInput = JSON.stringify(toolCall.input);
        }
        
        console.log(`Tool ${toolCall.name} input:`, toolInput);
        const result = await tool._call(toolInput);
        console.log(`Tool ${toolCall.name} result length:`, result ? result.length : 0);
        
        // Truncate very long results to prevent token overflow
        let truncatedResult = result;
        if (result && result.length > 10000) {
          truncatedResult = result.substring(0, 10000) + '\n...[Result truncated to prevent token overflow]';
        }
        
        toolResults.push({
          type: 'tool_result',
          tool_use_id: toolCall.id,
          content: truncatedResult || ''
        });
        
      } catch (error) {
        console.error(`Error executing tool ${toolCall.name}:`, error);
        toolResults.push({
          type: 'tool_result',
          tool_use_id: toolCall.id,
          content: `Error executing tool: ${error.message}`
        });
      }
    }
    
    return toolResults;
  }

  async processMessageStream(systemPrompt, userMessage, conversationHistory = [], onChunk) {
    if (!this.isInitialized) {
      throw new Error('Agent not initialized. Call initialize() first.');
    }

    try {
      // Build message history for Bedrock format with proper role alternation
      const messages = this.buildValidMessageHistory(conversationHistory, userMessage);

      let finalResponse = '';
      let allToolCalls = [];
      let currentMessages = [...messages];
      let fullConversationContent = '';

      // Main conversation loop with tool calling
      while (true) {
        const response = await this.invokeWithTools(systemPrompt, currentMessages);
        
        if (response.stop_reason === 'tool_use') {
          // Extract tool calls
          const toolCalls = response.content.filter(content => content.type === 'tool_use');
          
          // Send tool call notifications as inline markers (just the marker, not the full input)
          for (const toolCall of toolCalls) {
            const toolCallText = `[TOOL:${toolCall.name}:${toolCall.id}]`;
            fullConversationContent += toolCallText;
            if (onChunk) {
              onChunk(toolCallText);
            }
          }
          
          // Execute tools and collect results
          const toolResults = await this.executeTools(toolCalls);
          
          // Create frontend-friendly tool calls with results (don't mutate original)
          const frontendToolCalls = toolCalls.map((toolCall, i) => {
            const toolResult = toolResults[i];
            console.log(`[processMessageStream] Frontend tool call mapping - Tool: ${toolCall.name}, ID: ${toolCall.id}, Result exists: ${!!toolResult}, Result content: ${toolResult ? toolResult.content?.substring(0, 100) : 'N/A'}`);
            
            return {
              name: toolCall.name,
              id: toolCall.id,
              input: toolCall.input,
              result: toolResult ? toolResult.content : undefined
            };
          });
          
          // Add to allToolCalls for frontend
          allToolCalls.push(...frontendToolCalls);
          
          // Send tool results as inline markers (just the marker, not the full content)
          for (let i = 0; i < toolResults.length; i++) {
            const toolResult = toolResults[i];
            const toolCall = toolCalls[i];
            const toolResultText = `[RESULT:${toolCall.name}:${toolCall.id}]`;
            fullConversationContent += toolResultText;
            if (onChunk) {
              onChunk(toolResultText);
            }
          }
          
          // Add assistant message with tool calls to conversation
          currentMessages.push({
            role: 'assistant',
            content: response.content
          });
          
          // Add user message with tool results
          // Ensure we maintain role alternation
          currentMessages.push({
            role: 'user',
            content: toolResults
          });
          
          // Validate before next iteration
          this.validateRoleAlternation(currentMessages);
          
        } else {
          // Final response
          const textContent = response.content.find(content => content.type === 'text');
          finalResponse = textContent ? textContent.text : '';
          
          // Add final response to full content
          fullConversationContent += finalResponse;
          
          // Stream the final response
          if (onChunk && finalResponse) {
            const chunkSize = 10;
            for (let i = 0; i < finalResponse.length; i += chunkSize) {
              const chunk = finalResponse.slice(i, i + chunkSize);
              onChunk(chunk);
              // Small delay to simulate streaming
              await new Promise(resolve => setTimeout(resolve, 50));
            }
          }
          
          break;
        }
      }

      return {
        content: fullConversationContent, // Include tool calls in the final content
        toolCalls: allToolCalls,
        fullMessages: currentMessages
      };

    } catch (error) {
      console.error('Error streaming message with Bedrock Tools:', error);
      throw error;
    }
  }

  getAvailableTools() {
    return this.tools.map(tool => ({
      name: tool.name,
      description: tool.description
    }));
  }
}

module.exports = BedrockToolsAgent; 