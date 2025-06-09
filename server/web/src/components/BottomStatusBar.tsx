import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Settings, X, ChevronRight } from 'lucide-react';
import { agentClient } from '@/lib/agent-client';
import { useAuth } from '@/contexts/AuthContext';
import { UserMenu } from './UserMenu';
import { ThemeToggle } from './ThemeToggle';

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
  const { isAuthenticated } = useAuth();

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
    <div className="bg-background border-t border-border shadow-lg">
      <div className="flex items-center justify-between px-4 py-2 max-w-full">
        
        {/* Left side - Breadcrumbs */}
        <div className="flex items-center space-x-1 text-sm text-muted-foreground min-w-0 flex-1">
          {breadcrumbs.length > 0 ? (
            breadcrumbs.map((crumb, index) => (
              <div key={index} className="flex items-center space-x-1">
                {index > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
                <button
                  onClick={crumb.onClick}
                  className={`truncate hover:text-foreground ${
                    crumb.onClick ? 'cursor-pointer' : 'cursor-default'
                  }`}
                >
                  {crumb.label}
                </button>
              </div>
            ))
          ) : (
            <div className="text-muted-foreground text-xs">Ready for navigation breadcrumbs...</div>
          )}
        </div>

        {/* Center - Agent Status */}


        {/* Right side - Theme Toggle, User Menu & Test AI Agent Button */}
        <div className="flex items-center space-x-3">
          {/* Theme Toggle */}
          <ThemeToggle />
          
          {/* User Menu (only when authenticated) */}
          {isAuthenticated && <UserMenu />}
        </div>
      </div>
    </div>
  );
}; 