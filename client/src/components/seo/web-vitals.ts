import { NextWebVitalsMetric } from 'next/app';

// Add gtag to window object type
declare global {
  interface Window {
    gtag: (
      command: string,
      eventName: string,
      eventParams?: Record<string, any>
    ) => void;
  }
}

export function reportWebVitals(metric: NextWebVitalsMetric) {
  // Log metrics to console in development
  if (process.env.NODE_ENV === 'development') {
    console.log(metric);
  }
  
  const body = JSON.stringify({
    name: metric.name,
    id: metric.id,
    startTime: metric.startTime,
    value: metric.value,
    label: metric.label,
  });
  
  // Send to Google Analytics 4
  if (typeof window !== 'undefined' && window.gtag) {
    window.gtag('event', 'web_vitals', {
      event_category: 'Web Vitals',
      event_label: metric.id,
      value: Math.round(metric.name === 'CLS' ? metric.value * 1000 : metric.value),
      metric_id: metric.id,
      metric_name: metric.name,
      metric_value: metric.value,
      non_interaction: true, // Don't count against bounce rate
    });
  }
  
  // Using Beacon API as a fallback
  const url = '/api/vitals';
  // Use `navigator.sendBeacon()` if available
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url, body);
  } else {
    // Fallback to fetch for older browsers
    fetch(url, {
      body,
      method: 'POST',
      keepalive: true,
    });
  }
} 