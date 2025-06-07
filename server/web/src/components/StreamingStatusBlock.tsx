import { useState, useEffect } from 'react';
import { Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StreamingStatusBlockProps {
  status: string;
  progress: number;
  query: string;
  onCancel?: () => void;
}

export const StreamingStatusBlock = ({ 
  status, 
  progress, 
  query, 
  onCancel 
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
    <div className="relative p-4 bg-gray-50 rounded-lg border border-gray-200 mb-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
          <span className="text-sm font-medium text-gray-700">
            AI is thinking
            <span className="text-gray-400 ml-1 w-4 inline-block">{dots}</span>
          </span>
        </div>
        {onCancel && (
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1"
            title="Cancel"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Query */}
      <div className="text-xs text-gray-500 mb-3">
        "{query}"
      </div>

      {/* Current status */}
      <div className="text-xs text-gray-600 mb-2">
        {status}
      </div>

      {/* Simple progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-1">
        <div 
          className="bg-gray-400 h-1 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
    </div>
  );
}; 