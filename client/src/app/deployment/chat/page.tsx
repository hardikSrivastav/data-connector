"use client";

import { useState, useEffect, useRef } from "react";
import { flushSync } from "react-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { Send, Bot, User, FileText, Database, Shield, Settings, CheckCircle, Menu, RotateCcw } from "lucide-react";
import { Navbar } from "@/components/navbar";
import Image from "next/image";
import { MessageRenderer } from "@/components/message-renderer";

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
}

interface ToolCall {
  name: string;
  id: string;
  input?: any;
  result?: string;
}

interface ExtractedConfig {
  databases?: string[];
  auth?: string;
  environment?: string;
  scale?: string;
  deploymentProgress?: number; // Add deployment progress tracking
  deploymentFiles?: DeploymentFile[]; // Add file tracking
}

interface DeploymentFile {
  name: string;
  status: 'not_started' | 'in_progress' | 'completed';
  fieldsTotal: number;
  fieldsCompleted: number;
  missingFields: string[];
}

interface ProgressStep {
  id: string;
  label: string;
  completed: boolean;
  current: boolean;
}

export default function ChatDeploymentPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingToolCalls, setStreamingToolCalls] = useState<ToolCall[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [extractedConfig, setExtractedConfig] = useState<ExtractedConfig>({});
  const [isGeneratingFiles, setIsGeneratingFiles] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [showNavbar, setShowNavbar] = useState(false);
  const [navbarVisible, setNavbarVisible] = useState(false);
  const [currentStage, setCurrentStage] = useState<string>("Ready to configure your deployment");
  const [isToolSidebarOpen, setIsToolSidebarOpen] = useState(false);
  const [deploymentProgress, setDeploymentProgress] = useState(0);
  const [deploymentFiles, setDeploymentFiles] = useState<DeploymentFile[]>([]);
  const [showFilesSidebar, setShowFilesSidebar] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Restore conversation from localStorage on component mount
  useEffect(() => {
    const restoreConversation = async () => {
      // Try to restore conversation ID from localStorage
      const savedConversationId = localStorage.getItem('deployment-conversation-id');
      if (savedConversationId) {
        try {
          // Validate the session with backend and load conversation history
          const backendUrl = process.env.NODE_ENV === 'production' 
            ? 'http://localhost:3001/api/chat/validate-session'
            : 'http://localhost:3001/api/chat/validate-session';
            
          const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              conversationId: savedConversationId
            })
          });

          if (response.ok) {
            const data = await response.json();
            if (data.success && data.conversation) {
              // Session is valid, restore the conversation
              setConversationId(savedConversationId);
              
              // Restore messages from conversation history
              if (data.conversation.messages && data.conversation.messages.length > 0) {
                const formattedMessages = data.conversation.messages.map((msg: any) => ({
                  role: msg.role,
                  content: msg.content,
                  timestamp: new Date(msg.timestamp),
                  toolCalls: msg.toolCalls || []
                }));
                setMessages(formattedMessages);
              }
              
              // Restore extracted config if available
              if (data.conversation.metadata?.extractedConfig) {
                setExtractedConfig(data.conversation.metadata.extractedConfig);
              }
              
              console.log(`Restored conversation ${savedConversationId} with ${data.conversation.messages?.length || 0} messages`);
            } else {
              // Session is invalid or expired, clear localStorage
              localStorage.removeItem('deployment-conversation-id');
            }
          } else {
            // Session validation failed, clear localStorage
            localStorage.removeItem('deployment-conversation-id');
          }
        } catch (error) {
          console.error('Failed to restore conversation:', error);
          // Clear invalid session from localStorage
          localStorage.removeItem('deployment-conversation-id');
        }
      }
    };

    restoreConversation();
  }, []);

  // Update current stage based on conversation state
  useEffect(() => {
    if (isGeneratingFiles) {
      setCurrentStage("Generating your deployment files...");
    } else if (isStreaming) {
      setCurrentStage("Analyzing your requirements...");
    } else if (messages.length > 0) {
      setCurrentStage("Configuring your deployment");
    } else {
      setCurrentStage("Ready to configure your deployment");
    }
  }, [isGeneratingFiles, isStreaming, messages.length]);

  // Update deployment progress when extracted config changes
  useEffect(() => {
    if (extractedConfig.deploymentProgress !== undefined) {
      setDeploymentProgress(extractedConfig.deploymentProgress);
    }
    if (extractedConfig.deploymentFiles) {
      setDeploymentFiles(extractedConfig.deploymentFiles);
    }
  }, [extractedConfig]);

  const startConversation = async () => {
    setIsLoading(true);
    try {
      const backendUrl = process.env.NODE_ENV === 'production' 
        ? 'http://localhost:3001/api/chat/start'
        : 'http://localhost:3001/api/chat/start';
        
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userInfo: {
            company: "Your Company",
            email: "user@company.com"
          }
        })
      });

      if (!response.ok) {
        throw new Error('Failed to start conversation');
      }

      const data = await response.json();
      setConversationId(data.data.conversationId);
      // Save conversation ID to localStorage for persistence
      localStorage.setItem('deployment-conversation-id', data.data.conversationId);
      // Don't add the initial welcome message to messages array
      
    } catch (error) {
      toast.error("Failed to start conversation");
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Function to parse tool calls from streaming content
  const parseToolCallsFromContent = (content: string): ToolCall[] => {
    const toolCalls: ToolCall[] = [];
    const processedToolIds = new Set<string>();
    
    // Find all tool markers in the content
    const toolMarkerRegex = /\[(?:TOOL|RESULT):([^:]+):([^\]]+)\]/g;
    let match;
    
    while ((match = toolMarkerRegex.exec(content)) !== null) {
      const [fullMatch, toolName, toolId] = match;
      
      // Only process each tool once
      if (!processedToolIds.has(toolId)) {
        processedToolIds.add(toolId);
        
        // Create placeholder tool call
        const toolCall: ToolCall = {
          name: toolName,
          id: toolId,
          input: undefined, // Will be populated when complete data arrives
          result: undefined // Will be populated when complete data arrives
        };
        
        // Check if we have a result marker for this tool
        const resultMarker = `[RESULT:${toolName}:${toolId}]`;
        if (content.includes(resultMarker)) {
          toolCall.result = 'Processing...'; // Placeholder until real result arrives
        }
        
        toolCalls.push(toolCall);
      }
    }
    
    return toolCalls;
  };

    // Function to detect and clean progress JSON from streaming content
  const processProgressInContent = (content: string): string => {
    // Detect if we're in the middle of streaming progress JSON
    const hasProgressKeywords = content.includes('"deploymentProgress"') || 
                               content.includes('"deploymentFiles"') ||
                               content.includes('fieldsTotal') ||
                               content.includes('fieldsCompleted') ||
                               content.includes('missingFields');
    
    if (hasProgressKeywords) {
      // Try to find complete JSON blocks first
      const findCompleteJsonBlocks = (text: string): string[] => {
        const blocks: string[] = [];
        let braceCount = 0;
        let start = -1;
        
        for (let i = 0; i < text.length; i++) {
          if (text[i] === '{') {
            if (braceCount === 0) {
              start = i;
            }
            braceCount++;
          } else if (text[i] === '}') {
            braceCount--;
            if (braceCount === 0 && start !== -1) {
              const block = text.substring(start, i + 1);
              if (block.includes('"deploymentProgress"')) {
                blocks.push(block);
              }
            }
          }
        }
        return blocks;
      };
      
      const completeBlocks = findCompleteJsonBlocks(content);
      
      if (completeBlocks.length > 0) {
        // We have complete JSON, let it be parsed normally
        return content;
      } else {
        // We're streaming partial JSON - replace the entire JSON portion with a single placeholder
        
        // Find the start of the JSON block
        let jsonStart = -1;
        for (let i = 0; i < content.length; i++) {
          if (content[i] === '{' && content.substring(i).includes('"deploymentProgress"')) {
            jsonStart = i;
            break;
          }
        }
        
        if (jsonStart !== -1) {
          // Replace everything from the JSON start to the end with the placeholder
          const beforeJson = content.substring(0, jsonStart);
          return beforeJson + '\n\n⚡ **Updating deployment progress...**';
        } else {
          // Fallback: look for any progress-related content and replace it
          const progressRegex = /\{[^}]*(?:"deploymentProgress"|"deploymentFiles"|"fieldsTotal"|"fieldsCompleted"|"missingFields")[^}]*$/g;
          return content.replace(progressRegex, '\n\n⚡ **Updating deployment progress...**');
        }
      }
    }
    
    return content;
  };

  const sendMessage = async () => {
    if (!currentMessage.trim()) return;

    let currentConversationId = conversationId;

    // If no conversation started yet, start it first
    if (!currentConversationId) {
      setIsLoading(true);
      try {
        const backendUrl = process.env.NODE_ENV === 'production' 
          ? 'http://localhost:3001/api/chat/start'
          : 'http://localhost:3001/api/chat/start';
          
        const response = await fetch(backendUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            userInfo: {
              company: "Your Company",
              email: "user@company.com"
            }
          })
        });

        if (!response.ok) {
          throw new Error('Failed to start conversation');
        }

        const data = await response.json();
        currentConversationId = data.data.conversationId;
        setConversationId(currentConversationId);
        // Save conversation ID to localStorage for persistence
        if (currentConversationId) {
          localStorage.setItem('deployment-conversation-id', currentConversationId);
        }
        
      } catch (error) {
        toast.error("Failed to start conversation");
        console.error('Error:', error);
        setIsLoading(false);
        return;
      } finally {
        setIsLoading(false);
      }
    }

    if (!currentConversationId) return;

    const userMessage = {
      role: 'user' as const,
      content: currentMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    const messageToSend = currentMessage;
    setCurrentMessage("");
    setIsStreaming(true);
    setStreamingContent("");
    setStreamingToolCalls([]);
    
    let isCompleted = false;
    let completedData: any = null;

    try {
      const backendUrl = process.env.NODE_ENV === 'production' 
        ? 'http://localhost:3001/api/chat/message/stream'
        : 'http://localhost:3001/api/chat/message/stream';
        
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversationId: currentConversationId,
          message: messageToSend
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      if (!response.body) {
        throw new Error('No response body for streaming');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      try {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            if (line.trim() === '') continue;
            
            if (line.startsWith('data: ')) {
              try {
                const dataStr = line.slice(6);
                const data = JSON.parse(dataStr);
                
                if (data.type === 'chunk') {
                  flushSync(() => {
                    // Process progress JSON before displaying
                    const processedContent = processProgressInContent(data.fullContent);
                    setStreamingContent(processedContent);
                    // Parse tool calls from the current content
                    const parsedToolCalls = parseToolCallsFromContent(processedContent);
                    setStreamingToolCalls(parsedToolCalls);
                  });
                } else if (data.type === 'tool_call') {
                  // Tool calls are now inline in the message content
                  toast.info(`🔧 Tool in use`);
                } else if (data.type === 'tool_result') {
                  // Tool results are now inline in the message content
                  toast.success(`✅ Tool completed`);
                } else if (data.type === 'complete') {
                  isCompleted = true;
                  completedData = data;
                  // Update streaming tool calls with the complete data - merge with existing parsed calls
                  flushSync(() => {
                    const completeToolCalls = data.toolCalls || [];
                    const mergedToolCalls = completeToolCalls.map((completeTool: ToolCall) => {
                      // Find existing parsed tool call or create new one
                      const existingTool = parseToolCallsFromContent(data.message).find(
                        (t: ToolCall) => t.id === completeTool.id
                      );
                      return {
                        ...completeTool,
                        // Preserve any existing state but use complete data
                        ...existingTool
                      };
                    });
                    setStreamingToolCalls(mergedToolCalls);
                  });
                } else if (data.type === 'error') {
                  toast.error(data.message);
                  setStreamingContent("");
                  setStreamingToolCalls([]);
                  setIsStreaming(false);
                  return;
                }
              } catch (e) {
                console.error('Error parsing streaming data:', e);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
      
      if (isCompleted && completedData) {
        // Ensure all tool calls found in the message content are preserved
        const toolCallsFromContent = parseToolCallsFromContent(completedData.message);
        const completeToolCalls = completedData.toolCalls || [];
        
        // Merge tool calls from content with complete data, preferring complete data
        const mergedToolCalls = toolCallsFromContent.map(parsedTool => {
          const completeTool = completeToolCalls.find((ct: ToolCall) => ct.id === parsedTool.id);
          return completeTool || parsedTool;
        });
        
        // Add any additional tool calls from complete data that weren't in content
        completeToolCalls.forEach((completeTool: ToolCall) => {
          if (!mergedToolCalls.find(mt => mt.id === completeTool.id)) {
            mergedToolCalls.push(completeTool);
          }
        });
        
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedData.message,
          timestamp: new Date(),
          toolCalls: mergedToolCalls
        }]);
        
        // Update extracted config and progress tracking
        const newConfig = completedData.extractedConfig || {};
        setExtractedConfig(newConfig);
        
        // Update progress and files if provided
        if (newConfig.deploymentProgress !== undefined) {
          setDeploymentProgress(newConfig.deploymentProgress);
        }
        if (newConfig.deploymentFiles) {
          setDeploymentFiles(newConfig.deploymentFiles);
        }
      }
      
      setStreamingContent("");
      setStreamingToolCalls([]);
      setIsStreaming(false);
      
    } catch (error) {
      toast.error("Failed to send message");
      console.error('Error:', error);
      setStreamingContent("");
      setStreamingToolCalls([]);
      setIsStreaming(false);
    }
  };

  const simulateFileGeneration = async () => {
    setIsGeneratingFiles(true);
    setGenerationProgress(0);
    
    const steps: ProgressStep[] = [];
    
    if (extractedConfig.databases?.includes('PostgreSQL')) {
      steps.push({ id: 'db-postgres', label: 'Setting up PostgreSQL configuration', completed: false, current: false });
    }
    if (extractedConfig.databases?.includes('MongoDB')) {
      steps.push({ id: 'db-mongo', label: 'Setting up MongoDB configuration', completed: false, current: false });
    }
    if (extractedConfig.databases?.includes('Shopify')) {
      steps.push({ id: 'db-shopify', label: 'Setting up Shopify integration', completed: false, current: false });
    }
    if (extractedConfig.auth === 'Google OAuth') {
      steps.push({ id: 'auth-google', label: 'Configuring Google OAuth', completed: false, current: false });
    }
    if (extractedConfig.auth === 'Azure AD') {
      steps.push({ id: 'auth-azure', label: 'Configuring Azure AD', completed: false, current: false });
    }
    
    steps.push(
      { id: 'docker', label: 'Generating Docker configuration', completed: false, current: false },
      { id: 'nginx', label: 'Setting up Nginx reverse proxy', completed: false, current: false },
      { id: 'env', label: 'Creating environment files', completed: false, current: false },
      { id: 'scripts', label: 'Generating deployment scripts', completed: false, current: false }
    );
    
    setProgressSteps(steps);
    
    for (let i = 0; i < steps.length; i++) {
      const updatedSteps = [...steps];
      updatedSteps[i].current = true;
      setProgressSteps(updatedSteps);
      
      await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 1200));
      
      updatedSteps[i].completed = true;
      updatedSteps[i].current = false;
      setProgressSteps(updatedSteps);
      
      const progress = ((i + 1) / steps.length) * 100;
      setGenerationProgress(progress);
    }
    
    try {
      const backendUrl = process.env.NODE_ENV === 'production' 
        ? 'http://localhost:3001/api/chat/generate-files'
        : 'http://localhost:3001/api/chat/generate-files';
        
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversationId
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate files');
      }

      const data = await response.json();
      toast.success(data.data.message);
      
    } catch (error) {
      toast.error("Failed to generate files");
      console.error('Error:', error);
    } finally {
      setIsGeneratingFiles(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleSidebarStateChange = (isOpen: boolean) => {
    setIsToolSidebarOpen(isOpen);
  };

  const totalFiles = progressSteps.length;
  const completedFiles = progressSteps.filter(step => step.completed).length;
  const remainingFiles = totalFiles - completedFiles;

  const toggleNavbar = () => {
    if (!navbarVisible) {
      // Show navbar
      setNavbarVisible(true);
      setTimeout(() => setShowNavbar(true), 10);
    } else {
      // Hide navbar
      setShowNavbar(false);
      setTimeout(() => setNavbarVisible(false), 300); // Match animation duration
    }
  };

  const startNewConversation = async () => {
    // If we have an active conversation, destroy it on the backend first
    if (conversationId) {
      try {
        const backendUrl = process.env.NODE_ENV === 'production' 
          ? 'http://localhost:3001/api/chat/destroy-session'
          : 'http://localhost:3001/api/chat/destroy-session';
          
        const response = await fetch(backendUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            conversationId
          })
        });

        if (response.ok) {
          console.log(`Successfully destroyed session ${conversationId} on backend`);
        } else {
          console.warn(`Failed to destroy session ${conversationId} on backend`);
        }
      } catch (error) {
        console.error('Error destroying session on backend:', error);
      }
    }

    // Clear localStorage
    localStorage.removeItem('deployment-conversation-id');
    
    // Reset all state
    setConversationId(null);
    setMessages([]);
    setCurrentMessage("");
    setExtractedConfig({});
    setIsGeneratingFiles(false);
    setGenerationProgress(0);
    setProgressSteps([]);
    setStreamingContent("");
    setStreamingToolCalls([]);
    setIsStreaming(false);
    setIsLoading(false);
    
    // Hide navbar if it's visible
    setShowNavbar(false);
    setTimeout(() => setNavbarVisible(false), 300);
    
    console.log('Started new conversation - cleared all state and localStorage');
    toast.success("Conversation reset successfully");
  };

  // Calculate border progress for visual indicator
  const getBorderStyle = (progress: number) => {
    const angle = (progress / 100) * 360;
    
    return {
      background: `conic-gradient(from 0deg, #7b35b8 ${angle}deg, transparent ${angle}deg)`,
      padding: '3px',
      borderRadius: '16px'
    };
  };

  return (
    <div className="h-screen bg-white flex flex-col relative">
      {/* Navbar overlay */}
      {navbarVisible && (
        <div className={`absolute top-0 left-0 right-0 z-50 bg-white shadow-lg transition-all duration-300 ease-in-out ${
          showNavbar ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-full'
        }`}>
          <Navbar />
        </div>
      )}

      {/* Files Sidebar */}
      {showFilesSidebar && deploymentFiles.length > 0 && (
        <div className="fixed left-0 top-0 h-full w-80 bg-white border-r border-gray-200 shadow-lg z-40 overflow-y-auto">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium font-baskerville">Deployment Files</h3>
              <button
                onClick={() => setShowFilesSidebar(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <div className="text-sm text-gray-600 mt-1 font-baskerville">
              {deploymentProgress.toFixed(0)}% Complete
            </div>
          </div>
          <div className="p-4 space-y-3">
            {deploymentFiles.map((file, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm font-baskerville">{file.name}</span>
                  <div className={`w-3 h-3 rounded-full ${
                    file.status === 'completed' ? 'bg-green-500' :
                    file.status === 'in_progress' ? 'bg-yellow-500' :
                    'bg-gray-300'
                  }`} />
                </div>
                <div className="text-xs text-gray-600 mb-1 font-baskerville">
                  {file.fieldsCompleted}/{file.fieldsTotal} fields completed
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div 
                    className="bg-purple-600 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${(file.fieldsCompleted / file.fieldsTotal) * 100}%` }}
                  />
                </div>
                {file.missingFields.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs text-gray-500 font-baskerville">Missing:</div>
                    <div className="text-xs text-red-600 font-baskerville">
                      {file.missingFields.join(', ')}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {(isGeneratingFiles || completedFiles > 0) && (
        <div className="w-full bg-gray-50 border-b border-gray-200 p-4">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center justify-between mb-2">
                             <span className="text-sm text-gray-600 font-baskerville">
                 {isGeneratingFiles ? 
                   `${remainingFiles} files remaining, ${Math.round(generationProgress)}% there` :
                   `${completedFiles} files completed`
                 }
               </span>
            </div>
            <Progress value={generationProgress} className="h-2" />
          </div>
        </div>
      )}

      {/* Main Content */}
      {messages.length === 0 ? (
        /* Initial state - centered layout */
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-8">
          {/* Logo */}
          <div className="mb-8">
            <button
              onClick={toggleNavbar}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <div className="w-18 h-18 duration-300 bg-transparent border border-gray-900 rounded-full flex items-center justify-center shadow-lg">
                <Image
                  src="/ceneca-light.png"
                  alt="Ceneca"
                  width={60}
                  height={60}
                  className="rounded-lg grayscale"
                />
              </div>
            </button>
          </div>

          {/* Input Area - Large and Centered with Progress Border */}
          <div className="w-full max-w-2xl relative">
            <div 
              style={deploymentProgress > 0 ? getBorderStyle(deploymentProgress) : {}}
              className="rounded-2xl"
            >
              <textarea
                value={currentMessage}
                onChange={(e) => setCurrentMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your business scenario: What data sources will you connect? How many users? What's your primary use case for Ceneca?"
                className="w-full min-h-[150px] max-h-[400px] bg-white border-1 border-gray-800 text-base px-6 py-4 pr-20 pb-16 rounded-2xl focus:outline-none resize-none placeholder-gray-500 disabled:opacity-50 shadow-lg transition-all font-baskerville"
                disabled={isLoading || isStreaming}
                rows={3}
              />
            </div>
            <Button 
              onClick={sendMessage}
              disabled={isLoading || isStreaming || !currentMessage.trim()}
              className="absolute w-10 h-10 right-2 bottom-4 text-gray-600 bg-white border-1 border-gray-800 rounded-lg p-2 transition-all duration-300 hover:bg-[#7b35b8] hover:text-white font-baskerville disabled:hidden disabled:opacity-50 transition-all"
            >
              ↵
            </Button>
          </div>

          {/* Loading indicator */}
          {(isLoading || isStreaming) && !streamingContent && (
            <div className="mt-6 flex items-center gap-2">
              <div className="w-2 h-2 bg-[#7b35b8] rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-[#7b35b8] rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
              <div className="w-2 h-2 bg-[#7b35b8] rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
            </div>
          )}
        </div>
      ) : (
        /* Conversation state - full height layout */
        <div className="flex-1 flex flex-col h-full relative">
          {/* Messages Area - 80% of available space */}
          <div className={`flex-1 px-6 pt-4 overflow-y-auto transition-all duration-300 ${
            isToolSidebarOpen ? 'mr-96' : ''
          } ${showFilesSidebar ? 'ml-80' : ''}`} style={{
            height: '80%',
            maxHeight: navbarVisible ? 'calc(85vh - 120px)' : '85vh',
            marginTop: navbarVisible ? '120px' : '0px'
          }}>
            <div className="max-w-5xl mx-auto space-y-4" style={{width: '80%'}}>
              {messages.map((message, index) => (
                <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`${message.role === 'user' ? 'max-w-[80%] order-2' : 'w-full order-1'}`}>
                    <div className={`flex items-start gap-3 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                      
                      <div className={`p-3 rounded-2xl border ${
                        message.role === 'user' 
                          ? 'bg-gray-50 border-gray-200 text-gray-900' 
                          : 'bg-white border-gray-900 text-gray-900'
                      }`}>
                        <MessageRenderer 
                          content={message.content} 
                          role={message.role}
                          toolCalls={message.toolCalls}
                          onSidebarStateChange={handleSidebarStateChange}
                        />
                        

                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Streaming message */}
              {isStreaming && streamingContent && (
                <div className="flex justify-start">
                  <div className="w-full">
                    <div className="flex items-start gap-3">
                      <div className="p-3 rounded-2xl bg-white border border-gray-900 text-gray-900">
                        <div className="text-md leading-relaxed font-baskerville prose prose-md max-w-none">
                          <MessageRenderer 
                            content={streamingContent} 
                            role="assistant"
                            toolCalls={streamingToolCalls}
                            onSidebarStateChange={handleSidebarStateChange}
                          />
                          <span className="inline-block w-2 h-4 bg-[#7b35b8] ml-1 animate-pulse"></span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* File Generation Progress Details */}
              {isGeneratingFiles && (
                <div className="w-full max-w-2xl mx-auto my-4">
                  <div className="space-y-2">
                    {progressSteps.map((step) => (
                      <div key={step.id} className="flex items-center gap-3 p-2">
                        <div className={`w-4 h-4 rounded-full flex items-center justify-center ${
                          step.completed ? 'bg-green-500' : 
                          step.current ? 'bg-[#7b35b8] animate-pulse' : 
                          'bg-gray-300'
                        }`}>
                          {step.completed && <CheckCircle className="h-3 w-3 text-white" />}
                        </div>
                        <span className={`text-sm font-baskerville ${
                          step.completed ? 'text-green-600' : 
                          step.current ? 'text-[#7b35b8] font-medium' : 
                          'text-gray-500'
                        }`}>
                          {step.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Generate Files Button */}
              {!isGeneratingFiles && extractedConfig.databases && extractedConfig.databases.length > 0 && (
                <div className="flex justify-center py-6">
                  <Button 
                    onClick={simulateFileGeneration}
                    className="bg-[#7b35b8] text-white px-8 py-3 rounded-lg font-baskerville hover:bg-[#6a2d9f] transition-all"
                  >
                    🚀 Generate Deployment Files
                  </Button>
                </div>
              )}

              {/* Loading indicator */}
              {(isLoading || isStreaming) && !streamingContent && (
                <div className="flex justify-center py-4">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-[#7b35b8] rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-[#7b35b8] rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-2 h-2 bg-[#7b35b8] rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          </div>



          {/* Input Area - Fixed at bottom */}
          <div className={`border-gray-200 px-6 pt-2 transition-all duration-300 ${
            isToolSidebarOpen ? 'mr-96' : ''
          } ${showFilesSidebar ? 'ml-80' : ''}`}>
            <div className="max-w-5xl mx-auto relative" style={{width: '80%'}}>
              <div 
                style={deploymentProgress > 0 ? getBorderStyle(deploymentProgress) : {}}
                className="rounded-2xl"
              >
                <textarea
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Continue the conversation..."
                  className="w-full min-h-[100px] max-h-[200px] bg-white border-1 border-gray-900 text-base px-4 py-3 pr-16 rounded-2xl focus:outline-none resize-none placeholder-gray-500 disabled:opacity-50 shadow-xl transition-all font-baskerville"
                  disabled={isLoading || isStreaming}
                  rows={2}
                />
              </div>
              <Button 
                onClick={sendMessage}
                disabled={isLoading || isStreaming || !currentMessage.trim()}
                className="absolute w-8 h-8 right-3 top-1/2 transform text-gray-600 bg-white border-1 border-gray-900 shadow-xl rounded-lg p-1 transition-all duration-300 hover:bg-[#7b35b8] hover:text-white font-baskerville disabled:hidden disabled:opacity-50"
              >
                ↵
              </Button>
            </div>
          </div>

          {/* Logo button and Files toggle - Bottom Right */}
          <div className="fixed bottom-6 right-6 flex flex-col gap-3 z-10">
            {/* Files toggle button */}
            {deploymentFiles.length > 0 && (
              <button
                onClick={() => setShowFilesSidebar(!showFilesSidebar)}
                className={`w-12 h-12 ${showFilesSidebar ? 'bg-purple-100 border-purple-300' : 'bg-gray-50 border-gray-200'} hover:bg-purple-100 border hover:border-purple-300 rounded-full flex items-center justify-center shadow-lg transition-all duration-200`}
                title="View deployment files"
              >
                <FileText className={`h-5 w-5 ${showFilesSidebar ? 'text-purple-600' : 'text-gray-600'}`} />
              </button>
            )}
            
            {/* Reset button - only show when we have messages */}
            {messages.length > 0 && (
              <button
                onClick={startNewConversation}
                className="w-12 h-12 bg-red-50 hover:bg-red-100 border border-red-200 hover:border-red-300 rounded-full flex items-center justify-center shadow-lg transition-all duration-200"
                title="Reset conversation"
              >
                <RotateCcw className="h-5 w-5 text-red-600" />
              </button>
            )}
            
            <button
              onClick={toggleNavbar}
              className="w-12 h-12 duration-300 bg-white border border-gray-900 rounded-full flex items-center justify-center shadow-lg hover:opacity-80 transition-opacity"
            >
              <Image
                src="/ceneca-light.png"
                alt="Ceneca"
                width={30}
                height={30}
                className="rounded-lg grayscale"
              />
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

