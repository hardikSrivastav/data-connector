import React, { useState, useEffect, useRef } from 'react';
import { computeTextDiff, DiffChange } from '@/lib/diff/textDiff';
import { DiffRenderer } from './DiffRenderer';
import { agentClient } from '@/lib/agent-client';
import { TrivialQueryRequest } from '@/lib/AgentClient';
import { cn } from '@/lib/utils';

interface TrivialLLMEditorProps {
  originalText: string;
  onAccept: (newText: string) => void;
  onCancel: () => void;
  onReject?: () => void;
  onTryAgain?: () => void;
  onInsertBelow?: (newText: string) => void;
  className?: string;
  blockType?: string;
}

interface StreamingState {
  isStreaming: boolean;
  operation: string;
  provider: string;
  model: string;
  partialResult: string;
  finalResult: string;
  duration: number;
  cached: boolean;
}

const QUICK_OPERATIONS = [
  { id: 'fix_grammar', label: '✓ Fix grammar', shortcut: 'g' },
  { id: 'make_concise', label: '↗ Make concise', shortcut: 'c' },
  { id: 'improve_clarity', label: '💡 Improve clarity', shortcut: 'i' },
  { id: 'improve_tone', label: '🎯 Professional tone', shortcut: 't' },
  { id: 'expand_text', label: '📝 Expand', shortcut: 'e' },
  { id: 'simplify_language', label: '🔍 Simplify', shortcut: 's' },
];

export const TrivialLLMEditor: React.FC<TrivialLLMEditorProps> = ({
  originalText,
  onAccept,
  onCancel,
  onReject,
  onTryAgain,
  onInsertBelow,
  className,
  blockType = 'text'
}) => {
  const [inputText, setInputText] = useState('');
  const [showDiff, setShowDiff] = useState(false);
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([]);
  const [streamingState, setStreamingState] = useState<StreamingState>({
    isStreaming: false,
    operation: '',
    provider: '',
    model: '',
    partialResult: '',
    finalResult: '',
    duration: 0,
    cached: false
  });
  const [supportedOperations, setSupportedOperations] = useState<string[]>([]);
  const [isLLMEnabled, setIsLLMEnabled] = useState(false);
  const [showOperations, setShowOperations] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Check if AI operations are available
    const checkAI = async () => {
      try {
        const health = await agentClient.checkTrivialHealth();
        setIsLLMEnabled(health.status === 'healthy');
        setSupportedOperations(health.supported_operations || []);
      } catch (error) {
        console.warn('AI operations not available:', error);
        setIsLLMEnabled(false);
      }
    };

    checkAI();
  }, []);

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
      
      // Quick operation shortcuts
      if (isLLMEnabled && e.ctrlKey || e.metaKey) {
        const operation = QUICK_OPERATIONS.find(op => op.shortcut === e.key);
        if (operation && supportedOperations.includes(operation.id)) {
          e.preventDefault();
          handleLLMOperation(operation.id);
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onCancel, isLLMEnabled, supportedOperations]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputText.trim()) {
        // Show manual diff
        const changes = computeTextDiff(originalText, inputText.trim());
        setDiffChanges(changes);
        setStreamingState(prev => ({ 
          ...prev, 
          finalResult: inputText.trim(),
          operation: 'manual_edit',
          isStreaming: false
        }));
        setShowDiff(true);
      }
    }
  };

  const handleLLMOperation = async (operation: string) => {
    if (!isLLMEnabled || streamingState.isStreaming) return;

    setStreamingState({
      isStreaming: true,
      operation,
      provider: '',
      model: '',
      partialResult: '',
      finalResult: '',
      duration: 0,
      cached: false
    });
    setShowDiff(true);
    setShowOperations(false);

    const request: TrivialQueryRequest = {
      operation,
      text: originalText,
      context: {
        block_type: blockType
      }
    };

    try {
      await agentClient.streamTrivialOperation(
        request,
        (chunk) => {
          if (chunk.type === 'start') {
            setStreamingState(prev => ({
              ...prev,
              provider: chunk.provider || '',
              model: chunk.model || ''
            }));
          } else if (chunk.type === 'chunk') {
            const partialResult = chunk.partial_result || chunk.content || '';
            setStreamingState(prev => ({
              ...prev,
              partialResult
            }));
            
            // Update diff in real-time
            if (partialResult) {
              const changes = computeTextDiff(originalText, partialResult);
              setDiffChanges(changes);
            }
          } else if (chunk.type === 'complete') {
            const finalResult = chunk.result || '';
            setStreamingState(prev => ({
              ...prev,
              isStreaming: false,
              finalResult,
              duration: chunk.duration || 0,
              cached: chunk.cached || false
            }));
            
            // Final diff
            if (finalResult) {
              const changes = computeTextDiff(originalText, finalResult);
              setDiffChanges(changes);
            }
          }
        },
        (error) => {
          console.error('AI operation stream error:', error);
          setStreamingState(prev => ({
            ...prev,
            isStreaming: false
          }));
        }
      );
    } catch (error) {
      console.error('Failed to start AI operation:', error);
      setStreamingState(prev => ({
        ...prev,
        isStreaming: false
      }));
    }
  };

  const handleAccept = () => {
    const result = streamingState.finalResult || inputText.trim();
    onAccept(result);
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
      setStreamingState(prev => ({
        ...prev,
        isStreaming: false,
        finalResult: '',
        partialResult: ''
      }));
    }
  };

  const handleInsertBelow = () => {
    if (onInsertBelow) {
      const result = streamingState.finalResult || inputText.trim();
      onInsertBelow(result);
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
    const isStreaming = streamingState.isStreaming;
    const hasResult = streamingState.finalResult || inputText.trim();

    return (
      <div className={cn("space-y-3", className)}>
        {/* Streaming status */}
        {isStreaming && (
          <div className="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded">
            <div className="animate-spin w-3 h-3 border border-blue-300 border-t-blue-600 rounded-full"></div>
            <span>Generating...</span>
          </div>
        )}

        {/* Operation info */}
        {streamingState.operation && !isStreaming && (
          <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
            <span className="font-medium">
              {QUICK_OPERATIONS.find(op => op.id === streamingState.operation)?.label || streamingState.operation}
            </span>
            {streamingState.duration > 0 && (
              <span className="text-gray-400 dark:text-gray-500">
                • {streamingState.duration.toFixed(2)}s
                {streamingState.cached && ' (cached)'}
              </span>
            )}
          </div>
        )}
        
        {/* Diff display */}
        <DiffRenderer 
          changes={diffChanges}
          className="text-sm leading-relaxed"
          isStreaming={isStreaming}
        />
        
        {/* Control buttons */}
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={handleAccept}
            disabled={isStreaming || !hasResult}
            className="px-3 py-1 bg-blue-600 dark:bg-blue-500 text-white rounded hover:bg-blue-700 dark:hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Accept
          </button>
          <button
            onClick={handleReject}
            disabled={isStreaming}
            className="px-3 py-1 border border-input rounded hover:bg-accent text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Discard
          </button>
          {onInsertBelow && (
            <button
              onClick={handleInsertBelow}
              disabled={isStreaming || !hasResult}
              className="px-3 py-1 border border-input rounded hover:bg-accent text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Insert below
            </button>
          )}
          <button
            onClick={handleTryAgain}
            disabled={isStreaming}
            className="px-3 py-1 border border-input rounded hover:bg-accent text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative space-y-2", className)}>
      {/* AI operations panel */}
      {isLLMEnabled && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowOperations(!showOperations)}
              className="text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 rounded hover:bg-purple-200 dark:hover:bg-purple-900/30 transition-colors"
            >
              ✨ AI Operations {showOperations ? '▼' : '▶'}
            </button>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              or type manually below
            </span>
          </div>
          
          {showOperations && (
            <div className="grid grid-cols-2 gap-1 p-2 bg-muted rounded border border-border">
              {QUICK_OPERATIONS
                .filter(op => supportedOperations.includes(op.id))
                .map(operation => (
                <button
                  key={operation.id}
                  onClick={() => handleLLMOperation(operation.id)}
                  className="text-left text-xs px-2 py-1 hover:bg-card hover:shadow-sm rounded transition-all text-foreground"
                  title={`Ctrl/Cmd + ${operation.shortcut}`}
                >
                  {operation.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Manual input */}
      <textarea
        ref={textareaRef}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={adjustTextareaHeight}
        placeholder={
          isLLMEnabled 
            ? "Type replacement text or use AI operations above... (Enter to preview, Escape to cancel)"
            : "Type your replacement text here... (Enter to preview, Escape to cancel)"
        }
        className="w-full p-3 border border-blue-300 dark:border-blue-600 rounded resize-none outline-none focus:border-blue-400 dark:focus:border-blue-500 focus:ring-1 focus:ring-blue-400 dark:focus:ring-blue-500 transition-colors text-sm leading-relaxed bg-blue-50/30 dark:bg-blue-900/20 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
        rows={1}
        style={{ minHeight: '48px' }}
      />
      
      <div className="text-xs text-gray-500 dark:text-gray-400">
        Press Enter to preview changes, Escape to cancel
        {isLLMEnabled && (
          <span className="ml-2 text-purple-600 dark:text-purple-400">
            • Use Ctrl/Cmd + shortcuts for AI operations
          </span>
        )}
      </div>
    </div>
  );
}; 