import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Block, Workspace, Page } from '@/types';
import { BlockTypeSelector } from './BlockTypeSelector';
import { AIQuerySelector } from './AIQuerySelector';
import { TableBlock } from './TableBlock';
import { ToggleBlock } from './ToggleBlock';
import { CanvasBlock } from './CanvasBlock';
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
  onNavigateToPage
}: BlockEditorProps) => {
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [typeSelectorQuery, setTypeSelectorQuery] = useState('');
  const [showAIQuery, setShowAIQuery] = useState(false);
  const [aiQuery, setAIQuery] = useState('');
  const [isAILoading, setIsAILoading] = useState(false);
  const [showAddButton, setShowAddButton] = useState(false);
  const [justCreatedFromSlash, setJustCreatedFromSlash] = useState(false);
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
      if (['heading1', 'heading2', 'heading3', 'divider', 'table', 'toggle', 'subpage', 'canvas'].includes(block.type)) {
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
      if (currentLine.startsWith('/')) {
        const query = currentLine.slice(1);
        setTypeSelectorQuery(query);
        setShowTypeSelector(true);
        setShowAIQuery(false); // Close AI query if open
      } 
      // Check if current line starts with '@' for AI query
      else if (currentLine.startsWith('@')) {
        const query = currentLine.slice(1);
        setAIQuery(query);
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
        }
      }
    } else {
      // Fallback to original logic if we can't get cursor position
      if (content.startsWith('/')) {
        const query = content.slice(1);
        setTypeSelectorQuery(query);
        setShowTypeSelector(true);
        setShowAIQuery(false);
      } else if (content.startsWith('@')) {
        const query = content.slice(1);
        setAIQuery(query);
        setShowAIQuery(true);
        setShowTypeSelector(false);
      } else {
        setShowTypeSelector(false);
        setShowAIQuery(false);
        setTypeSelectorQuery('');
        setAIQuery('');
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
    
    // Remove the @ command from the content while preserving line structure
    const textarea = textareaRef.current;
    if (textarea) {
      console.log(`🔧 BlockEditor: Processing @ command removal with textarea`);
      const cursorPosition = textarea.selectionStart;
      const content = block.content;
      const textBeforeCursor = content.substring(0, cursorPosition);
      const currentLineStart = textBeforeCursor.lastIndexOf('\n') + 1;
      const currentLine = content.substring(currentLineStart, cursorPosition);
      
      console.log(`📍 BlockEditor: Cursor analysis:`, {
        cursorPosition,
        currentLineStart,
        currentLine,
        contentLength: content.length
      });
      
      if (currentLine.startsWith('@')) {
        console.log(`🎯 BlockEditor: Found @ command at line start, removing...`);
        // Calculate the exact positions to preserve content structure
        const beforeCommand = content.substring(0, currentLineStart);
        const afterCursor = content.substring(cursorPosition);
        
        // If there's content after the cursor on the same line, preserve it
        const restOfCurrentLine = content.substring(cursorPosition);
        const nextLineBreak = restOfCurrentLine.indexOf('\n');
        const restOfLine = nextLineBreak >= 0 ? restOfCurrentLine.substring(0, nextLineBreak) : restOfCurrentLine;
        const afterCurrentLine = nextLineBreak >= 0 ? restOfCurrentLine.substring(nextLineBreak) : '';
        
        // Reconstruct content: everything before the line + any remaining content on the line + everything after
        const newContent = beforeCommand + restOfLine + afterCurrentLine;
        
        console.log(`🔧 BlockEditor: Content reconstruction:`, {
          beforeCommand_length: beforeCommand.length,
          restOfLine_length: restOfLine.length,
          afterCurrentLine_length: afterCurrentLine.length,
          newContent_length: newContent.length,
          originalContent_length: content.length
        });
        
        onUpdate({ content: newContent });
        console.log(`✅ BlockEditor: Block content updated after @ command removal`);
        
        // Set cursor position to where the @ command was (beginning of the line)
        setTimeout(() => {
          if (textareaRef.current) {
            const newCursorPosition = currentLineStart;
            textareaRef.current.setSelectionRange(newCursorPosition, newCursorPosition);
            console.log(`📍 BlockEditor: Cursor repositioned to ${newCursorPosition}`);
          }
        }, 0);
      }
    } else {
      console.log(`🔧 BlockEditor: Processing @ command removal without textarea (fallback)`);
      // Fallback: if @ was at the beginning of the content, remove just the @ and query
      if (block.content.startsWith('@')) {
        const atCommandEnd = block.content.indexOf(' ');
        if (atCommandEnd >= 0) {
          const newContent = block.content.substring(atCommandEnd + 1);
          onUpdate({ content: newContent });
          console.log(`✅ BlockEditor: Fallback content update (space found at ${atCommandEnd})`);
        } else {
          // If there's no space, check for newline after the command
          const newlineIndex = block.content.indexOf('\n');
          if (newlineIndex >= 0) {
            const newContent = block.content.substring(newlineIndex + 1);
            onUpdate({ content: newContent });
            console.log(`✅ BlockEditor: Fallback content update (newline found at ${newlineIndex})`);
          } else {
            onUpdate({ content: '' });
            console.log(`✅ BlockEditor: Fallback content cleared (no delimiter found)`);
          }
        }
      }
    }
    
    // Close the AI query selector
    setShowAIQuery(false);
    setAIQuery('');
    console.log(`🚪 BlockEditor: AI query selector closed`);
    
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
    }, 0);
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
      default: return "Type '/' for commands, '@' for AI";
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
      case 'table':
      case 'toggle':
      case 'subpage':
        return `${baseClasses} hidden`; // Hide textarea for custom components
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
      case 'table':
      case 'toggle':
      case 'subpage':
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
            display: showAIQuery || ['table', 'toggle', 'subpage', 'canvas'].includes(block.type) ? 'none' : 'block' // Hide textarea when AI query is active or for custom components
          }}
        />
        
        {/* Inline AI Query Selector - replaces the textarea when active */}
        {showAIQuery && (
          <AIQuerySelector
            query={aiQuery}
            onQuerySubmit={handleAIQuerySubmit}
            onClose={() => {
              // Don't modify content when just closing, preserve everything
              setShowAIQuery(false);
              setAIQuery('');
              
              // Focus back to textarea and restore cursor position
              setTimeout(() => {
                if (textareaRef.current) {
                  textareaRef.current.focus();
                  
                  // Try to restore cursor to the end of the @ command line
                  const content = block.content;
                  const atIndex = content.lastIndexOf('@');
                  if (atIndex >= 0) {
                    // Find the end of the current line where @ command was
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
            isLoading={isAILoading}
          />
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
