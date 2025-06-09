import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { authClient, AuthUser, AuthHealth } from '@/lib/auth-client';

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  authHealth: AuthHealth | null;
  login: () => void;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authHealth, setAuthHealth] = useState<AuthHealth | null>(null);

  const checkAuthHealth = async () => {
    try {
      const health = await authClient.checkHealth();
      setAuthHealth(health);
      return health;
    } catch (error) {
      console.error('Auth health check failed:', error);
      setAuthHealth({
        status: 'unhealthy',
        sso_enabled: false,
        message: 'Authentication service unavailable'
      });
      return null;
    }
  };

  const checkCurrentUser = async () => {
    try {
      const currentUser = await authClient.getCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch (error) {
      console.error('Failed to check current user:', error);
      setUser(null);
      return null;
    }
  };

  const refresh = async () => {
    setIsLoading(true);
    await Promise.all([
      checkAuthHealth(),
      checkCurrentUser()
    ]);
    setIsLoading(false);
  };

  const login = () => {
    authClient.redirectToLogin();
  };

  const logout = async () => {
    try {
      await authClient.logout();
      setUser(null);
    } catch (error) {
      console.error('Logout failed:', error);
      // Force clear user state even if logout request fails
      setUser(null);
    }
  };

  // Initial auth state check
  useEffect(() => {
    refresh();
  }, []);

  // Handle OAuth callback - check if we're on the callback URL
  useEffect(() => {
    const handleOAuthCallback = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has('code') && urlParams.has('state')) {
        // We're in an OAuth callback - wait a moment for backend to process
        // then check user state
        setTimeout(async () => {
          await checkCurrentUser();
          setIsLoading(false);
          
          // Clean up URL
          window.history.replaceState({}, document.title, window.location.pathname);
        }, 1000);
      }
    };

    handleOAuthCallback();
  }, []);

  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated,
        authHealth,
        login,
        logout,
        refresh,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 