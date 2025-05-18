'use client';

import { ReactNode } from 'react';
import { useAnalytics } from '@/hooks/use-analytics';

interface AnalyticsProviderProps {
  children: ReactNode;
}

export default function AnalyticsProvider({ children }: AnalyticsProviderProps) {
  // This hook will track page views
  useAnalytics();
  
  return <>{children}</>;
} 