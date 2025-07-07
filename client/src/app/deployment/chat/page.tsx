"use client";

import { useState, useEffect, useRef } from "react";
import { flushSync } from "react-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Send, Bot, User, ArrowLeft, Download } from "lucide-react";
import Link from "next/link";

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ExtractedConfig {
  databases?: string[];
  auth?: string;
  environment?: string;
  scale?: string;
}

export default function ChatDeploymentPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [extractedConfig, setExtractedConfig] = useState<ExtractedConfig>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Monitor streaming content changes
  useEffect(() => {
    console.log('Frontend: streamingContent state changed:', streamingContent);
    console.log('Frontend: isStreaming state:', isStreaming);
    console.log('Frontend: Should show streaming message:', isStreaming && streamingContent);
  }, [streamingContent, isStreaming]);

  // Auto-start conversation when component mounts
  useEffect(() => {
    if (!conversationId) {
      startConversation();
    }
  }, []);

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
      setMessages([{
        role: 'assistant',
        content: data.data.message,
        timestamp: new Date()
      }]);
      
    } catch (error) {
      toast.error("Failed to start conversation");
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim() || !conversationId) return;

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
    
    let isCompleted = false;
    let completedData: any = null;

    try {
      // Use streaming endpoint - bypass Next.js rewrites for streaming
      const backendUrl = process.env.NODE_ENV === 'production' 
        ? 'http://localhost:3001/api/chat/message/stream'  // Direct to backend in production
        : 'http://localhost:3001/api/chat/message/stream'; // Direct to backend in development
        
      console.log(`Frontend: Making streaming request to ${backendUrl}`);
      
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversationId,
          message: messageToSend
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      // Check if response body exists
      if (!response.body) {
        throw new Error('No response body for streaming');
      }

      const startTime = Date.now();
      console.log(`Frontend: Starting to read stream... [${new Date().toISOString()}]`);
      
      // Read the stream with proper handling
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      let buffer = '';
      
      try {
        while (true) {
          const readStartTime = Date.now();
          const { done, value } = await reader.read();
          const readEndTime = Date.now();
          
          if (done) {
            console.log(`Frontend: Stream read completed [${new Date().toISOString()}] (Total time: ${Date.now() - startTime}ms)`);
            break;
          }
          
          // Decode the chunk
          const chunk = decoder.decode(value, { stream: true });
          console.log(`Frontend: Received chunk [${new Date().toISOString()}] (Read took: ${readEndTime - readStartTime}ms):`, chunk);
          buffer += chunk;
          
          // Process complete lines (Server-Sent Events format)
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.trim() === '') continue; // Skip empty lines
            
            if (line.startsWith('data: ')) {
              try {
                const dataStr = line.slice(6); // Remove 'data: ' prefix
                console.log('Frontend: Processing SSE data:', dataStr);
                const data = JSON.parse(dataStr);
                
                if (data.type === 'chunk') {
                  console.log('Frontend: Updating streaming content:', data.content);
                  console.log('Frontend: Full content length:', data.fullContent.length);
                  console.log('Frontend: isStreaming before update:', isStreaming);
                  
                  // Force React to update the UI immediately
                  flushSync(() => {
                    setStreamingContent(data.fullContent);
                  });
                  
                  console.log('Frontend: streamingContent updated to:', data.fullContent);
                } else if (data.type === 'complete') {
                  // Mark as completed but don't end streaming yet
                  console.log('Frontend: Stream completion message received');
                  isCompleted = true;
                  completedData = data;
                  // Don't return here, let the stream finish naturally
                } else if (data.type === 'error') {
                  console.log('Frontend: Stream error:', data.message);
                  toast.error(data.message);
                  setStreamingContent("");
                  setIsStreaming(false);
                  return; // Exit on error
                } else if (data.type === 'status') {
                  console.log('Frontend: Stream status:', data.message);
                }
              } catch (e) {
                console.error('Frontend: Error parsing streaming data:', e, 'Line:', line);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
      
      // Handle completion after stream ends
      if (isCompleted && completedData) {
        console.log('Frontend: Processing completion after stream ended');
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedData.message,
          timestamp: new Date()
        }]);
        setExtractedConfig(completedData.extractedConfig);
      }
      
      // If we reach here, streaming is done
      console.log('Frontend: Stream processing completed, setting isStreaming to false');
      setStreamingContent("");
      setIsStreaming(false);
      
    } catch (error) {
      toast.error("Failed to send message");
      console.error('Error:', error);
      setStreamingContent("");
      setIsStreaming(false); // Set streaming to false on error
    }
  };

  const generateFiles = async () => {
    if (!conversationId) return;

    setIsLoading(true);
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
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-screen bg-white flex flex-col pt-24">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white flex-shrink-0">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            
            {/* Configuration Pills */}
            {Object.keys(extractedConfig).length > 0 && (
              <div className="flex items-center gap-2">
                {extractedConfig.databases && extractedConfig.databases.map((db) => (
                  <Badge key={db} variant="secondary" className="font-baskerville text-xs">
                    {db}
                  </Badge>
                ))}
                {extractedConfig.auth && (
                  <Badge variant="secondary" className="font-baskerville text-xs">
                    {extractedConfig.auth}
                  </Badge>
                )}
                {extractedConfig.environment && (
                  <Badge variant="secondary" className="font-baskerville text-xs">
                    {extractedConfig.environment}
                  </Badge>
                )}
                {Object.keys(extractedConfig).length > 0 && (
                  <Button
                    onClick={generateFiles}
                    size="sm"
                    className="text-white bg-[#7b35b8] hover:bg-[#6b2ea5] font-baskerville"
                  >
                    <Download className="h-3 w-3 mr-1" />
                    Generate Files
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col max-w-4xl mx-auto px-6 py-6 overflow-hidden">
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto mb-4">
          {messages.length > 0 && (
            <div className="space-y-8 pb-4">
              {messages.map((message, index) => (
                <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[70%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                    <div className={`flex items-start gap-4 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                        message.role === 'user' 
                          ? 'bg-gray-100 text-gray-600' 
                          : 'bg-[#7b35b8] text-white'
                      }`}>
                        {message.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                      </div>
                      <div className={`p-5 rounded-xl ${
                        message.role === 'user' 
                          ? 'bg-gray-100 text-gray-900' 
                          : 'bg-gray-50 text-gray-900'
                      }`}>
                        <p className="text-sm whitespace-pre-wrap font-baskerville leading-relaxed">
                          {message.content}
                        </p>
                        <p className="text-xs text-gray-500 mt-3 font-baskerville">
                          {message.timestamp.toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Streaming message */}
              {isStreaming && streamingContent && (
                <div className="flex justify-start">
                  <div className="max-w-[70%]">
                    <div className="flex items-start gap-4">
                      <div className="w-8 h-8 rounded-full bg-[#7b35b8] flex items-center justify-center flex-shrink-0">
                        <Bot className="h-4 w-4 text-white" />
                      </div>
                      <div className="p-5 rounded-xl bg-gray-50 text-gray-900">
                        <p className="text-sm whitespace-pre-wrap font-baskerville leading-relaxed">
                          {streamingContent}
                          <span className="inline-block w-2 h-4 bg-[#7b35b8] ml-1 animate-pulse"></span>
                        </p>
                        <p className="text-xs text-gray-500 mt-3 font-baskerville">
                          Streaming... (Length: {streamingContent.length})
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Debug info */}
              {process.env.NODE_ENV === 'development' && (
                <div className="text-xs text-gray-400 p-2 bg-gray-50 rounded">
                  Debug: isStreaming={isStreaming.toString()}, streamingContent.length={streamingContent.length}, condition={((isStreaming && streamingContent) ? 'true' : 'false')}
                </div>
              )}
              
              {(isLoading || isStreaming) && !streamingContent && (
                <div className="flex justify-start">
                  <div className="flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-[#7b35b8] flex items-center justify-center">
                      <Bot className="h-4 w-4 text-white animate-pulse" />
                    </div>
                    <div className="bg-gray-50 p-5 rounded-xl">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
          
          {messages.length === 0 && !isLoading && !isStreaming && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="inline-flex items-center gap-2 text-gray-500 text-sm font-baskerville">
                  <Bot className="h-4 w-4" />
                  I'll help you configure your Ceneca deployment
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input - Much Bigger Like Notion */}
        <div className="flex-shrink-0 bg-white border-t border-gray-100 pt-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <textarea
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={messages.length === 0 ? "Ask me about your deployment configuration..." : "Continue the conversation..."}
                  className="w-full min-h-[120px] max-h-[300px] bg-gray-50 border border-gray-200 font-baskerville text-base px-6 py-4 rounded-2xl focus:ring-2 focus:ring-[#7b35b8] focus:border-transparent resize-none placeholder-gray-500 disabled:opacity-50"
                  disabled={isLoading || isStreaming}
                  rows={4}
                />
              </div>
              <Button 
                onClick={sendMessage}
                disabled={isLoading || isStreaming || !currentMessage.trim()}
                className="bg-[#7b35b8] hover:bg-[#6b2ea5] text-white p-4 rounded-2xl h-12 w-12 flex items-center justify-center disabled:opacity-50"
              >
                <Send className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 