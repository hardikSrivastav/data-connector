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
          allToolCalls.push(...toolCalls);
          
          // Add tool call text to full content as formatted code blocks
          for (const toolCall of toolCalls) {
            fullConversationContent += `\n\n\`\`\`tool-call\n🔧 ${toolCall.name}\n${JSON.stringify(toolCall.input, null, 2)}\n\`\`\`\n`;
          }
          
          // Execute tools and collect results
          const toolResults = await this.executeTools(toolCalls);
          
          // Add tool results to full content as formatted code blocks
          for (let i = 0; i < toolResults.length; i++) {
            const toolResult = toolResults[i];
            const toolCall = toolCalls[i];
            fullConversationContent += `\n\`\`\`tool-result\n✅ ${toolCall.name} completed\n${toolResult.content.length > 500 ? toolResult.content.substring(0, 500) + '...' : toolResult.content}\n\`\`\`\n\n`;
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
    
    // Add validation and debugging
    console.log('BedrockToolsAgent: Invoking with messages (roles):', messages.map(m => m.role));
    
    // Validate message format
    for (const message of messages) {
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
        messages: messages,
        tools: this.getBedrockToolsFormat()
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

        // Execute the tool
        const result = await tool._call(toolCall.input.input || JSON.stringify(toolCall.input));
        
        toolResults.push({
          type: 'tool_result',
          tool_use_id: toolCall.id,
          content: result
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
          allToolCalls.push(...toolCalls);
          
          // Send tool call notifications to frontend as formatted code blocks
          for (const toolCall of toolCalls) {
            const toolCallText = `\n\n\`\`\`tool-call\n🔧 ${toolCall.name}\n${JSON.stringify(toolCall.input, null, 2)}\n\`\`\`\n`;
            fullConversationContent += toolCallText;
            if (onChunk) {
              onChunk(toolCallText);
            }
          }
          
          // Execute tools and collect results
          const toolResults = await this.executeTools(toolCalls);
          
          // Send tool results to frontend as formatted code blocks
          for (let i = 0; i < toolResults.length; i++) {
            const toolResult = toolResults[i];
            const toolCall = toolCalls[i];
            const toolResultText = `\n\`\`\`tool-result\n✅ ${toolCall.name} completed\n${toolResult.content.length > 500 ? toolResult.content.substring(0, 500) + '...' : toolResult.content}\n\`\`\`\n\n`;
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