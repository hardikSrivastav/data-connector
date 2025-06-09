import React from 'react';
import { DiffChange } from '@/lib/diff/textDiff';
import { cn } from '@/lib/utils';

interface DiffRendererProps {
  changes: DiffChange[];
  className?: string;
  animationSpeed?: number;
  isStreaming?: boolean;
}

export const DiffRenderer: React.FC<DiffRendererProps> = ({ 
  changes, 
  className,
  animationSpeed = 200,
  isStreaming = false
}) => {
  return (
    <div className={cn("diff-container", className, {
      "opacity-75": isStreaming
    })}>
      {changes.map((change, index) => (
        <DiffSpan 
          key={index}
          change={change}
          animationSpeed={animationSpeed}
          isStreaming={isStreaming}
        />
      ))}
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1"></span>
      )}
    </div>
  );
};

interface DiffSpanProps {
  change: DiffChange;
  animationSpeed: number;
  isStreaming?: boolean;
}

const DiffSpan: React.FC<DiffSpanProps> = ({ change, animationSpeed, isStreaming = false }) => {
  const getClassName = () => {
    switch (change.type) {
      case 'added':
        return 'bg-blue-100 text-blue-800 rounded-sm px-0.5 transition-all duration-200 ease-in-out';
      case 'removed':
        return 'text-gray-400 line-through transition-all duration-200 ease-in-out';
      case 'unchanged':
      default:
        return 'transition-all duration-200 ease-in-out';
    }
  };

  return (
    <span 
      className={getClassName()}
      style={{
        transitionDuration: `${animationSpeed}ms`
      }}
    >
      {change.value}
    </span>
  );
};

interface DiffControlsProps {
  onAccept: () => void;
  onDiscard: () => void;
  onInsertBelow: () => void;
  onTryAgain: () => void;
  onClose: () => void;
}

export const DiffControls: React.FC<DiffControlsProps> = ({
  onAccept,
  onDiscard,
  onInsertBelow,
  onTryAgain,
  onClose
}) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-64">
      <div className="space-y-1">
        <button
          onClick={onAccept}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors text-left"
        >
          <span className="text-green-600">✓</span>
          <span>Accept</span>
        </button>
        
        <button
          onClick={onDiscard}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors text-left"
        >
          <span className="text-red-600">✕</span>
          <span>Discard</span>
          <span className="ml-auto text-xs text-gray-400">Escape</span>
        </button>
        
        <button
          onClick={onInsertBelow}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors text-left"
        >
          <span className="text-gray-600">≡</span>
          <span>Insert below</span>
        </button>
        
        <button
          onClick={onTryAgain}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors text-left"
        >
          <span className="text-gray-600">↺</span>
          <span>Try again</span>
        </button>
      </div>
    </div>
  );
}; 