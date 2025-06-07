import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, Sparkles, Send, X, FileText, CheckSquare, Edit3, Lightbulb, Code, Search } from 'lucide-react';
import styles from './BlockEditor.module.css';

interface AIQuerySelectorProps {
  query: string;
  onQuerySubmit: (query: string) => void;
  onClose: () => void;
  isLoading?: boolean;
  streamingStatus?: string;
  streamingProgress?: number;
}

const AI_OPTIONS = [
  {
    section: 'Write',
    items: [
      { icon: '📊', text: 'Add a summary', query: 'Add a summary' },
      { icon: '📝', text: 'Add action items', query: 'Add action items' },
      { icon: '✏️', text: 'Write anything...', query: 'Write anything...' },
    ]
  },
  {
    section: 'Think, ask, chat',
    items: [
      { icon: '💡', text: 'Brainstorm ideas...', query: 'Brainstorm ideas...' },
      { icon: '</>', text: 'Get help with code...', query: 'Get help with code...' },
    ]
  },
  {
    section: 'Find, search',
    items: [
      { icon: '🔍', text: 'Ask a question...', query: 'Ask a question...' },
    ]
  }
];

export const AIQuerySelector = ({ 
  query, 
  onQuerySubmit, 
  onClose, 
  isLoading = false, 
  streamingStatus,
  streamingProgress 
}: AIQuerySelectorProps) => {
  const [inputValue, setInputValue] = useState(query);
  const [showDropdown, setShowDropdown] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (inputRef.current && !isLoading) {
      inputRef.current.focus();
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

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [inputValue]);

  const handleSubmit = () => {
    if (inputValue.trim() && !isLoading) {
      onQuerySubmit(inputValue.trim());
      setShowDropdown(false);
    }
  };

  const handleOptionClick = (optionQuery: string) => {
    setInputValue(optionQuery);
    onQuerySubmit(optionQuery);
    setShowDropdown(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    setShowDropdown(e.target.value.length === 0);
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-none">
      {/* Search Input */}
      <div className="relative">
        <div className="flex items-center bg-white border border-gray-200 rounded-lg shadow-lg hover:shadow-xl transition-shadow w-full">
          <div className="flex items-center pl-3">
            <Sparkles className="h-4 w-4 text-gray-400" />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            placeholder="Ask AI anything..."
            className="flex-1 px-3 py-2.5 bg-transparent border-none outline-none text-sm text-gray-900 placeholder-gray-400"
            disabled={isLoading}
          />
          {inputValue && (
            <button
              onClick={() => {
                setInputValue('');
                setShowDropdown(true);
                inputRef.current?.focus();
              }}
              className="p-1 mr-2 text-gray-400 hover:text-gray-600 rounded"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Dropdown Menu */}
      {showDropdown && !isLoading && (
        <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-2 w-full">
          {AI_OPTIONS.map((section, sectionIndex) => (
            <div key={sectionIndex}>
              {/* Section Header */}
              <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                {section.section}
              </div>
              
              {/* Section Items */}
              <div className="mb-2">
                {section.items.map((item, itemIndex) => (
                  <button
                    key={itemIndex}
                    onClick={() => handleOptionClick(item.query)}
                    className="w-full flex items-center px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors text-left"
                  >
                    <span className="mr-3 text-base">{item.icon}</span>
                    <span>{item.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Streaming Progress State */}
      {isLoading && (
        <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-4 w-full">
          <div className="px-4">
            <div className="flex items-center justify-center gap-3 text-sm text-gray-600 mb-3">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span className="font-medium">AI is working...</span>
            </div>
            
            {/* Streaming Status */}
            {streamingStatus && (
              <div className="text-center mb-3">
                <div className="text-xs text-gray-500 mb-1">Current step:</div>
                <div className="text-sm text-gray-700 font-medium">{streamingStatus}</div>
              </div>
            )}
            
            {/* Progress Bar */}
            {streamingProgress !== undefined && (
              <div className="mb-3">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Progress</span>
                  <span>{Math.round(streamingProgress * 100)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div 
                    className="bg-blue-500 h-1.5 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${Math.round(streamingProgress * 100)}%` }}
                  />
                </div>
              </div>
            )}
            
            {/* Streaming Steps Indicator */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('classif') ? 'bg-blue-500' : 
                  streamingStatus?.includes('databas') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('classif') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Analyzing query
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('schema') || streamingStatus?.includes('loading') ? 'bg-blue-500' : 
                  streamingStatus?.includes('generat') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('schema') || streamingStatus?.includes('loading') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Loading schemas
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('generat') ? 'bg-blue-500' : 
                  streamingStatus?.includes('execut') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('generat') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Generating query
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('execut') ? 'bg-blue-500' : 
                  streamingStatus?.includes('analyz') || streamingStatus?.includes('insight') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('execut') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Executing query
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('analyz') || streamingStatus?.includes('insight') ? 'bg-blue-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('analyz') || streamingStatus?.includes('insight') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Generating insights
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 