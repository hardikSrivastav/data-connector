import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  MessageSquare, 
  Download, 
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import { apiService } from '../services/apiService';
import { websocketService } from '../services/websocketService';
import type { Session, WorkspaceData, FileContent, ChatMessage } from '../types';

export const EditorPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [session, setSession] = useState<Session | null>(null);
  const [workspaceData, setWorkspaceData] = useState<WorkspaceData | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'files' | 'chat'>('chat');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionId) {
      loadSessionData();
      initializeChat();
    }
    
    return () => {
      websocketService.disconnect();
    };
  }, [sessionId]);

  const loadSessionData = async () => {
    if (!sessionId) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const [sessionData, workspaceData] = await Promise.all([
        apiService.getSession(sessionId),
        apiService.getWorkspace(sessionId)
      ]);
      
      setSession(sessionData);
      setWorkspaceData(workspaceData);
      
      // Select first file by default
      if (workspaceData.files.length > 0) {
        setSelectedFile(workspaceData.files[0]);
      }
      
    } catch (err) {
      console.error('Failed to load session data:', err);
      setError(apiService.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const initializeChat = async () => {
    if (!sessionId) return;
    
    try {
      // Set up event handlers BEFORE connecting
      websocketService.onConnection((connected) => {
        console.log('WebSocket connection status changed:', connected);
        setIsConnected(connected);
      });

      websocketService.onMessage((message) => {
        console.log('WebSocket message received:', message);
        const aiMessage: ChatMessage = {
          id: Date.now().toString(),
          role: 'assistant',
          content: message,
          timestamp: new Date().toISOString(),
        };
        
        setMessages(prev => [...prev, aiMessage]);
        setIsLoading(false);
        
        // Reload workspace data when AI makes changes
        loadSessionData();
      });
      
      // Now connect to WebSocket
      await websocketService.connect(sessionId);
      
      // Check connection status after a brief delay to ensure handlers are set
      setTimeout(() => {
        websocketService.checkConnectionStatus();
      }, 100);
      
      // Send initial greeting
      const initialMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: 'Welcome! I\'m your AI assistant. I\'ll help you customize your authentication template. What would you like to configure?',
        timestamp: new Date().toISOString(),
      };
      
      setMessages([initialMessage]);
      
    } catch (error) {
      console.error('Failed to initialize chat:', error);
      setIsConnected(false);
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: 'Failed to connect to AI assistant. Please try refreshing the page.',
        timestamp: new Date().toISOString(),
      };
      setMessages([errorMessage]);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || !isConnected || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      websocketService.sendMessage(inputMessage);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: 'Failed to send message. Please check your connection.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleDownload = async () => {
    if (!workspaceData) return;
    
    try {
      const content = workspaceData.files.map(file => 
        `// File: ${file.path}\n${file.content}\n\n`
      ).join('');
      
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auth-template-${session?.template_version}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      
    } catch (err) {
      console.error('Failed to download files:', err);
    }
  };

  const handleBackToHome = () => {
    navigate('/');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-secondary-600">Loading editor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card bg-red-50 border-red-200">
        <div className="flex items-center space-x-2 text-red-800">
          <AlertCircle className="w-5 h-5" />
          <div>
            <h2 className="text-lg font-semibold mb-2">Error</h2>
            <p className="mb-4">{error}</p>
            <div className="space-x-2">
              <button onClick={loadSessionData} className="btn btn-outline">
                Try Again
              </button>
              <button onClick={handleBackToHome} className="btn btn-secondary">
                Back to Home
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!session || !workspaceData) {
    return (
      <div className="card">
        <p className="text-secondary-600">Session not found</p>
        <button onClick={handleBackToHome} className="mt-4 btn btn-primary">
          Back to Home
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-secondary-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={handleBackToHome}
              className="btn btn-outline flex items-center space-x-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            
            <div>
              <h1 className="text-xl font-bold text-secondary-900">
                Template Editor
              </h1>
              <p className="text-sm text-secondary-600">
                {session.template_version} • Session: {session.id.slice(0, 8)}...
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Connection Status */}
            <div className="flex items-center space-x-2">
              {isConnected ? (
                <CheckCircle className="w-5 h-5 text-green-600" />
              ) : (
                <AlertCircle className="w-5 h-5 text-red-600" />
              )}
              <span className={`text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>

            <button
              onClick={loadSessionData}
              className="btn btn-outline"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            <button
              onClick={handleDownload}
              className="btn btn-primary flex items-center space-x-2"
            >
              <Download className="w-4 h-4" />
              <span>Download</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Left Sidebar - File List */}
        <div className="w-64 bg-white border-r border-secondary-200 overflow-y-auto">
          <div className="p-4">
            <h3 className="font-medium text-secondary-900 mb-3">Files</h3>
            <div className="space-y-1">
              {workspaceData.files.map((file) => (
                <button
                  key={file.path}
                  onClick={() => {
                    setSelectedFile(file);
                    setActiveTab('files');
                  }}
                  className={`w-full text-left p-2 rounded-lg transition-colors ${
                    selectedFile?.path === file.path
                      ? 'bg-primary-100 text-primary-800'
                      : 'hover:bg-secondary-100'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4" />
                    <span className="text-sm">{file.path}</span>
                    {file.modified && (
                      <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          {/* Tab Navigation */}
          <div className="flex border-b border-secondary-200 bg-white">
            <button
              onClick={() => setActiveTab('files')}
              className={`px-4 py-2 font-medium ${
                activeTab === 'files'
                  ? 'border-b-2 border-primary-600 text-primary-600'
                  : 'text-secondary-600 hover:text-secondary-900'
              }`}
            >
              <FileText className="w-4 h-4 inline mr-2" />
              Files
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-4 py-2 font-medium ${
                activeTab === 'chat'
                  ? 'border-b-2 border-primary-600 text-primary-600'
                  : 'text-secondary-600 hover:text-secondary-900'
              }`}
            >
              <MessageSquare className="w-4 h-4 inline mr-2" />
              AI Assistant
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-hidden">
            {activeTab === 'files' && selectedFile && (
              <div className="h-full p-4">
                <div className="h-full border border-secondary-300 rounded-lg overflow-hidden">
                  <div className="bg-secondary-50 px-4 py-2 border-b border-secondary-300">
                    <h4 className="font-medium text-secondary-900">{selectedFile.path}</h4>
                  </div>
                  <div className="p-4 h-full overflow-auto">
                    <pre className="text-sm text-secondary-800 whitespace-pre-wrap">
                      {selectedFile.content}
                    </pre>
                  </div>
                </div>
              </div>
            )}
            
            {activeTab === 'chat' && (
              <div className="flex flex-col h-full">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                          message.role === 'user'
                            ? 'bg-primary-600 text-white'
                            : message.role === 'system'
                            ? 'bg-yellow-100 text-yellow-800 border border-yellow-300'
                            : 'bg-secondary-100 text-secondary-900'
                        }`}
                      >
                        <div className="text-sm whitespace-pre-wrap">
                          {message.content}
                        </div>
                        <div className="text-xs opacity-70 mt-1">
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-secondary-100 text-secondary-900 px-4 py-2 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600"></div>
                          <span className="text-sm">AI is thinking...</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Input */}
                <div className="p-4 bg-white border-t border-secondary-200">
                  <div className="flex space-x-2">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Ask me anything about your template configuration..."
                      className="flex-1 resize-none input"
                      rows={1}
                      disabled={!isConnected || isLoading}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!isConnected || isLoading || !inputMessage.trim()}
                      className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Send
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};