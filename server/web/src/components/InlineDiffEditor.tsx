import React, { useState, useEffect, useRef } from 'react';
import { computeTextDiff, DiffChange } from '@/lib/diff/textDiff';
import { DiffRenderer } from './DiffRenderer';
import { cn } from '@/lib/utils';

interface InlineDiffEditorProps {
  originalText: string;
  onAccept: (newText: string) => void;
  onCancel: () => void;
  onReject?: () => void;
  onTryAgain?: () => void;
  onInsertBelow?: (newText: string) => void;
  className?: string;
}

export const InlineDiffEditor: React.FC<InlineDiffEditorProps> = ({
  originalText,
  onAccept,
  onCancel,
  onReject,
  onTryAgain,
  onInsertBelow,
  className
}) => {
  const [inputText, setInputText] = useState('');
  const [showDiff, setShowDiff] = useState(false);
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Focus the textarea when component mounts
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onCancel]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputText.trim()) {
        // Show diff immediately
        const changes = computeTextDiff(originalText, inputText.trim());
        setDiffChanges(changes);
        setShowDiff(true);
      }
    }
  };

  const handleAccept = () => {
    onAccept(inputText.trim());
  };

  const handleReject = () => {
    if (onReject) {
      onReject();
    } else {
      onCancel();
    }
  };

  const handleTryAgain = () => {
    if (onTryAgain) {
      onTryAgain();
    } else {
      // Reset to input mode
      setShowDiff(false);
      setInputText('');
    }
  };

  const handleInsertBelow = () => {
    if (onInsertBelow) {
      onInsertBelow(inputText.trim());
    }
  };

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [inputText]);

  if (showDiff) {
    return (
      <div className={cn("space-y-2", className)}>
        <DiffRenderer 
          changes={diffChanges}
          className="text-sm leading-relaxed"
        />
        
        {/* Control buttons matching Notion's design */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={handleAccept}
            className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            Accept
          </button>
          <button
            onClick={handleReject}
            className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
          >
            Discard
          </button>
          {onInsertBelow && (
            <button
              onClick={handleInsertBelow}
              className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            >
              Insert below
            </button>
          )}
          <button
            onClick={handleTryAgain}
            className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative", className)}>
      <textarea
        ref={textareaRef}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={adjustTextareaHeight}
        placeholder="Type your replacement text here... (Enter to preview, Escape to cancel)"
        className="w-full p-3 border border-blue-300 rounded resize-none outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition-colors text-sm leading-relaxed bg-blue-50/30"
        rows={1}
        style={{ minHeight: '48px' }}
      />
      <div className="text-xs text-gray-500 mt-1">
        Press Enter to preview changes, Escape to cancel
      </div>
    </div>
  );
}; 