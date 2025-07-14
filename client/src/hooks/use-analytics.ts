import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

declare global {
  interface Window {
    gtag: (
      command: string,
      eventName: string,
      eventParams?: Record<string, any>
    ) => void;
  }
}

export const GA_MEASUREMENT_ID = 'G-0KY7J773R1';

export function useAnalytics() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname && typeof window !== 'undefined' && window.gtag) {
      // Track page views - use window.location.search for search params to avoid SSR issues
      const searchParams = typeof window !== 'undefined' ? window.location.search : '';
      const url = pathname + searchParams;
      
      window.gtag('config', GA_MEASUREMENT_ID, {
        page_path: url,
      });
    }
  }, [pathname]);

  // Function to track custom events
  const trackEvent = (action: string, category: string, label: string, value?: number) => {
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', action, {
        event_category: category,
        event_label: label,
        value: value,
      });
    }
  };

  return { trackEvent };
} 