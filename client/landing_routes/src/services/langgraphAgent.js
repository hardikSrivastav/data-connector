const { StateGraph, END } = require('@langchain/langgraph');
const { ChatAnthropic } = require('@langchain/anthropic');
const { HumanMessage, SystemMessage } = require('@langchain/core/messages');
const { ToolNode } = require('@langchain/langgraph/prebuilt');
const { 
  IntrospectFileTool, 
  EditFileTool, 
  ListDeploymentFilesTool, 
  CreateDeploymentFileTool,
  PackageDeploymentFilesTool
} = require('./langgraphTools');

class LangGraphAgent {
  constructor() {
    this.model = null;
    this.tools = null;
    this.graph = null;
    this.isInitialized = false;
  }

  async initialize() {
    try {
      // Check if Anthropic API key is available
      if (!process.env.ANTHROPIC_API_KEY) {
        throw new Error('ANTHROPIC_API_KEY environment variable is required for LangGraph agent');
      }

      // Initialize the ChatAnthropic model
      this.model = new ChatAnthropic({
        apiKey: process.env.ANTHROPIC_API_KEY,
        model: 'claude-3-haiku-20240307',
        temperature: 0.7,
        maxTokens: 2000,
      });

      // Initialize tools
      this.tools = [
        new IntrospectFileTool(),
        new EditFileTool(),
        new ListDeploymentFilesTool(),
        new CreateDeploymentFileTool(),
        new PackageDeploymentFilesTool()
      ];

      // Bind tools to the model
      this.modelWithTools = this.model.bindTools(this.tools);

      // Create the graph
      this.graph = this.createGraph();

      this.isInitialized = true;
      console.log('LangGraph agent initialized successfully');
    } catch (error) {
      console.error('Failed to initialize LangGraph agent:', error);
      throw error;
    }
  }

  createGraph() {
    // Define the agent state
    const agentState = {
      messages: {
        value: (x, y) => x.concat(y),
        default: () => [],
      },
    };

    // Create a new graph
    const workflow = new StateGraph(agentState);

    // Define the nodes
    workflow.addNode('agent', this.callModel.bind(this));
    workflow.addNode('tools', new ToolNode(this.tools));

    // Set the entrypoint
    workflow.setEntryPoint('agent');

    // Define conditional edges
    workflow.addConditionalEdges(
      'agent',
      this.shouldContinue.bind(this),
      {
        continue: 'tools',
        end: END,
      }
    );

    // Add edge from tools back to agent
    workflow.addEdge('tools', 'agent');

    // Compile the graph
    return workflow.compile();
  }

  async callModel(state) {
    const messages = state.messages;
    const response = await this.modelWithTools.invoke(messages);
    return { messages: [response] };
  }

  shouldContinue(state) {
    const messages = state.messages;
    const lastMessage = messages[messages.length - 1];
    
    // If there are tool calls, continue to tools
    if (lastMessage.tool_calls && lastMessage.tool_calls.length > 0) {
      return 'continue';
    }
    // Otherwise, end
    return 'end';
  }

  async processMessage(systemPrompt, userMessage, conversationHistory = []) {
    if (!this.isInitialized) {
      throw new Error('Agent not initialized. Call initialize() first.');
    }

    try {
      // Build the message history
      const messages = [
        new SystemMessage(systemPrompt),
        ...conversationHistory,
        new HumanMessage(userMessage)
      ];

      console.log('Processing message with LangGraph...');
      console.log('Message history:', messages.map(m => ({ role: m.constructor.name, content: m.content?.substring(0, 100) + '...' })));

      // Invoke the graph
      const result = await this.graph.invoke({
        messages: messages
      });

      console.log('LangGraph result:', result);
      console.log('Result messages count:', result.messages.length);

      // Extract tool calls from all messages
      let allToolCalls = [];
      let finalContent = '';

      for (const message of result.messages) {
        if (message.tool_calls) {
          allToolCalls.push(...message.tool_calls);
        }
        // Get the final assistant message content
        if (message.constructor.name === 'AIMessage' && message.content) {
          finalContent = message.content;
        }
      }

      console.log('Extracted tool calls:', allToolCalls);
      console.log('Final content:', finalContent);

      return {
        content: finalContent,
        toolCalls: allToolCalls,
        fullMessages: result.messages
      };

    } catch (error) {
      console.error('Error processing message with LangGraph:', error);
      throw error;
    }
  }

  async processMessageStream(systemPrompt, userMessage, conversationHistory = [], onChunk) {
    if (!this.isInitialized) {
      throw new Error('Agent not initialized. Call initialize() first.');
    }

    try {
      // Build the message history
      const messages = [
        new SystemMessage(systemPrompt),
        ...conversationHistory,
        new HumanMessage(userMessage)
      ];

      // Use streaming with the graph
      let fullContent = '';
      let toolCalls = [];
      let allMessages = [];

      // Stream the response
      for await (const output of await this.graph.stream({
        messages: messages
      })) {
        console.log('LangGraph stream output:', JSON.stringify(output, null, 2));
        
        // Handle agent node outputs
        if (output.agent && output.agent.messages) {
          const message = output.agent.messages[output.agent.messages.length - 1];
          allMessages.push(message);
          
          if (message.content) {
            fullContent += message.content;
            if (onChunk) {
              onChunk(message.content);
            }
          }

          if (message.tool_calls && message.tool_calls.length > 0) {
            toolCalls.push(...message.tool_calls);
            // Notify about tool calls
            if (onChunk) {
              for (const toolCall of message.tool_calls) {
                onChunk(`\n[TOOL CALL] ${toolCall.name}: ${JSON.stringify(toolCall.args)}\n`);
              }
            }
          }
        }

        // Handle tools node outputs
        if (output.tools && output.tools.messages) {
          allMessages.push(...output.tools.messages);
          
          // Notify about tool results
          if (onChunk) {
            for (const toolMessage of output.tools.messages) {
              onChunk(`\n[TOOL RESULT] ${toolMessage.content}\n`);
            }
          }
        }
      }

      return {
        content: fullContent,
        toolCalls: toolCalls,
        fullMessages: allMessages
      };

    } catch (error) {
      console.error('Error streaming message with LangGraph:', error);
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

module.exports = LangGraphAgent; 