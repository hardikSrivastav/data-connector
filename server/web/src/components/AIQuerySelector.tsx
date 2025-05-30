import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, Sparkles, Send, X } from 'lucide-react';
import styles from './BlockEditor.module.css';

interface AIQuerySelectorProps {
  query: string;
  onQuerySubmit: (query: string) => void;
  onClose: () => void;
  isLoading?: boolean;
}

export const AIQuerySelector = ({ query, onQuerySubmit, onClose, isLoading = false }: AIQuerySelectorProps) => {
  const [inputValue, setInputValue] = useState(query);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      // Position cursor at the end
      inputRef.current.setSelectionRange(inputValue.length, inputValue.length);
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [inputValue]);

  const handleSubmit = () => {
    if (inputValue.trim() && !isLoading) {
      onQuerySubmit(inputValue.trim());
    }
  };

  return (
    <div className={`inline-block relative w-full ${styles.aiQueryInline}`}>
      {/* Inline AI Input */}
      <div className="inline-flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 w-full max-w-lg font-baskerville">
        <Sparkles className="h-5 w-5 text-blue-500 flex-shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ask AI anything..."
          className="flex-1 bg-transparent border-none outline-none text-base text-gray-700 placeholder-gray-500 min-w-0 font-baskerville py-1"
          disabled={isLoading}
        />
        <div className="flex items-center gap-1">
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
          ) : (
            <>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleSubmit}
                disabled={!inputValue.trim()}
                className="h-7 w-7 p-0 hover:bg-blue-100"
              >
                <Send className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={onClose}
                className="h-7 w-7 p-0 hover:bg-blue-100"
              >
                <X className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Loading State Overlay */}
      {isLoading && (
        <div className="absolute top-full left-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg z-50 w-full max-w-lg">
          <div className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>AI is thinking...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 