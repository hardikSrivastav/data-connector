import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Block } from '@/types';
import { BlockTypeSelector } from './BlockTypeSelector';
import { cn } from '@/lib/utils';
import { GripVertical, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import styles from './BlockEditor.module.css';

interface BlockEditorProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  onAddBlock: () => void;
  onDeleteBlock: () => void;
  onFocus: () => void;
  isFocused: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  // Selection props
  isSelected?: boolean;
  onSelect?: (e?: React.MouseEvent) => void;
  onDragStart?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
  // Drag selection props
  onMouseDown?: (e: React.MouseEvent) => void;
  onMouseEnter?: (e: React.MouseEvent) => void;
  onMouseUp?: (e: React.MouseEvent) => void;
  isFirstSelected?: boolean;
  isLastSelected?: boolean;
  isInSelection?: boolean;
}

export const BlockEditor = ({
  block,
  onUpdate,
  onAddBlock,
  onDeleteBlock,
  onFocus,
  isFocused,
  onMoveUp,
  onMoveDown,
  isSelected = false,
  onSelect,
  onDragStart,
  onDragOver,
  onDrop,
  onMouseDown,
  onMouseEnter,
  onMouseUp,
  isFirstSelected = false,
  isLastSelected = false,
  isInSelection = false
}: BlockEditorProps) => {
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [typeSelectorQuery, setTypeSelectorQuery] = useState('');
  const [showAddButton, setShowAddButton] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const blockRef = useRef<HTMLDivElement>(null);

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  };

  useEffect(() => {
    if (isFocused && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isFocused]);

  useEffect(() => {
    adjustTextareaHeight();
  }, [block.content, block.type]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onAddBlock();
    } else if (e.key === 'Backspace' && block.content === '') {
      e.preventDefault();
      onDeleteBlock();
    } else if (e.key === 'ArrowUp' && e.metaKey) {
      e.preventDefault();
      onMoveUp();
    } else if (e.key === 'ArrowDown' && e.metaKey) {
      e.preventDefault();
      onMoveDown();
    }
  };

  const handleContentChange = (content: string) => {
    if (content.startsWith('/')) {
      const query = content.slice(1);
      setTypeSelectorQuery(query);
      setShowTypeSelector(true);
    } else {
      setShowTypeSelector(false);
      setTypeSelectorQuery('');
    }
    
    onUpdate({ content });
  };

  const handleTypeSelect = (type: Block['type']) => {
    onUpdate({ type, content: '' });
    setShowTypeSelector(false);
    setTypeSelectorQuery('');
  };

  const getPlaceholder = () => {
    switch (block.type) {
      case 'heading1': return "Heading 1";
      case 'heading2': return "Heading 2";
      case 'heading3': return "Heading 3";
      case 'bullet': return "• List item";
      case 'numbered': return "1. List item";
      case 'quote': return "Quote";
      case 'code': return "Code";
      case 'divider': return "---";
      default: return "Type '/' for commands";
    }
  };

  const getClassName = () => {
    const baseClasses = "w-full resize-none border-none outline-none bg-transparent font-baskerville overflow-hidden";
    
    switch (block.type) {
      case 'heading1':
        return `${baseClasses} text-3xl font-bold py-2`;
      case 'heading2':
        return `${baseClasses} text-2xl font-bold py-2`;
      case 'heading3':
        return `${baseClasses} text-xl font-bold py-1`;
      case 'bullet':
        return `${baseClasses} pl-6 relative`;
      case 'numbered':
        return `${baseClasses} pl-6 relative`;
      case 'quote':
        return `${baseClasses} pl-4 border-l-4 border-gray-300 italic text-gray-600`;
      case 'code':
        return `${baseClasses} font-mono text-sm bg-gray-100 p-3 rounded`;
      case 'divider':
        return `${baseClasses} text-center text-gray-400`;
      default:
        return `${baseClasses} py-1`;
    }
  };

  const getMinHeight = () => {
    switch (block.type) {
      case 'heading1':
      case 'heading2':
      case 'heading3':
        return '48px';
      case 'code':
        return '80px';
      default:
        return '24px';
    }
  };

  // Get selection styling classes
  const getSelectionClasses = () => {
    if (!isSelected && !isInSelection) return "";
    
    let classes = styles.selectedBlock + " ";
    
    if (isFirstSelected && isLastSelected) {
      // Single block selected
      classes += styles.singleSelected;
    } else if (isFirstSelected) {
      // First block in selection
      classes += styles.firstSelected;
    } else if (isLastSelected) {
      // Last block in selection
      classes += styles.lastSelected;
    } else if (isInSelection) {
      // Middle block in selection
      classes += styles.middleSelected;
    }
    
    return classes;
  };

  if (block.type === 'divider') {
    return (
      <div
        ref={blockRef}
        className={cn(
          "group relative py-2 cursor-pointer transition-colors -my-1",
          getSelectionClasses()
        )}
        onMouseEnter={(e) => {
          setShowAddButton(true);
          onMouseEnter?.(e);
        }}
        onMouseLeave={() => setShowAddButton(false)}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onClick={(e) => onSelect?.(e)}
        draggable
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 w-20">
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "h-6 w-6 p-0 transition-opacity cursor-grab",
                showAddButton ? "opacity-100" : "opacity-0"
              )}
              draggable
              onDragStart={onDragStart}
            >
              <GripVertical className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onAddBlock();
              }}
              className={cn(
                "h-6 w-6 p-0 transition-opacity",
                showAddButton ? "opacity-100" : "opacity-0"
              )}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <hr className="flex-1 border-gray-300" />
        </div>
      </div>
    );
  }

  return (
    <div
      ref={blockRef}
      className={cn(
        "group relative cursor-pointer transition-colors -my-1",
        getSelectionClasses()
      )}
      onMouseEnter={(e) => {
        setShowAddButton(true);
        onMouseEnter?.(e);
      }}
      onMouseLeave={() => setShowAddButton(false)}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      onClick={(e) => onSelect?.(e)}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="flex items-start gap-2">
        <div className="flex items-center gap-1 w-20 pt-1">
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-6 w-6 p-0 transition-opacity cursor-grab",
              showAddButton ? "opacity-100" : "opacity-0"
            )}
            draggable
            onDragStart={onDragStart}
          >
            <GripVertical className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onAddBlock();
            }}
            className={cn(
              "h-6 w-6 p-0 transition-opacity",
              showAddButton ? "opacity-100" : "opacity-0"
            )}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="flex-1 relative">
          {(block.type === 'bullet' || block.type === 'numbered') && (
            <div className="absolute left-0 top-1">
              {block.type === 'bullet' ? '•' : '1.'}
            </div>
          )}
          
          <textarea
            ref={textareaRef}
            value={block.content}
            onChange={(e) => handleContentChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={onFocus}
            onInput={adjustTextareaHeight}
            onClick={(e) => e.stopPropagation()}
            placeholder={getPlaceholder()}
            className={getClassName()}
            rows={1}
            style={{
              minHeight: getMinHeight(),
              height: 'auto'
            }}
          />
          
          {showTypeSelector && (
            <BlockTypeSelector
              query={typeSelectorQuery}
              onSelect={handleTypeSelect}
              onClose={() => setShowTypeSelector(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
};
