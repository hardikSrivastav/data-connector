import { useState, useEffect } from 'react';
import { Loader2, X, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StreamingEvent {
  type: 'status' | 'progress' | 'error' | 'complete' | 'partial_sql' | 'analysis_chunk';
  message: string;
  timestamp: string;
  metadata?: any;
}

interface StreamingStatusBlockProps {
  status: string;
  progress: number;
  query: string;
  onCancel?: () => void;
  // New props for transparent streaming
  streamingHistory?: StreamingEvent[];
  showHistory?: boolean;
}

export const StreamingStatusBlock = ({ 
  status, 
  progress, 
  query, 
  onCancel,
  streamingHistory = [],
  showHistory = true
}: StreamingStatusBlockProps) => {
  const [dots, setDots] = useState('');

  // Animate dots for thinking effect
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => {
        if (prev.length >= 3) return '';
        return prev + '.';
      });
    }, 500);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 mb-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-gray-400 dark:text-gray-500 animate-spin" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
            AI Processing
            <span className="text-gray-400 dark:text-gray-500 ml-1 w-4 inline-block">{dots}</span>
          </span>
        </div>
        {onCancel && (
          <button
            onClick={onCancel}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors p-1"
            title="Cancel"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Query */}
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-3">
        "{query}"
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-3">
        <div 
          className="bg-blue-500 h-1.5 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>

      {/* Live Status Feed - Show exactly what backend sends */}
      <div className="space-y-2">
        {/* Current Status - Direct from backend */}
        {status && (
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse mt-1.5 flex-shrink-0" />
            <div className="flex-1">
              <div className="text-sm text-blue-600 dark:text-blue-400 font-medium">
                {status}
              </div>
              <div className="text-xs text-gray-400 dark:text-gray-500">
                {new Date().toLocaleTimeString()}
              </div>
            </div>
          </div>
        )}
        
        {/* Show streaming history if available and enabled */}
        {showHistory && streamingHistory && streamingHistory.length > 0 && (
          <div className="mt-3 pt-2 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-2">
              <Clock className="h-3 w-3" />
              <span>Recent Updates</span>
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {streamingHistory.slice(-4).map((event, index) => (
                <div key={index} className="flex items-start gap-2 text-xs opacity-75">
                  <div className={cn(
                    "w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0",
                    event.type === 'error' ? 'bg-red-400' :
                    event.type === 'complete' ? 'bg-green-400' :
                    event.type === 'progress' ? 'bg-yellow-400' :
                    'bg-gray-400 dark:bg-gray-500'
                  )} />
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-600 dark:text-gray-300 truncate">
                      {event.message}
                    </div>
                    <div className="text-gray-400 dark:text-gray-500 text-xs">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Fallback: If no history, show current status prominently */}
        {(!showHistory || !streamingHistory || streamingHistory.length === 0) && status && (
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mt-2">
            <div className="text-sm text-blue-800 dark:text-blue-200 font-medium">
              {status}
            </div>
            {progress > 0 && (
              <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                {Math.round(progress * 100)}% complete
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}; 