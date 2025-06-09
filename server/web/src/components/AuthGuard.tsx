import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoginScreen } from './LoginScreen';
import { LoadingScreen } from './LoadingScreen';

interface AuthGuardProps {
  children: React.ReactNode;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const { isAuthenticated, isLoading, authHealth } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  // If SSO is disabled or auth service is unhealthy, allow access
  if (!authHealth?.sso_enabled || authHealth.status === 'unhealthy') {
    return <>{children}</>;
  }

  // If SSO is enabled but user is not authenticated, show login
  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  // User is authenticated, show the app
  return <>{children}</>;
}; 