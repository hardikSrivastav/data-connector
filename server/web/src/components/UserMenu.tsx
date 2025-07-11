import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { 
  User, 
  LogOut, 
  Shield, 
  Loader2,
  ChevronDown 
} from 'lucide-react';

export const UserMenu: React.FC = () => {
  const { user, logout, authHealth } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  if (!user) {
    return null;
  }

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  const getUserInitials = (name: string): string => {
    return name
      .split(' ')
      .map(part => part[0]?.toUpperCase())
      .filter(Boolean)
      .slice(0, 2)
      .join('');
  };

  const formatRoles = (roles: string[]): string => {
    if (!roles || roles.length === 0) return 'No roles';
    if (roles.length === 1) return roles[0];
    if (roles.length === 2) return roles.join(' & ');
    return `${roles[0]} & ${roles.length - 1} more`;
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 py-1 gap-2 hover:bg-accent transition-colors"
        >
          <div className="w-6 h-6 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center p-1">
            <img 
              src="/340-coding.svg" 
              alt="Profile" 
              className="w-full h-full object-contain filter dark:invert"
            />
          </div>
          <span className="text-sm text-gray-700 dark:text-gray-300 max-w-32 truncate">
            {user.name}
          </span>
          <ChevronDown className="h-3 w-3 text-gray-400 dark:text-gray-500" />
        </Button>
      </DropdownMenuTrigger>
      
      <DropdownMenuContent align="end" className="w-64 bg-card border-border">
        <DropdownMenuLabel className="pb-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center p-1.5">
              <img 
                src="/340-coding.svg" 
                alt="Profile" 
                className="w-full h-full object-contain filter dark:invert"
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium text-gray-900 dark:text-gray-100 truncate">
                {user.name}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                {user.email}
              </div>
            </div>
          </div>
        </DropdownMenuLabel>
        
        <DropdownMenuSeparator />
        
        {/* Role Information */}
        <div className="px-2 py-2">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
            <Shield className="h-3 w-3" />
            <span>Roles</span>
          </div>
          <div className="text-xs text-gray-700 dark:text-gray-300 pl-5">
            {formatRoles(user.roles)}
          </div>
          
          {user.dev_mode && (
            <div className="mt-2 px-2 py-1 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded text-xs text-yellow-700 dark:text-yellow-300">
              Development Mode
            </div>
          )}
        </div>
        
        <DropdownMenuSeparator />
        
        {/* Auth Status */}
        {authHealth && (
          <>
            <div className="px-2 py-2">
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  authHealth.status === 'healthy' 
                    ? 'bg-green-500' 
                    : authHealth.status === 'degraded'
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`} />
                <span className="text-gray-500 dark:text-gray-400">
                  Authentication {authHealth.status}
                </span>
              </div>
              {authHealth.okta_connected && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Connected via Okta SSO
                </div>
              )}
            </div>
            <DropdownMenuSeparator />
          </>
        )}
        
        {/* Logout */}
        <DropdownMenuItem
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400 focus:bg-red-50 dark:focus:bg-red-900/20 cursor-pointer"
        >
          {isLoggingOut ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Signing out...
            </>
          ) : (
            <>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </>
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}; 