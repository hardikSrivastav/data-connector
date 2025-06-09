import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Loader2, Shield, User, CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import ParticleBackground from './ParticleBackground';

export const LoginScreen: React.FC = () => {
  const { login, authHealth } = useAuth();
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = () => {
    setIsLoggingIn(true);
    login();
    // Note: The page will redirect, so we don't need to reset loading state
  };

  const getStatusIcon = () => {
    if (!authHealth) return null;
    
    switch (authHealth.status) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'degraded':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      default:
        return <XCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusColor = () => {
    if (!authHealth) return 'bg-gray-500';
    
    switch (authHealth.status) {
      case 'healthy':
        return 'bg-green-500';
      case 'degraded':
        return 'bg-yellow-500';
      default:
        return 'bg-red-500';
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Particle Background */}
      <div className="fixed inset-0 z-0">
        <ParticleBackground />
      </div>

      {/* Enhanced Background Pattern Overlay */}
      <div className="fixed inset-0 z-10 pointer-events-none">
        {/* Grid and dots pattern with lower opacity to blend with particles */}
        <div className="absolute inset-0 opacity-[0.015]">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid-pattern" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="currentColor" strokeWidth="0.5" />
              </pattern>
              <pattern id="dots-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="10" cy="10" r="0.5" fill="currentColor" opacity="0.8" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid-pattern)" />
            <rect width="100%" height="100%" fill="url(#dots-pattern)" />
          </svg>
        </div>
        
        {/* Subtle gradient overlays for depth */}
        <div className="absolute inset-0 bg-gradient-radial from-purple-500/4 via-transparent to-transparent"></div>
        <div className="absolute inset-0 bg-gradient-to-tr from-purple-600/3 via-transparent to-pink-500/3"></div>
      </div>

      <div className="relative z-20 w-full max-w-md p-6">
        {/* Logo and Brand Section */}
        <div className="text-center mb-12">
          <div className="flex justify-center mb-8">
            <div className="relative">
              {/* Logo container with enhanced styling */}
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-purple-600 to-purple-800 dark:from-purple-500 dark:to-purple-700 flex items-center justify-center shadow-2xl shadow-purple-500/30 p-3">
                <img
                  src="/ceneca-light.png"
                  alt="Ceneca Logo"
                  width={44}
                  height={44}
                  className="object-contain filter brightness-0 invert"
                />
              </div>
              {/* Enhanced glow effect */}
              <div className="absolute inset-0 w-20 h-20 rounded-full bg-gradient-to-br from-purple-600 to-purple-800 dark:from-purple-500 dark:to-purple-700 opacity-30 blur-2xl animate-pulse"></div>
              {/* Additional outer glow */}
              <div className="absolute -inset-2 w-24 h-24 rounded-full bg-gradient-to-br from-purple-400/20 to-pink-400/20 blur-3xl"></div>
            </div>
          </div>
          
          {/* Brand name with enhanced gradient */}
          <h1 className="text-4xl font-bold mb-4 font-serif">
            <span className="bg-gradient-to-r from-purple-600 via-purple-500 to-pink-500 dark:from-purple-400 dark:via-purple-300 dark:to-pink-400 bg-clip-text text-transparent">
              Ceneca
            </span>
          </h1>
          
          <p className="text-lg text-muted-foreground font-serif">
            Sign in to access your workspace
          </p>
        </div>

        {/* Login Card with enhanced glass effect */}
        <div className="bg-card/80 dark:bg-card/60 backdrop-blur-3xl rounded-2xl border border-border/60 shadow-2xl shadow-black/20 dark:shadow-black/30 p-8 ring-1 ring-purple-500/20">
          {/* SSO Status */}
          {authHealth && (
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Shield className="h-5 w-5 text-muted-foreground" />
                  <span className="text-sm font-medium text-foreground font-serif">Single Sign-On</span>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusIcon()}
                  <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
                </div>
              </div>
              
              {authHealth.okta_connected && authHealth.okta_issuer && (
                <div className="text-sm text-muted-foreground ml-8 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
                  <span className="font-serif">Connected to {authHealth.okta_issuer.replace('https://', '')}</span>
                </div>
              )}
            </div>
          )}

          {/* Login Button with landing page styling */}
          <Button
            onClick={handleLogin}
            disabled={isLoggingIn || authHealth?.status === 'unhealthy'}
            className="w-full h-16 text-xl py-8 px-10 transition-all duration-300 bg-zinc-900 text-white hover:bg-[#7b35b8] dark:bg-zinc-800 dark:hover:bg-[#7b35b8] font-serif rounded-xl shadow-lg shadow-zinc-900/25 dark:shadow-zinc-800/25 hover:shadow-xl hover:shadow-[#7b35b8]/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none transform hover:scale-[1.02] disabled:hover:scale-100"
          >
            {isLoggingIn ? (
              <div className="flex items-center gap-3">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span>Redirecting...</span>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <User className="h-6 w-6" />
                <span>Continue with SSO</span>
              </div>
            )}
          </Button>

          {/* Status Message */}
          {authHealth?.message && (
            <div className={`mt-6 p-4 rounded-xl text-sm border backdrop-blur-sm ${
              authHealth.status === 'healthy'
                ? 'bg-green-50/80 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-200/60 dark:border-green-800/60'
                : authHealth.status === 'degraded'
                ? 'bg-yellow-50/80 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 border-yellow-200/60 dark:border-yellow-800/60'
                : 'bg-red-50/80 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200/60 dark:border-red-800/60'
            }`}>
              <div className="flex items-start gap-3">
                {getStatusIcon()}
                <span className="flex-1 leading-relaxed font-serif">{authHealth.message}</span>
              </div>
            </div>
          )}

          {/* Role Info */}
          {authHealth?.configured_roles && Object.keys(authHealth.configured_roles).length > 0 && (
            <div className="mt-6 pt-6 border-t border-border/30">
              <div className="text-sm font-medium text-foreground mb-4 font-serif">Available roles:</div>
              <div className="flex flex-wrap gap-2">
                {Object.keys(authHealth.configured_roles).map((role) => (
                  <span
                    key={role}
                    className="px-3 py-2 bg-muted/60 text-muted-foreground rounded-lg text-sm font-medium border border-border/40 backdrop-blur-sm font-serif"
                  >
                    {role}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}; 