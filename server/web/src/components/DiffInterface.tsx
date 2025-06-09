import React, { useState, useEffect, useRef } from 'react';
import { computeTextDiff, DiffChange, applyDiffChanges } from '@/lib/diff/textDiff';
import { DiffRenderer, DiffControls } from './DiffRenderer';
import { cn } from '@/lib/utils';

interface DiffInterfaceProps {
  originalText: string;
  onAccept: (newText: string) => void;
  onDiscard: () => void;
  onInsertBelow: (newText: string) => void;
  onTryAgain: () => void;
  className?: string;
}

export const DiffInterface: React.FC<DiffInterfaceProps> = ({
  originalText,
  onAccept,
  onDiscard,
  onInsertBelow,
  onTryAgain,
  className
}) => {
  const [newText, setNewText] = useState(originalText);
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([]);
  const [showControls, setShowControls] = useState(false);
  const [controlsPosition, setControlsPosition] = useState({ x: 0, y: 0 });
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Compute diff whenever text changes
    if (newText !== originalText) {
      const changes = computeTextDiff(originalText, newText);
      setDiffChanges(changes);
      setShowControls(true);
    } else {
      setDiffChanges([]);
      setShowControls(false);
    }
  }, [originalText, newText]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleDiscard();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const updateControlsPosition = () => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setControlsPosition({
        x: rect.left,
        y: rect.bottom + 8
      });
    }
  };

  useEffect(() => {
    if (showControls) {
      updateControlsPosition();
      window.addEventListener('scroll', updateControlsPosition);
      window.addEventListener('resize', updateControlsPosition);
      
      return () => {
        window.removeEventListener('scroll', updateControlsPosition);
        window.removeEventListener('resize', updateControlsPosition);
      };
    }
  }, [showControls]);

  const handleAccept = () => {
    const finalText = applyDiffChanges(diffChanges);
    onAccept(finalText);
    setShowControls(false);
  };

  const handleDiscard = () => {
    setNewText(originalText);
    setDiffChanges([]);
    setShowControls(false);
    onDiscard();
  };

  const handleInsertBelow = () => {
    const finalText = applyDiffChanges(diffChanges);
    onInsertBelow(finalText);
    setShowControls(false);
  };

  const handleTryAgain = () => {
    setNewText(originalText);
    setDiffChanges([]);
    setShowControls(false);
    onTryAgain();
  };

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [newText]);

  return (
    <>
      <div ref={containerRef} className={cn("relative", className)}>
        {diffChanges.length > 0 ? (
          // Show diff preview
          <div className="p-3 bg-gray-50 rounded border border-gray-200 min-h-24 cursor-pointer"
               onClick={() => textareaRef.current?.focus()}>
            <DiffRenderer 
              changes={diffChanges}
              className="text-sm leading-relaxed"
            />
          </div>
        ) : (
          // Show editable textarea
          <textarea
            ref={textareaRef}
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            onInput={adjustTextareaHeight}
            placeholder="Type your replacement text here..."
            className="w-full p-3 border border-gray-200 rounded resize-none outline-none focus:border-blue-300 focus:ring-1 focus:ring-blue-300 transition-colors text-sm leading-relaxed"
            rows={1}
            style={{ minHeight: '48px' }}
          />
        )}
      </div>

      {/* Floating Controls */}
      {showControls && (
        <div 
          className="fixed z-50"
          style={{
            left: controlsPosition.x,
            top: controlsPosition.y
          }}
        >
          <DiffControls
            onAccept={handleAccept}
            onDiscard={handleDiscard}
            onInsertBelow={handleInsertBelow}
            onTryAgain={handleTryAgain}
            onClose={handleDiscard}
          />
        </div>
      )}
    </>
  );
}; 