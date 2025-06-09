import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Settings, X, ChevronRight, Menu } from 'lucide-react';
import { agentClient } from '@/lib/agent-client';
import { useAuth } from '@/contexts/AuthContext';
import { UserMenu } from './UserMenu';
import { ThemeToggle } from './ThemeToggle';

interface BottomStatusBarProps {
  showAgentPanel: boolean;
  onToggleAgentPanel: (show: boolean) => void;
  breadcrumbs?: Array<{ label: string; onClick?: () => void }>;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
}

export const BottomStatusBar = ({ 
  showAgentPanel, 
  onToggleAgentPanel, 
  breadcrumbs = [],
  sidebarCollapsed = false,
  onToggleSidebar
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
        
        {/* Left side - Sidebar toggle (when collapsed) + Breadcrumbs */}
        <div className="flex items-center space-x-3 text-sm text-muted-foreground min-w-0 flex-1">
          {/* Sidebar Toggle Button - only show when collapsed */}
          {sidebarCollapsed && onToggleSidebar && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleSidebar}
              className="h-7 w-7 p-0 hover:bg-accent"
              title="Show sidebar"
            >
              <Menu className="h-4 w-4" />
            </Button>
          )}
          
          {/* Breadcrumbs */}
          <div className="flex items-center space-x-1 min-w-0 flex-1">
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