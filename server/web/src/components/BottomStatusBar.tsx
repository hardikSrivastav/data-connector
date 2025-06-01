import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Settings, X, ChevronRight } from 'lucide-react';
import { agentClient } from '@/lib/agent-client';

interface BottomStatusBarProps {
  showAgentPanel: boolean;
  onToggleAgentPanel: (show: boolean) => void;
  breadcrumbs?: Array<{ label: string; onClick?: () => void }>;
}

export const BottomStatusBar = ({ 
  showAgentPanel, 
  onToggleAgentPanel, 
  breadcrumbs = [] 
}: BottomStatusBarProps) => {
  const [agentStatus, setAgentStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  // Test agent connection on mount and periodically
  useEffect(() => {
    const testAgentConnection = async () => {
      try {
        const isOnline = await agentClient.testConnection();
        setAgentStatus(isOnline ? 'online' : 'offline');
      } catch (error) {
        console.warn('Agent connection test failed:', error);
        setAgentStatus('offline');
      }
    };

    testAgentConnection();
    
    // Test connection periodically
    const interval = setInterval(testAgentConnection, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  }, []);

  const handleRetryConnection = async () => {
    setAgentStatus('checking');
    const isOnline = await agentClient.testConnection();
    setAgentStatus(isOnline ? 'online' : 'offline');
  };

  return (
    <div className="bg-white border-t border-gray-200 shadow-lg">
      <div className="flex items-center justify-between px-4 py-2 max-w-full">
        
        {/* Left side - Breadcrumbs */}
        <div className="flex items-center space-x-1 text-sm text-gray-600 min-w-0 flex-1">
          {breadcrumbs.length > 0 ? (
            breadcrumbs.map((crumb, index) => (
              <div key={index} className="flex items-center space-x-1">
                {index > 0 && <ChevronRight className="h-3 w-3 text-gray-400" />}
                <button
                  onClick={crumb.onClick}
                  className={`truncate hover:text-gray-900 ${
                    crumb.onClick ? 'cursor-pointer' : 'cursor-default'
                  }`}
                >
                  {crumb.label}
                </button>
              </div>
            ))
          ) : (
            <div className="text-gray-400 text-xs">Ready for navigation breadcrumbs...</div>
          )}
        </div>

        {/* Center - Agent Status */}
        <div className="flex items-center space-x-3 px-4">
          <div className="flex items-center space-x-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${
              agentStatus === 'online' ? 'bg-green-500' : 
              agentStatus === 'offline' ? 'bg-red-500' : 
              'bg-yellow-500 animate-pulse'
            }`} />
            <span className="text-gray-700 hidden sm:inline">
              AI Agent: {
                agentStatus === 'online' ? 'Connected' :
                agentStatus === 'offline' ? 'Disconnected' :
                'Checking...'
              }
            </span>
            <span className="text-gray-700 sm:hidden">
              {agentStatus === 'online' ? '🟢' : agentStatus === 'offline' ? '🔴' : '🟡'}
            </span>
            {agentStatus === 'offline' && (
              <button
                onClick={handleRetryConnection}
                className="text-blue-600 hover:text-blue-800 text-xs underline"
              >
                Retry
              </button>
            )}
          </div>
        </div>

        {/* Right side - Test AI Agent Button */}
        <div className="flex items-center space-x-2">
          {!showAgentPanel ? (
            <Button
              onClick={() => onToggleAgentPanel(true)}
              size="sm"
              variant="outline"
              className="bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-200"
            >
              <Settings className="h-3 w-3 mr-1" />
              <span className="hidden sm:inline">Test AI Agent</span>
              <span className="sm:hidden">Test</span>
            </Button>
          ) : (
            <Button
              onClick={() => onToggleAgentPanel(false)}
              size="sm"
              variant="outline"
              className="bg-gray-50 hover:bg-gray-100"
            >
              <X className="h-3 w-3 mr-1" />
              <span className="hidden sm:inline">Close Panel</span>
              <span className="sm:hidden">Close</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}; 