import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Loader2, Database, Shield, User } from 'lucide-react';

export const LoginScreen: React.FC = () => {
  const { login, authHealth } = useAuth();
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = () => {
    setIsLoggingIn(true);
    login();
    // Note: The page will redirect, so we don't need to reset loading state
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted">
      <div className="w-full max-w-md">
        {/* Logo/Title */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="w-12 h-12 bg-blue-600 dark:bg-blue-500 rounded-lg flex items-center justify-center">
              <Database className="h-6 w-6 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Data Connector
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Sign in to access your workspace
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-card rounded-lg border border-border p-6 shadow-sm">
          {/* SSO Status */}
          {authHealth && (
            <div className="mb-6">
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-2">
                <Shield className="h-4 w-4" />
                <span>Single Sign-On</span>
                <div className={`w-2 h-2 rounded-full ${
                  authHealth.status === 'healthy' 
                    ? 'bg-green-500' 
                    : authHealth.status === 'degraded'
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`} />
              </div>
              
              {authHealth.okta_connected && authHealth.okta_issuer && (
                <div className="text-xs text-gray-500 dark:text-gray-400 pl-6">
                  Connected to {authHealth.okta_issuer.replace('https://', '')}
                </div>
              )}
            </div>
          )}

          {/* Login Button */}
          <Button
            onClick={handleLogin}
            disabled={isLoggingIn || authHealth?.status === 'unhealthy'}
            className="w-full h-11 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-md font-medium"
          >
            {isLoggingIn ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Redirecting...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <User className="h-4 w-4" />
                <span>Continue with SSO</span>
              </div>
            )}
          </Button>

          {/* Status Message */}
          {authHealth?.message && (
            <div className={`mt-4 p-3 rounded-md text-sm ${
              authHealth.status === 'healthy'
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
                : authHealth.status === 'degraded'
                ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800'
                : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
            }`}>
              {authHealth.message}
            </div>
          )}

          {/* Role Info */}
          {authHealth?.configured_roles && Object.keys(authHealth.configured_roles).length > 0 && (
            <div className="mt-4 pt-4 border-t border-border">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Available roles:</div>
              <div className="flex flex-wrap gap-1">
                {Object.keys(authHealth.configured_roles).map((role) => (
                  <span
                    key={role}
                    className="px-2 py-1 bg-muted text-muted-foreground rounded text-xs"
                  >
                    {role}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Secure authentication powered by Okta
          </p>
        </div>
      </div>
    </div>
  );
}; 