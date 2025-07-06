"use client";

import { useState, useEffect, useRef } from "react";
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
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [extractedConfig, setExtractedConfig] = useState<ExtractedConfig>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-start conversation when component mounts
  useEffect(() => {
    if (!conversationId) {
      startConversation();
    }
  }, []);

  const startConversation = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/chat/start', {
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
    setCurrentMessage("");
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversationId,
          message: currentMessage
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.data.message,
        timestamp: new Date()
      }]);
      
      setExtractedConfig(data.data.extractedConfig);
      
    } catch (error) {
      toast.error("Failed to send message");
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const generateFiles = async () => {
    if (!conversationId) return;

    setIsLoading(true);
    try {
      const response = await fetch('/api/chat/generate-files', {
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
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/deployment">
                <Button variant="ghost" size="sm" className="font-baskerville text-gray-600 hover:text-gray-900">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Deployment
                </Button>
              </Link>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-[#7b35b8] rounded-lg flex items-center justify-center">
                  <Bot className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold font-baskerville">Deployment Assistant</h1>
                  <p className="text-sm text-gray-500 font-baskerville">Configure your deployment</p>
                </div>
              </div>
            </div>
            
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
      <div className="max-w-4xl mx-auto px-6 py-12">
        
        {/* Messages */}
        {messages.length > 0 && (
          <div className="space-y-8 mb-12">
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
            
            {isLoading && (
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

        {/* Input - Much Bigger Like Notion */}
        <div className="sticky bottom-0 bg-white pt-6">
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <textarea
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={messages.length === 0 ? "Ask me about your deployment configuration..." : "Continue the conversation..."}
                  className="w-full min-h-[120px] max-h-[300px] bg-gray-50 border border-gray-200 font-baskerville text-base px-6 py-4 rounded-2xl focus:ring-2 focus:ring-[#7b35b8] focus:border-transparent resize-none placeholder-gray-500"
                  disabled={isLoading}
                  rows={4}
                />
              </div>
              <Button 
                onClick={sendMessage}
                disabled={isLoading || !currentMessage.trim()}
                className="bg-[#7b35b8] hover:bg-[#6b2ea5] text-white p-4 rounded-2xl h-12 w-12 flex items-center justify-center"
              >
                <Send className="h-5 w-5" />
              </Button>
            </div>
            
            {messages.length === 0 && !isLoading && (
              <div className="text-center mt-12">
                <div className="inline-flex items-center gap-2 text-gray-500 text-sm font-baskerville">
                  <Bot className="h-4 w-4" />
                  I'll help you configure your Ceneca deployment
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 