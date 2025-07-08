"use client";

import { useState, useEffect, useRef } from "react";
import { flushSync } from "react-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { Send, Bot, User, FileText, Database, Shield, Settings, CheckCircle, Menu } from "lucide-react";
import { Navbar } from "@/components/navbar";
import Image from "next/image";

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
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [extractedConfig, setExtractedConfig] = useState<ExtractedConfig>({});
  const [isGeneratingFiles, setIsGeneratingFiles] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [showNavbar, setShowNavbar] = useState(false);
  const [navbarVisible, setNavbarVisible] = useState(false);
  const [currentStage, setCurrentStage] = useState<string>("Ready to configure your deployment");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Auto-start conversation when component mounts
  useEffect(() => {
    if (!conversationId) {
      // Don't auto-start conversation - let user initiate
      // startConversation();
    }
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
      // Don't add the initial welcome message to messages array
      
    } catch (error) {
      toast.error("Failed to start conversation");
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim()) return;

    // If no conversation started yet, start it first
    if (!conversationId) {
      await startConversation();
    }

    if (!conversationId) return;

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
      const backendUrl = process.env.NODE_ENV === 'production' 
        ? 'http://localhost:3001/api/chat/message/stream'
        : 'http://localhost:3001/api/chat/message/stream';
        
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
                    setStreamingContent(data.fullContent);
                  });
                } else if (data.type === 'complete') {
                  isCompleted = true;
                  completedData = data;
                } else if (data.type === 'error') {
                  toast.error(data.message);
                  setStreamingContent("");
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
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedData.message,
          timestamp: new Date()
        }]);
        setExtractedConfig(completedData.extractedConfig);
      }
      
      setStreamingContent("");
      setIsStreaming(false);
      
    } catch (error) {
      toast.error("Failed to send message");
      console.error('Error:', error);
      setStreamingContent("");
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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
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

          {/* Input Area - Large and Centered */}
          <div className="w-full max-w-2xl relative">
            <textarea
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tell me about your deployment needs - databases, authentication, scale, environment..."
              className="w-full min-h-[150px] max-h-[400px] bg-white border-1 border-gray-800 text-base px-6 py-4 pr-20 pb-16 rounded-2xl focus:outline-none resize-none placeholder-gray-500 disabled:opacity-50 shadow-lg transition-all font-baskerville"
              disabled={isLoading || isStreaming}
              rows={3}
            />
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
          <div className="flex-1 px-6 py-4 overflow-y-auto" style={{height: '80%'}}>
            <div className="max-w-5xl mx-auto space-y-4" style={{width: '80%'}}>
              {messages.map((message, index) => (
                <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                    <div className={`flex items-start gap-3 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                        message.role === 'user' 
                          ? 'bg-gray-100 text-gray-600' 
                          : 'bg-[#7b35b8] text-white'
                      }`}>
                        {message.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                      </div>
                      <div className={`p-3 rounded-2xl border ${
                        message.role === 'user' 
                          ? 'bg-gray-50 border-gray-200 text-gray-900' 
                          : 'bg-white border-gray-200 text-gray-900'
                      }`}>
                        <p className="text-sm whitespace-pre-wrap leading-relaxed font-baskerville">
                          {message.content}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Streaming message */}
              {isStreaming && streamingContent && (
                <div className="flex justify-start">
                  <div className="max-w-[80%]">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#7b35b8] flex items-center justify-center flex-shrink-0">
                        <Bot className="h-4 w-4 text-white" />
                      </div>
                      <div className="p-3 rounded-2xl bg-white border border-gray-200 text-gray-900">
                        <p className="text-sm whitespace-pre-wrap leading-relaxed font-baskerville">
                          {streamingContent}
                          <span className="inline-block w-2 h-4 bg-[#7b35b8] ml-1 animate-pulse"></span>
                        </p>
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
          <div className="border-t border-gray-200 bg-white px-6 py-4">
            <div className="max-w-5xl mx-auto relative" style={{width: '80%'}}>
              <textarea
                value={currentMessage}
                onChange={(e) => setCurrentMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Continue the conversation..."
                className="w-full min-h-[60px] max-h-[200px] bg-white border-1 border-gray-300 text-base px-4 py-3 pr-16 rounded-2xl focus:outline-none resize-none placeholder-gray-500 disabled:opacity-50 shadow-sm transition-all font-baskerville"
                disabled={isLoading || isStreaming}
                rows={2}
              />
              <Button 
                onClick={sendMessage}
                disabled={isLoading || isStreaming || !currentMessage.trim()}
                className="absolute w-8 h-8 right-2 top-1/2 transform -translate-y-1/2 text-gray-600 bg-white border-1 border-gray-300 rounded-lg p-1 transition-all duration-300 hover:bg-[#7b35b8] hover:text-white font-baskerville disabled:hidden disabled:opacity-50"
              >
                ↵
              </Button>
            </div>
          </div>

          {/* Logo button - Bottom Right */}
          <button
            onClick={toggleNavbar}
            className="fixed bottom-6 right-6 hover:opacity-80 transition-opacity z-10"
          >
            <div className="w-12 h-12 duration-300 bg-white border border-gray-900 rounded-full flex items-center justify-center shadow-lg">
              <Image
                src="/ceneca-light.png"
                alt="Ceneca"
                width={30}
                height={30}
                className="rounded-lg grayscale"
              />
            </div>
          </button>
        </div>
      )}

    </div>
  );
}

