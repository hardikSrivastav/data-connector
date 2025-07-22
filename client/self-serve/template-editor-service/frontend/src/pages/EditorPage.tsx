import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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

  // Local storage key for this session's chat
  const getStorageKey = () => `chat_messages_${sessionId}`;

  // Check if localStorage is available
  const isLocalStorageAvailable = () => {
    try {
      const test = '__localStorage_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  };

  // Save messages to localStorage
  const saveMessagesToStorage = (messages: ChatMessage[]) => {
    if (!sessionId || !isLocalStorageAvailable()) return;
    try {
      localStorage.setItem(getStorageKey(), JSON.stringify(messages));
    } catch (error) {
      console.warn('Failed to save messages to localStorage:', error);
    }
  };

  // Load messages from localStorage
  const loadMessagesFromStorage = (): ChatMessage[] => {
    if (!sessionId || !isLocalStorageAvailable()) return [];
    try {
      const stored = localStorage.getItem(getStorageKey());
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.warn('Failed to load messages from localStorage:', error);
      return [];
    }
  };

  // Clear messages from localStorage
  const clearMessagesFromStorage = () => {
    if (!sessionId || !isLocalStorageAvailable()) return;
    try {
      localStorage.removeItem(getStorageKey());
    } catch (error) {
      console.warn('Failed to clear messages from localStorage:', error);
    }
  };

  // Update messages state and persist to localStorage
  const updateMessages = (newMessages: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
    setMessages(prev => {
      const updated = typeof newMessages === 'function' ? newMessages(prev) : newMessages;
      saveMessagesToStorage(updated);
      return updated;
    });
  };

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
      // Load existing messages from localStorage first
      const existingMessages = loadMessagesFromStorage();
      
      // Set up event handlers BEFORE connecting
      websocketService.onConnection((connected) => {
        console.log('WebSocket connection status changed:', connected);
        setIsConnected(connected);
      });

      websocketService.onMessage((message) => {
        console.log('WebSocket message received:', message);
        
        // Filter out initialization messages
        const initMessages = [
          'Connected to AI assistant',
          'AI assistant initialized successfully. How can I help you customize your authentication template?'
        ];
        
        if (initMessages.some(initMsg => message.includes(initMsg))) {
          console.log('Filtering out initialization message:', message);
          return;
        }
        
        const aiMessage: ChatMessage = {
          id: Date.now().toString(),
          role: 'assistant',
          content: message,
          timestamp: new Date().toISOString(),
        };
        
        updateMessages(prev => [...prev, aiMessage]);
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
      
      // Only show welcome message if no existing messages
      if (existingMessages.length === 0) {
        const isScenario = session?.scenario_id;
        const scenarioName = session?.metadata?.scenario_name || 'deployment';
        const templateCount = session?.metadata?.template_count || 1;
        
        const greeting = isScenario 
          ? `Welcome! I'm your AI deployment assistant. I'll help you configure your ${scenarioName.toLowerCase()} with ${templateCount} related files. I can coordinate changes across all files to ensure consistency. What would you like to configure?`
          : `Welcome! I'm your AI assistant. I'll help you customize your template. What would you like to configure?`;
        
        const initialMessage: ChatMessage = {
          id: Date.now().toString(),
          role: 'system',
          content: greeting,
          timestamp: new Date().toISOString(),
        };
        
        updateMessages([initialMessage]);
      } else {
        // Restore existing messages
        updateMessages(existingMessages);
      }
      
    } catch (error) {
      console.error('Failed to initialize chat:', error);
      setIsConnected(false);
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: 'Failed to connect to AI assistant. Please try refreshing the page.',
        timestamp: new Date().toISOString(),
      };
      updateMessages([errorMessage]);
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

    updateMessages(prev => [...prev, userMessage]);
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
      updateMessages(prev => [...prev, errorMessage]);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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

  const handleClearChat = () => {
    if (confirm('Are you sure you want to clear the chat history? This action cannot be undone.')) {
      clearMessagesFromStorage();
      updateMessages([]);
      
      // Show welcome message again after clearing
      const isScenario = session?.scenario_id;
      const scenarioName = session?.metadata?.scenario_name || 'deployment';
      const templateCount = session?.metadata?.template_count || 1;
      
      const greeting = isScenario 
        ? `Welcome! I'm your AI deployment assistant. I'll help you configure your ${scenarioName.toLowerCase()} with ${templateCount} related files. I can coordinate changes across all files to ensure consistency. What would you like to configure?`
        : `Welcome! I'm your AI assistant. I'll help you customize your template. What would you like to configure?`;
      
      const initialMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'system',
        content: greeting,
        timestamp: new Date().toISOString(),
      };
      
      updateMessages([initialMessage]);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground font-baskerville">Loading editor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card bg-red-50 border-red-200">
        <div className="text-red-800">
          <h2 className="text-lg font-semibold mb-2 font-baskerville">Error</h2>
          <p className="mb-4 font-baskerville">{error}</p>
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
    );
  }

  if (!session || !workspaceData) {
    return (
      <div className="card">
        <p className="text-muted-foreground font-baskerville">Session not found</p>
        <button onClick={handleBackToHome} className="mt-4 btn btn-primary">
          Back to Home
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Compact Header */}
      <div className="navbar-glass border-b border-border px-4 py-2 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={handleBackToHome}
              className="text-sm text-muted-foreground hover:text-foreground font-baskerville"
            >
              ← Back
            </button>
            <div className="text-sm font-baskerville">
              <span className="text-muted-foreground ml-2">
                {session.scenario_id 
                  ? `${session.metadata?.scenario_name} (${session.metadata?.template_count} files)`
                  : session.template_version
                }
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`}></div>
              <span className={`text-sm font-baskerville ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <button
              onClick={loadSessionData}
              className="text-sm text-muted-foreground hover:text-foreground font-baskerville"
            >
              Refresh
            </button>
            <button
              onClick={handleClearChat}
              className="text-sm text-red-600 hover:text-red-700 font-baskerville"
              title="Clear chat history"
            >
              Clear Chat
            </button>
            <button
              onClick={handleDownload}
              className="text-sm bg-primary text-primary-foreground px-3 py-1 rounded font-baskerville hover:bg-primary/90"
            >
              Download
            </button>
          </div>
        </div>
      </div>

      {/* Main Content - Single Viewport */}
      <div className="flex-1 flex min-h-0">
        {/* Compact File Sidebar */}
        <div className="w-64 bg-card border-r border-border flex flex-col">
          <div className="p-3 border-b border-border flex-shrink-0">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium font-baskerville">Files</h3>
              {session?.scenario_id && (
                <span className="text-xs bg-muted text-muted-foreground px-2 py-1 rounded font-baskerville">
                  {workspaceData.files.length}
                </span>
              )}
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-3">
            <div className="space-y-2">
              {workspaceData.files.map((file) => {
                const fileExtension = file.path.split('.').pop();
                const isConfig = file.path.includes('config');
                const isDocker = file.path.includes('docker-compose') || file.path.includes('compose');
                const isNginx = file.path.includes('nginx');
                const isAuth = file.path.includes('auth');
                
                let categoryColor = 'text-muted-foreground';
                let categoryLabel = 'config';
                
                if (isDocker) {
                  categoryColor = 'text-blue-600';
                  categoryLabel = 'deployment';
                } else if (isNginx) {
                  categoryColor = 'text-purple-600';
                  categoryLabel = 'infrastructure';
                } else if (isAuth) {
                  categoryColor = 'text-red-600';
                  categoryLabel = 'authentication';
                } else if (isConfig) {
                  categoryColor = 'text-green-600';
                  categoryLabel = 'configuration';
                }
                
                return (
                  <button
                    key={file.path}
                    onClick={() => {
                      setSelectedFile(file);
                      setActiveTab('files');
                    }}
                    className={`w-full text-left p-2 rounded transition-colors border font-baskerville text-xs ${
                      selectedFile?.path === file.path
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'border-border hover:bg-accent/50'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="font-medium truncate font-mono">
                        {file.path}
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`text-xs ${categoryColor}`}>
                          {categoryLabel}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {fileExtension?.toUpperCase()}
                        </span>
                        {file.modified && (
                          <div className="w-1.5 h-1.5 bg-yellow-400 rounded-full"></div>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Compact Tab Navigation */}
          <div className="flex border-b border-border bg-card flex-shrink-0">
            <button
              onClick={() => setActiveTab('files')}
              className={`px-4 py-2 font-medium font-baskerville text-sm ${
                activeTab === 'files'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Files
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-4 py-2 font-medium font-baskerville text-sm ${
                activeTab === 'chat'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="flex items-center space-x-2">
                <span>{session?.scenario_id ? 'Assistant' : 'AI Assistant'}</span>
                {messages.length > 1 && (
                  <span className="text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                    {messages.length - 1}
                  </span>
                )}
              </div>
            </button>
          </div>

          {/* Tab Content - Fills remaining space */}
          <div className="flex-1 min-h-0">
            {activeTab === 'files' && selectedFile && (
              <div className="h-full flex flex-col">
                <div className="bg-muted px-4 py-2 border-b border-border flex-shrink-0">
                  <h4 className="font-medium font-mono text-sm">{selectedFile.path}</h4>
                </div>
                <div className="flex-1 overflow-auto p-4 bg-background">
                  <pre className="font-mono whitespace-pre-wrap text-foreground text-sm leading-relaxed">
                    {selectedFile.content}
                  </pre>
                </div>
              </div>
            )}
            
            {activeTab === 'chat' && (
              <div className="flex flex-col h-full">
                {/* Messages - Scrollable area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-md px-4 py-3 rounded-lg ${
                          message.role === 'user'
                            ? 'bg-primary text-primary-foreground'
                            : message.role === 'system'
                            ? 'bg-yellow-50 text-yellow-800 border border-yellow-200'
                            : 'bg-muted text-foreground'
                        }`}
                      >
                        <div className="whitespace-pre-wrap font-baskerville text-sm leading-relaxed">
                          {message.content}
                        </div>
                        <div className="text-xs opacity-70 mt-2 font-baskerville">
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-muted text-foreground px-4 py-3 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                          <span className="font-baskerville text-sm">AI is thinking...</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Input - Fixed at bottom */}
                <div className="p-4 bg-card border-t border-border flex-shrink-0">
                  <div className="flex space-x-3">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder={session?.scenario_id 
                        ? "Ask me about your deployment configuration..."
                        : "Ask me about your template configuration..."
                      }
                      className="flex-1 resize-none input text-sm"
                      rows={2}
                      disabled={!isConnected || isLoading}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!isConnected || isLoading || !inputMessage.trim()}
                      className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed text-sm px-4 py-2"
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