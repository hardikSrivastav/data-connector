import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Block, Workspace, Page } from '@/types';
import { BlockTypeSelector } from './BlockTypeSelector';
import { AIQuerySelector } from './AIQuerySelector';
import { TableBlock } from './TableBlock';
import { ToggleBlock } from './ToggleBlock';
import { CanvasBlock } from './CanvasBlock';
import { StatsBlock } from './StatsBlock';
import { StreamingStatusBlock } from './StreamingStatusBlock';
import { cn } from '@/lib/utils';
import { GripVertical, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import styles from './BlockEditor.module.css';

// Import SubpageBlock with explicit path
import { SubpageBlock } from './SubpageBlock';

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
  // AI Query props
  onAIQuery?: (query: string, blockId: string) => void;
  // Workspace for subpage blocks and canvas
  workspace?: Workspace;
  page?: Page;
  onNavigateToPage?: (pageId: string) => void;
  onCreateCanvasPage?: (canvasData: any) => Promise<string>;
  // Streaming state
  streamingState?: {
    isStreaming: boolean;
    status: string;
    progress: number;
    blockId?: string;
  };
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
  isInSelection = false,
  onAIQuery,
  workspace,
  page,
  onNavigateToPage,
  onCreateCanvasPage,
  streamingState
}: BlockEditorProps) => {
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [typeSelectorQuery, setTypeSelectorQuery] = useState('');
  const [showAIQuery, setShowAIQuery] = useState(false);
  const [aiQuery, setAIQuery] = useState('');
  const [aiQueryPosition, setAIQueryPosition] = useState<{ top: number; left: number } | null>(null);
  const [isAILoading, setIsAILoading] = useState(false);
  const [showAddButton, setShowAddButton] = useState(false);
  const [justCreatedFromSlash, setJustCreatedFromSlash] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const blockRef = useRef<HTMLDivElement>(null);

  // Calculate cursor position in pixels
  const calculateCursorPosition = () => {
    if (!textareaRef.current) return { top: 0, left: 0 };
    
    const textarea = textareaRef.current;
    const cursorPosition = textarea.selectionStart;
    const content = textarea.value;
    
    // Find the current line that contains the cursor
    const textBeforeCursor = content.substring(0, cursorPosition);
    const lines = textBeforeCursor.split('\n');
    const currentLineIndex = lines.length - 1;
    
    // Get computed style
    const computedStyle = window.getComputedStyle(textarea);
    const lineHeight = parseFloat(computedStyle.lineHeight) || parseFloat(computedStyle.fontSize) * 1.2;
    const paddingTop = parseFloat(computedStyle.paddingTop) || 0;
    
    // Calculate the top position based on line number
    const top = currentLineIndex * lineHeight + paddingTop;
    
    // For left position, we can just use 0 since we want full width
    const left = 0;
    
    return { top, left };
  };

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
    if (e.key === 'Enter') {
      // If we just created this block from a slash command, don't create a new block yet
      if (justCreatedFromSlash) {
        setJustCreatedFromSlash(false);
        return; // Allow normal Enter behavior (line break)
      }
      
      // Define special block types that should have reversed Enter behavior
      const specialBlockTypes = ['quote', 'code', 'bullet', 'numbered'];
      const isSpecialBlock = specialBlockTypes.includes(block.type);
      
      // For headings, dividers, and custom block types, Enter always creates a new block
      if (['heading1', 'heading2', 'heading3', 'divider', 'table', 'toggle', 'subpage', 'canvas', 'stats'].includes(block.type)) {
        e.preventDefault();
        onAddBlock();
        return;
      }
      
      // For special block types: Enter creates new block, Shift+Enter creates line break
      if (isSpecialBlock) {
        if (e.shiftKey) {
          // Shift+Enter: create line break within the special block
          // Don't preventDefault, let textarea handle it naturally
          return;
        } else {
          // Enter: exit the special block and create a new paragraph block
          e.preventDefault();
          onAddBlock();
          return;
        }
      }
      
      // For regular text blocks (paragraph): Enter creates line break, Shift+Enter creates new block
      if (e.shiftKey) {
        e.preventDefault();
        onAddBlock();
        return;
      }
      
      // Default behavior for regular blocks: allow Enter to create line breaks within the block
      // (don't preventDefault, let the textarea handle it naturally)
      
    } else if (e.key === 'Backspace' && block.content === '') {
      e.preventDefault();
      onDeleteBlock();
    } else if (e.key === 'Delete') {
      // Delete key always deletes the block regardless of content
      e.preventDefault();
      onDeleteBlock();
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'Backspace') {
      // Ctrl/Cmd + Backspace also deletes the block (consistent with selection shortcut)
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
    // Reset the flag when user starts typing
    if (justCreatedFromSlash) {
      setJustCreatedFromSlash(false);
    }
    
    // Only show AI query if this block is currently focused
    if (!isFocused) {
      onUpdate({ content });
      return;
    }
    
    // Get cursor position to detect commands at current line
    const textarea = textareaRef.current;
    if (textarea) {
      const cursorPosition = textarea.selectionStart;
      const textBeforeCursor = content.substring(0, cursorPosition);
      const currentLineStart = textBeforeCursor.lastIndexOf('\n') + 1;
      const currentLine = content.substring(currentLineStart, cursorPosition);
      
      // Check if current line starts with '/' for block type selector
      if (currentLine.startsWith('/') && !currentLine.startsWith('//')) {
        const query = currentLine.slice(1);
        setTypeSelectorQuery(query);
        setShowTypeSelector(true);
        setShowAIQuery(false); // Close AI query if open
      } 
      // Check if current line starts with '//' for AI query
      else if (currentLine.startsWith('//')) {
        const query = currentLine.slice(2);
        setAIQuery(query);
        
        // Calculate position for AI query selector
        const position = calculateCursorPosition();
        setAIQueryPosition(position);
        setShowAIQuery(true);
        setShowTypeSelector(false); // Close type selector if open
      } 
      else {
        // Close selectors if we're no longer on a command line
        if (showAIQuery || showTypeSelector) {
          setShowTypeSelector(false);
          setShowAIQuery(false);
          setTypeSelectorQuery('');
          setAIQuery('');
          setAIQueryPosition(null);
        }
      }
    } else {
      // Fallback: look for commands anywhere in content for better detection
      const lines = content.split('\n');
      let foundAIQuery = false;
      let foundTypeSelector = false;
      
      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('//') && trimmedLine.length > 2) {
          const query = trimmedLine.slice(2);
          setAIQuery(query);
          
          // Calculate position for AI query selector
          const position = calculateCursorPosition();
          setAIQueryPosition(position);
          setShowAIQuery(true);
          setShowTypeSelector(false);
          foundAIQuery = true;
          break;
        } else if (trimmedLine.startsWith('/') && !trimmedLine.startsWith('//') && trimmedLine.length > 1) {
          const query = trimmedLine.slice(1);
          setTypeSelectorQuery(query);
          setShowTypeSelector(true);
          setShowAIQuery(false);
          foundTypeSelector = true;
          break;
        }
      }
      
      // Close selectors if no commands found
      if (!foundAIQuery && !foundTypeSelector) {
        setShowTypeSelector(false);
        setShowAIQuery(false);
        setTypeSelectorQuery('');
        setAIQuery('');
        setAIQueryPosition(null);
      }
    }
    
    onUpdate({ content });
  };

  const handleTypeSelect = (type: Block['type']) => {
    const textarea = textareaRef.current;
    if (textarea) {
      const cursorPosition = textarea.selectionStart;
      const content = block.content;
      const textBeforeCursor = content.substring(0, cursorPosition);
      const currentLineStart = textBeforeCursor.lastIndexOf('\n') + 1;
      const currentLine = content.substring(currentLineStart, cursorPosition);
      
      if (currentLine.startsWith('/')) {
        // Replace only the slash command on current line
        const beforeSlashCommand = content.substring(0, currentLineStart);
        const afterCursor = content.substring(cursorPosition);
        const newContent = beforeSlashCommand + afterCursor;
        
        onUpdate({ type, content: newContent });
      } else {
        // Fallback to clearing content
        onUpdate({ type, content: '' });
      }
    } else {
      onUpdate({ type, content: '' });
    }
    
    setShowTypeSelector(false);
    setTypeSelectorQuery('');
    setJustCreatedFromSlash(true); // Set flag to prevent immediate new block creation
    
    // Focus the textarea after type selection
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }, 0);
  };

  const handleAIQuerySubmit = async (query: string) => {
    console.log(`🚀 BlockEditor: handleAIQuerySubmit called`);
    console.log(`📝 BlockEditor: Query='${query}', BlockId='${block.id}'`);
    console.log(`📝 BlockEditor: Block content before query: '${block.content}'`);
    
    setIsAILoading(true);
    console.log(`⏳ BlockEditor: AI loading state set to true`);
    
    // Remove the // command from the content - simplified approach
    const content = block.content;
    let newContent = content;
    let newCursorPosition = 0;
    
    // Find all instances of '//' followed by the query text
    const searchPattern = '//' + query;
    const patternIndex = content.indexOf(searchPattern);
    
    if (patternIndex >= 0) {
      console.log(`🎯 BlockEditor: Found '//${query}' at position ${patternIndex}`);
      
      // Remove the '//' command and query text
      const beforePattern = content.substring(0, patternIndex);
      const afterPattern = content.substring(patternIndex + searchPattern.length);
      
      // Check if there's a space or newline after the pattern that should also be removed
      let extraCharsToRemove = 0;
      if (afterPattern.startsWith(' ')) {
        extraCharsToRemove = 1;
      } else if (afterPattern.startsWith('\n')) {
        extraCharsToRemove = 1;
      }
      
      newContent = beforePattern + afterPattern.substring(extraCharsToRemove);
      newCursorPosition = patternIndex;
      
      console.log(`🔧 BlockEditor: Content reconstruction:`, {
        originalLength: content.length,
        newLength: newContent.length,
        patternIndex,
        searchPattern,
        extraCharsToRemove,
        newCursorPosition
      });
    } else {
      console.log(`⚠️ BlockEditor: Pattern '//${query}' not found in content`);
      
      // Fallback: try to remove just '//' from the beginning of lines
      const lines = content.split('\n');
      const newLines = lines.map(line => {
        if (line.startsWith('//')) {
          // Remove the '//' and any following whitespace on this line
          return line.replace(/^\/\/\s*.*$/, '').trim();
        }
        return line;
      });
      newContent = newLines.join('\n');
      
      // Remove any empty lines that resulted from the removal
      newContent = newContent.replace(/\n\s*\n/g, '\n').trim();
      
      console.log(`🔧 BlockEditor: Fallback content cleanup applied`);
    }
    
    // Update the block content
    onUpdate({ content: newContent });
    console.log(`✅ BlockEditor: Block content updated after // command removal`);
    
    // Close the AI query selector
    setShowAIQuery(false);
    setAIQuery('');
    setAIQueryPosition(null);
    console.log(`🚪 BlockEditor: AI query selector closed`);
    
    // Set cursor position after content update
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.setSelectionRange(newCursorPosition, newCursorPosition);
        textareaRef.current.focus();
        console.log(`📍 BlockEditor: Cursor repositioned to ${newCursorPosition}`);
      }
    }, 0);
    
    // Call the parent's AI query handler
    if (onAIQuery) {
      console.log(`📞 BlockEditor: Calling parent onAIQuery handler...`);
      console.log(`📞 BlockEditor: Parameters: query='${query}', blockId='${block.id}'`);
      await onAIQuery(query, block.id);
      console.log(`✅ BlockEditor: Parent AI query handler completed`);
    } else {
      console.warn(`⚠️ BlockEditor: No onAIQuery handler provided!`);
    }
    
    setIsAILoading(false);
    console.log(`⏳ BlockEditor: AI loading state set to false`);
    
    // Focus back to textarea
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        console.log(`🎯 BlockEditor: Focus returned to textarea`);
      }
    }, 100); // Slightly longer delay to ensure content update is complete
  };

  const getPlaceholder = () => {
    // Only show placeholder when block is focused and empty
    if (!isFocused || block.content.trim() !== '') {
      return '';
    }
    
    switch (block.type) {
      case 'heading1': return "Heading 1";
      case 'heading2': return "Heading 2";
      case 'heading3': return "Heading 3";
      case 'bullet': return "• List item";
      case 'numbered': return "1. List item";
      case 'quote': return "Quote";
      case 'code': return "Code";
      case 'divider': return "---";
      case 'table': return "Table";
      case 'toggle': return "Toggle list";
      case 'subpage': return "Sub-page link";
      case 'canvas': return "Canvas analysis";
      case 'stats': return "Statistics";
      default: return "Type '/' for commands, '//' for AI";
    }
  };

  const getClassName = () => {
    const baseClasses = "w-full resize-none border-none outline-none bg-transparent overflow-hidden";
    
    switch (block.type) {
      case 'heading1':
        return `${baseClasses} text-3xl font-semibold py-2 leading-tight`;
      case 'heading2':
        return `${baseClasses} text-2xl font-semibold py-2 leading-tight`;
      case 'heading3':
        return `${baseClasses} text-xl font-semibold py-1 leading-tight`;
      case 'bullet':
        return `${baseClasses} pl-6 relative leading-relaxed`;
      case 'numbered':
        return `${baseClasses} pl-6 relative leading-relaxed`;
      case 'quote':
        return `${baseClasses} pl-4 border-l-3 border-gray-300 text-gray-600 leading-relaxed`;
      case 'code':
        return `${baseClasses} font-mono text-sm bg-gray-50/50 p-3 rounded-md leading-relaxed`;
      case 'divider':
        return `${baseClasses} text-center text-gray-400`;
      case 'table':
      case 'toggle':
      case 'subpage':
      case 'canvas':
        return `${baseClasses} hidden`; // Hide textarea for custom components
      case 'stats':
        return `${baseClasses} hidden`; // Hide textarea for custom components
      default:
        return `${baseClasses} py-1 leading-relaxed`;
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
      case 'table':
      case 'toggle':
      case 'subpage':
        return 'auto'; // Let custom components control their height
      case 'stats':
        return 'auto'; // Let custom components control their height
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
        data-block-id={block.id}
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
        <div className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center gap-1 -ml-20">
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-6 w-6 p-0 transition-opacity cursor-grab flex items-center justify-center",
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
              "h-6 w-6 p-0 transition-opacity flex items-center justify-center",
              showAddButton ? "opacity-100" : "opacity-0"
            )}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="flex items-center gap-2 ml-0">
          <hr className="flex-1 border-gray-300" />
        </div>
      </div>
    );
  }

  return (
    <div
      ref={blockRef}
      data-block-id={block.id}
      className={cn(
        "group relative cursor-pointer transition-colors -my-1",
        getSelectionClasses()
      )}
      onMouseEnter={(e) => {
        setShowAddButton(true);
        onMouseEnter?.(e);
      }}
      onMouseLeave={() => setShowAddButton(false)}
      onMouseDown={(e) => {
        // Don't trigger selection mouse down if clicking on interactive elements
        const target = e.target as HTMLElement;
        if (
          target.tagName === 'BUTTON' ||
          target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.closest('button') ||
          target.closest('input') ||
          target.closest('textarea') ||
          target.closest('.canvas-preview') // Don't interfere with canvas navigation
        ) {
          return;
        }
        onMouseDown?.(e);
      }}
      onMouseUp={onMouseUp}
      onClick={(e) => {
        // Don't trigger selection if clicking on interactive elements within the block
        const target = e.target as HTMLElement;
        if (
          target.tagName === 'BUTTON' ||
          target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.closest('button') ||
          target.closest('input') ||
          target.closest('textarea') ||
          target.closest('.canvas-preview') // Don't interfere with canvas navigation
        ) {
          return;
        }
        onSelect?.(e);
      }}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center gap-1 -ml-20">
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            "h-6 w-6 p-0 transition-opacity cursor-grab flex items-center justify-center",
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
            "h-6 w-6 p-0 transition-opacity flex items-center justify-center",
            showAddButton ? "opacity-100" : "opacity-0"
          )}
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      
      <div className="relative ml-0">
        {(block.type === 'bullet' || block.type === 'numbered') && (
          <div className="absolute left-0 top-1">
            {block.type === 'bullet' ? '•' : '1.'}
          </div>
        )}
        
        {/* Custom block components */}
        {block.type === 'table' && (
          <TableBlock
            block={block}
            onUpdate={onUpdate}
            isFocused={isFocused}
          />
        )}
        
        {block.type === 'toggle' && (
          <ToggleBlock
            block={block}
            onUpdate={onUpdate}
            isFocused={isFocused}
            onAddBlock={onAddBlock}
          />
        )}
        
        {block.type === 'subpage' && workspace && (
          <SubpageBlock
            block={block}
            onUpdate={onUpdate}
            isFocused={isFocused}
            workspace={workspace}
            onNavigateToPage={onNavigateToPage}
          />
        )}
        
        {block.type === 'canvas' && workspace && page && (
          <CanvasBlock
            block={block}
            onUpdate={onUpdate}
            isFocused={isFocused}
            workspace={workspace}
            page={page}
            onNavigateToPage={onNavigateToPage}
            onCreateCanvasPage={onCreateCanvasPage}
          />
        )}
        
        {block.type === 'stats' && (
          <StatsBlock
            block={block}
            onUpdate={onUpdate}
            isFocused={isFocused}
            onFocus={onFocus}
            onAddBlock={onAddBlock}
          />
        )}
        
        {/* Streaming Status Block - shown when AI is processing */}
        {streamingState?.isStreaming && streamingState?.blockId === block.id && (
          <StreamingStatusBlock
            status={streamingState.status}
            progress={streamingState.progress}
            query={block.content || ''}
            onCancel={() => {
              // TODO: Implement streaming cancellation
              console.log('Cancel streaming requested');
            }}
          />
        )}
        
        <textarea
          ref={textareaRef}
          value={block.content}
          onChange={(e) => handleContentChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={onFocus}
          onInput={adjustTextareaHeight}
          onClick={(e) => {
            e.stopPropagation();
            // If AI query is showing and user clicks textarea, close it and focus
            if (showAIQuery) {
              setShowAIQuery(false);
              setAIQuery('');
              setAIQueryPosition(null);
              // Don't modify content when clicking away from AI query
              setTimeout(() => {
                if (textareaRef.current) {
                  textareaRef.current.focus();
                  // Position cursor where user clicked
                  const clickPosition = e.currentTarget.selectionStart;
                  textareaRef.current.setSelectionRange(clickPosition, clickPosition);
                }
              }, 0);
            }
          }}
          placeholder={getPlaceholder()}
          className={getClassName()}
          rows={1}
          style={{
            minHeight: getMinHeight(),
            height: 'auto',
            display: showAIQuery || 
                    ['table', 'toggle', 'subpage', 'canvas', 'stats'].includes(block.type) || 
                    (streamingState?.isStreaming && streamingState?.blockId === block.id) 
                    ? 'none' : 'block' // Hide textarea when AI query is active, for custom components, or when streaming
          }}
        />
        
        {/* Inline AI Query Selector - positioned at cursor location */}
        {showAIQuery && aiQueryPosition && (
          <div
            style={{
              position: 'absolute',
              top: aiQueryPosition.top,
              left: 0,
              right: 0,
              zIndex: 1000,
            }}
          >
            <AIQuerySelector
              query={aiQuery}
              onQuerySubmit={handleAIQuerySubmit}
              onClose={() => {
                // Don't modify content when just closing, preserve everything
                setShowAIQuery(false);
                setAIQuery('');
                setAIQueryPosition(null);
                
                // Focus back to textarea and restore cursor position
                setTimeout(() => {
                  if (textareaRef.current) {
                    textareaRef.current.focus();
                    
                    // Try to restore cursor to the end of the // command line
                    const content = block.content;
                    const atIndex = content.lastIndexOf('//');
                    if (atIndex >= 0) {
                      // Find the end of the current line where // command was
                      const afterAt = content.substring(atIndex);
                      const nextLineBreak = afterAt.indexOf('\n');
                      const cursorPos = nextLineBreak >= 0 ? atIndex + nextLineBreak : content.length;
                      textareaRef.current.setSelectionRange(cursorPos, cursorPos);
                    } else {
                      // Fallback: position at end of content
                      textareaRef.current.setSelectionRange(content.length, content.length);
                    }
                  }
                }, 0);
              }}
              isLoading={isAILoading || (streamingState?.isStreaming && streamingState?.blockId === block.id)}
              streamingStatus={streamingState?.isStreaming && streamingState?.blockId === block.id ? streamingState.status : undefined}
              streamingProgress={streamingState?.isStreaming && streamingState?.blockId === block.id ? streamingState.progress : undefined}
            />
          </div>
        )}
        
        {showTypeSelector && (
          <BlockTypeSelector
            query={typeSelectorQuery}
            onSelect={handleTypeSelect}
            onClose={() => setShowTypeSelector(false)}
          />
        )}
      </div>
    </div>
  );
};
