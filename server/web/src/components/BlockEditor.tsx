import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Block, Workspace, Page } from '@/types';
import { BlockTypeSelector } from './BlockTypeSelector';
import AIQuerySelector from './AIQuerySelector';
import { InlineDiffEditor } from './InlineDiffEditor';
import { TrivialLLMEditor } from './TrivialLLMEditor';
import { TableBlock } from './TableBlock';
import { ToggleBlock } from './ToggleBlock';
import { CanvasBlock } from './CanvasBlock';
import { StatsBlock } from './StatsBlock';
import { StreamingStatusBlock } from './StreamingStatusBlock';
import { GraphingBlock } from './GraphingBlock';
import { cn } from '@/lib/utils';
import { GripVertical, Plus, Bold, Italic, Underline, Strikethrough, Code, Link, Palette, Highlighter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import styles from './BlockEditor.module.css';

// Import SubpageBlock with explicit path
import { SubpageBlock } from './SubpageBlock';

interface BlockEditorProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  onAddBlock: (type?: Block['type']) => void;
  onDeleteBlock: () => void;
  onFocus: () => void;
  isFocused: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  // Block navigation props
  onFocusNextBlock?: () => void;
  onFocusPreviousBlock?: () => void;
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
  // Diff mode trigger
  triggerDiffMode?: boolean;
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
    query?: string;
    history: Array<{
      type: 'status' | 'progress' | 'error' | 'complete' | 'partial_sql' | 'analysis_chunk';
      message: string;
      timestamp: string;
      metadata?: any;
    }>;
  };
  // Markdown paste handler
  onMarkdownPaste?: (markdownText: string, blockId: string) => void;
}

// Enhanced markdown detection patterns
const MARKDOWN_PATTERNS = {
  // Headings - must have space after #
  heading1: /^#\s/,
  heading2: /^##\s/,
  heading3: /^###\s/,
  
  // Lists - must have space after marker
  bullet: /^[-*+]\s/,
  numbered: /^\d+\.\s/,
  
  // Special blocks
  quote: /^>\s/,
  code: /^```\s*$/,  // Code block starts with ``` and optional language
  
  // Divider - three or more dashes
  divider: /^---+\s*$/,
};

// Helper function to detect if content should be split into multiple blocks
const shouldTriggerMultiBlockMarkdown = (content: string): boolean => {
  if (!content || !content.includes('\n')) return false;
  
  const lines = content.split('\n').filter(line => line.trim());
  if (lines.length < 2) return false;
  
  // Check for multiple markdown patterns in different lines
  const patternMatches = lines.map(line => {
    return Object.values(MARKDOWN_PATTERNS).some(pattern => pattern.test(line.trim()));
  });
  
  // If we have multiple lines with markdown patterns, suggest multi-block
  const markdownLineCount = patternMatches.filter(Boolean).length;
  
  // Also check for mixed content (headers + lists, headers + quotes, etc.)
  const hasHeadings = lines.some(line => /^#{1,3}\s/.test(line.trim()));
  const hasLists = lines.some(line => /^[-*+]\s|^\d+\.\s/.test(line.trim()));
  const hasQuotes = lines.some(line => /^>\s/.test(line.trim()));
  const hasCode = content.includes('```');
  
  const contentTypeCount = [hasHeadings, hasLists, hasQuotes, hasCode].filter(Boolean).length;
  
  return markdownLineCount >= 2 || contentTypeCount >= 2;
};

// Helper function to determine if a block type should render markdown
const shouldRenderMarkdown = (blockType: Block['type']): boolean => {
  return ['text', 'heading1', 'heading2', 'heading3', 'bullet', 'numbered', 'quote'].includes(blockType);
};

// Helper function to check if content has markdown formatting
const hasMarkdownFormatting = (content: string): boolean => {
  if (!content) return false;
  
  // Check for inline markdown patterns
  const inlinePatterns = [
    /\*\*[^*]+\*\*/,      // **bold**
    /\*[^*]+\*/,          // *italic*
    /_[^_]+_/,            // _italic_
    /`[^`]+`/,            // `code`
    /~~[^~]+~~/,          // ~~strikethrough~~
    /<u>[^<]+<\/u>/,      // <u>underline</u>
    /\[[^\]]+\]\([^)]+\)/, // [link](url)
    /<span[^>]*style[^>]*color[^>]*>[^<]+<\/span>/i, // <span style="color: ...">text</span>
    /<span[^>]*style[^>]*background[^>]*>[^<]+<\/span>/i, // <span style="background: ...">text</span>
    /<mark[^>]*>[^<]+<\/mark>/i, // <mark>highlight</mark>
  ];
  
  return inlinePatterns.some(pattern => pattern.test(content));
};

// Color picker component
const ColorPicker = ({ 
  position, 
  onColorSelect, 
  onClose, 
  type 
}: {
  position: { top: number; left: number; width: number };
  onColorSelect: (color: string) => void;
  onClose: () => void;
  type: 'text' | 'background';
}) => {
  const colors = [
    '#000000', '#374151', '#6B7280', '#9CA3AF', '#D1D5DB', '#F3F4F6',
    '#DC2626', '#EA580C', '#D97706', '#CA8A04', '#65A30D', '#16A34A',
    '#0891B2', '#2563EB', '#7C3AED', '#C026D3', '#DC2626', '#BE123C'
  ];

  return (
    <div
      className="absolute z-50 bg-background border border-border rounded-md shadow-lg p-2"
      style={{
        top: position.top - 80,
        left: Math.max(0, position.left + (position.width / 2) - 100),
        minWidth: '160px'
      }}
      onMouseDown={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <div className="grid grid-cols-6 gap-1">
        {colors.map((color) => (
          <button
            key={color}
            className="w-6 h-6 rounded border border-border hover:scale-110 transition-transform"
            style={{ backgroundColor: color }}
            onMouseDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onColorSelect(color);
            }}
            title={color}
          />
        ))}
      </div>
    </div>
  );
};

// Add formatting toolbar component
const FormattingToolbar = ({ 
  position, 
  onFormat, 
  onClose,
  onColorFormat,
  showColorPicker,
  showHighlightPicker,
  onToggleColorPicker,
  onToggleHighlightPicker
}: { 
  position: { top: number; left: number; width: number };
  onFormat: (type: string) => void;
  onClose: () => void;
  onColorFormat: (color: string, type: 'text' | 'background') => void;
  showColorPicker: boolean;
  showHighlightPicker: boolean;
  onToggleColorPicker: () => void;
  onToggleHighlightPicker: () => void;
}) => {
  return (
    <>
      <div
        className="absolute z-50 bg-background border border-border rounded-md shadow-lg p-1 flex items-center gap-1"
        style={{
          top: position.top,
          left: Math.max(0, position.left + (position.width / 2) - 150), // Center the toolbar, but keep it on screen
          minWidth: '300px'
        }}
        onMouseDown={(e) => {
          // Prevent the toolbar from losing focus when clicking buttons
          e.preventDefault();
          e.stopPropagation();
        }}
      >
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFormat('bold');
          }}
          title="Bold (Ctrl+B)"
        >
          <Bold className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFormat('italic');
          }}
          title="Italic (Ctrl+I)"
        >
          <Italic className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFormat('underline');
          }}
          title="Underline (Ctrl+U)"
        >
          <Underline className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFormat('strikethrough');
          }}
          title="Strikethrough (Ctrl+Shift+S)"
        >
          <Strikethrough className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFormat('code');
          }}
          title="Code (Ctrl+E)"
        >
          <Code className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFormat('link');
          }}
          title="Link (Ctrl+K)"
        >
          <Link className="h-4 w-4" />
        </Button>
        <div className="w-px h-6 bg-border mx-1" />
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleColorPicker();
          }}
          title="Text Color"
        >
          <Palette className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleHighlightPicker();
          }}
          title="Highlight"
        >
          <Highlighter className="h-4 w-4" />
        </Button>
      </div>
      
      {showColorPicker && (
        <ColorPicker
          position={position}
          onColorSelect={(color) => onColorFormat(color, 'text')}
          onClose={() => onToggleColorPicker()}
          type="text"
        />
      )}
      
      {showHighlightPicker && (
        <ColorPicker
          position={position}
          onColorSelect={(color) => onColorFormat(color, 'background')}
          onClose={() => onToggleHighlightPicker()}
          type="background"
        />
      )}
    </>
  );
};

export const BlockEditor = ({
  block,
  onUpdate,
  onAddBlock,
  onDeleteBlock,
  onFocus,
  isFocused,
  onMoveUp,
  onMoveDown,
  onFocusNextBlock,
  onFocusPreviousBlock,
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
  triggerDiffMode = false,
  workspace,
  page,
  onNavigateToPage,
  onCreateCanvasPage,
  streamingState,
  onMarkdownPaste
}: BlockEditorProps) => {
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [typeSelectorQuery, setTypeSelectorQuery] = useState('');
  const [showAIQuery, setShowAIQuery] = useState(false);
  const [aiQuery, setAIQuery] = useState('');
  const [aiQueryPosition, setAIQueryPosition] = useState<{ top: number; left: number } | null>(null);
  const [isAILoading, setIsAILoading] = useState(false);
  const [diffMode, setDiffMode] = useState(false);
  const [originalTextForDiff, setOriginalTextForDiff] = useState('');
  const [showAddButton, setShowAddButton] = useState(false);
  const [justCreatedFromSlash, setJustCreatedFromSlash] = useState(false);
  // New state to handle the transition from markdown to editing mode
  const [isTransitioningToEdit, setIsTransitioningToEdit] = useState(false);
  // Formatting toolbar state
  const [showFormattingToolbar, setShowFormattingToolbar] = useState(false);
  const [formattingToolbarPosition, setFormattingToolbarPosition] = useState<{ top: number; left: number; width: number } | null>(null);
  const [selectedText, setSelectedText] = useState('');
  const [selectionStart, setSelectionStart] = useState(0);
  const [selectionEnd, setSelectionEnd] = useState(0);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [showHighlightPicker, setShowHighlightPicker] = useState(false);
  
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

  // Reset transition state when focus changes
  useEffect(() => {
    if (isFocused) {
      setIsTransitioningToEdit(false);
    }
  }, [isFocused]);

  // Add formatting functions
  const applyFormatting = (formatType: string) => {
    if (!textareaRef.current) return;
    
    const textarea = textareaRef.current;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const content = textarea.value;
    const selectedText = content.substring(start, end);
    
    let before = '';
    let after = '';
    let newText = selectedText;
    let cursorOffset = 0;
    
    switch (formatType) {
      case 'bold':
        // Check if already bold
        if (selectedText.startsWith('**') && selectedText.endsWith('**') && selectedText.length > 4) {
          newText = selectedText.slice(2, -2);
          cursorOffset = 0;
        } else {
          before = '**';
          after = '**';
          newText = selectedText;
          cursorOffset = 2;
        }
        break;
        
      case 'italic':
        // Check if already italic
        if (selectedText.startsWith('*') && selectedText.endsWith('*') && selectedText.length > 2 && !selectedText.startsWith('**')) {
          newText = selectedText.slice(1, -1);
          cursorOffset = 0;
        } else {
          before = '*';
          after = '*';
          newText = selectedText;
          cursorOffset = 1;
        }
        break;
        
      case 'underline':
        // Use HTML-style underline since markdown doesn't have native underline
        if (selectedText.startsWith('<u>') && selectedText.endsWith('</u>') && selectedText.length > 7) {
          newText = selectedText.slice(3, -4);
          cursorOffset = 0;
        } else {
          before = '<u>';
          after = '</u>';
          newText = selectedText;
          cursorOffset = 3;
        }
        break;
        
      case 'strikethrough':
        if (selectedText.startsWith('~~') && selectedText.endsWith('~~') && selectedText.length > 4) {
          newText = selectedText.slice(2, -2);
          cursorOffset = 0;
        } else {
          before = '~~';
          after = '~~';
          newText = selectedText;
          cursorOffset = 2;
        }
        break;
        
      case 'code':
        if (selectedText.startsWith('`') && selectedText.endsWith('`') && selectedText.length > 2) {
          newText = selectedText.slice(1, -1);
          cursorOffset = 0;
        } else {
          before = '`';
          after = '`';
          newText = selectedText;
          cursorOffset = 1;
        }
        break;
        
      case 'link':
        if (selectedText) {
                  before = '[';
        after = '](https://)';
        newText = selectedText;
        cursorOffset = selectedText.length + 3; // Position cursor after https://
      } else {
        before = '[';
        after = '](https://)';
        newText = 'Link text';
        cursorOffset = 1; // Position cursor to select "Link text"
      }
      break;
      
    case 'textColor':
      // This will be handled by the color picker
      return;
      
    case 'highlight':
      // This will be handled by the highlight picker
      return;
    }
    
    const newContent = content.substring(0, start) + before + newText + after + content.substring(end);
    
    // Update content
    onUpdate({ content: newContent });
    
    // Set cursor position and maintain focus
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        const newCursorPos = formatType === 'link' && !selectedText 
          ? start + 1 // Start of "Link text" for replacement
          : start + before.length + cursorOffset;
        const newCursorEnd = formatType === 'link' && !selectedText
          ? start + 1 + 9 // Select "Link text"
          : newCursorPos;
        
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newCursorPos, newCursorEnd);
        adjustTextareaHeight();
        
        // If we still have a selection after link formatting, keep the toolbar open
        if (formatType === 'link' && !selectedText) {
          // For link formatting with no initial selection, we now have selected text
          setTimeout(() => {
            setShowFormattingToolbar(false);
          }, 100);
        } else {
          setShowFormattingToolbar(false);
        }
      }
    });
  };

  // Color formatting functions
  const applyColorFormatting = (color: string, type: 'text' | 'background') => {
    if (!textareaRef.current) return;
    
    const textarea = textareaRef.current;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const content = textarea.value;
    const selectedText = content.substring(start, end);
    
    if (!selectedText) return;
    
    let before = '';
    let after = '';
    
    if (type === 'text') {
      before = `<span style="color: ${color}">`;
      after = '</span>';
    } else if (type === 'background') {
      before = `<span style="background-color: ${color}; padding: 2px 4px; border-radius: 3px;">`;
      after = '</span>';
    }
    
    const newContent = content.substring(0, start) + before + selectedText + after + content.substring(end);
    
    // Update content
    onUpdate({ content: newContent });
    
    // Set cursor position and maintain focus
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        const newCursorPos = start + before.length + selectedText.length + after.length;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        adjustTextareaHeight();
        setShowFormattingToolbar(false);
        setShowColorPicker(false);
        setShowHighlightPicker(false);
      }
    });
  };

  // Handle text selection for formatting toolbar
  const handleTextSelection = () => {
    if (!textareaRef.current || !blockRef.current) return;
    
    const textarea = textareaRef.current;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    
    if (start !== end && isFocused) {
      const selectedText = textarea.value.substring(start, end);
      setSelectedText(selectedText);
      setSelectionStart(start);
      setSelectionEnd(end);
      
      // Calculate more accurate position based on selection
      const textareaRect = textarea.getBoundingClientRect();
      const containerRect = blockRef.current.getBoundingClientRect();
      
      // Get text metrics to calculate selection position
      const textBeforeSelection = textarea.value.substring(0, start);
      const lines = textBeforeSelection.split('\n');
      const currentLineIndex = lines.length - 1;
      
      // Estimate line height from computed styles
      const computedStyle = window.getComputedStyle(textarea);
      const lineHeight = parseFloat(computedStyle.lineHeight) || parseFloat(computedStyle.fontSize) * 1.2;
      const paddingTop = parseFloat(computedStyle.paddingTop) || 0;
      
      // Calculate approximate position of selection start
      const selectionTop = textareaRect.top + paddingTop + (currentLineIndex * lineHeight);
      
      // Position toolbar above the selection
      const position = {
        top: selectionTop - containerRect.top - 60, // 60px above selection, relative to block container
        left: textareaRect.left - containerRect.left, // Left edge of textarea, relative to block container
        width: textareaRect.width
      };
      
      setFormattingToolbarPosition(position);
      setShowFormattingToolbar(true);
    } else {
      setShowFormattingToolbar(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Handle formatting shortcuts
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
      switch (e.key.toLowerCase()) {
        case 'b':
          e.preventDefault();
          applyFormatting('bold');
          return;
        case 'i':
          e.preventDefault();
          applyFormatting('italic');
          return;
        case 'u':
          e.preventDefault();
          applyFormatting('underline');
          return;
        case 'e':
          e.preventDefault();
          applyFormatting('code');
          return;
        case 'k':
          e.preventDefault();
          applyFormatting('link');
          return;
      }
    }
    
    // Handle Ctrl+Shift+S for strikethrough
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 's') {
      e.preventDefault();
      applyFormatting('strikethrough');
      return;
    }

    if (e.key === 'Enter') {
      // If we just created this block from a slash command or markdown conversion, don't create a new block yet
      if (justCreatedFromSlash) {
        setJustCreatedFromSlash(false);
        return; // Allow normal Enter behavior (line break)
      }
      
      // Handle bulleted and numbered lists with proper continuation behavior
      if (block.type === 'bullet' || block.type === 'numbered') {
        if (e.shiftKey) {
          // Shift+Enter: create line break within the list item
          return;
        } else {
          e.preventDefault();
          
          // If the current list item is empty, exit the list (create regular text block)
          if (block.content.trim() === '') {
            onUpdate({ type: 'text', indentLevel: 0 });
            return;
          }
          
          // If the current list item has content, create another item of the same type
          // and preserve the indentation level
          onAddBlock(block.type);
          // After creating the new block, we need to set its indent level
          // This will be handled by the parent component receiving the type and setting indentLevel
          return;
        }
      }
      
      // For quote and code blocks: Enter creates new block, Shift+Enter creates line break
      if (['quote', 'code'].includes(block.type)) {
        if (e.shiftKey) {
          // Shift+Enter: create line break within the special block
          return;
        } else {
          // Enter: exit the special block and create a new paragraph block
          e.preventDefault();
          onAddBlock();
          return;
        }
      }
      
      // For headings, dividers, and custom block types, Enter always creates a new block
      if (['heading1', 'heading2', 'heading3', 'divider', 'table', 'toggle', 'subpage', 'canvas', 'stats'].includes(block.type)) {
        e.preventDefault();
        onAddBlock();
        return;
      }
      
      // For regular text blocks (paragraph): Enter creates new block, Shift+Enter creates line break
      if (e.shiftKey) {
        // Shift+Enter: create line break within the block
        return;
      } else {
        // Enter: create new block
        e.preventDefault();
        onAddBlock();
        return;
      }
      
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
    } else if (e.key === 'ArrowUp' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey) {
      // Navigate to previous block
      e.preventDefault();
      onFocusPreviousBlock?.();
    } else if (e.key === 'ArrowDown' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey) {
      // Navigate to next block
      e.preventDefault();
      onFocusNextBlock?.();
    } else if (e.key === 'Tab' && (block.type === 'bullet' || block.type === 'numbered')) {
      e.preventDefault();
      const currentIndent = block.indentLevel || 0;
      
      if (e.shiftKey && (e.ctrlKey || e.metaKey)) {
        // Ctrl/Cmd+Shift+Tab: jump to first indent level (level 0)
        if (currentIndent > 0) {
          onUpdate({ indentLevel: 0 });
        }
      } else if (e.shiftKey) {
        // Shift+Tab: decrease indentation (unindent)
        if (currentIndent > 0) {
          onUpdate({ indentLevel: currentIndent - 1 });
        }
      } else {
        // Tab: increase indentation (indent)
        const maxIndent = 5; // Limit to 5 levels of indentation
        if (currentIndent < maxIndent) {
          onUpdate({ indentLevel: currentIndent + 1 });
        }
      }
    }
  };

  // Function to parse and convert pasted markdown content
  const parseMarkdownContent = (content: string) => {
    const lines = content.split('\n');
    const blocks = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmedLine = line.trim();
      
      // Skip empty lines
      if (!trimmedLine) {
        continue;
      }
      
      let blockType: Block['type'] = 'text';
      let blockContent = line;
      let indentLevel = 0;
      
      // Check for markdown patterns
      for (const [type, pattern] of Object.entries(MARKDOWN_PATTERNS)) {
        if (pattern.test(trimmedLine)) {
          blockType = type as Block['type'];
          
          // Extract content based on type
          if (type === 'heading1') {
            blockContent = trimmedLine.replace(/^#\s/, '');
          } else if (type === 'heading2') {
            blockContent = trimmedLine.replace(/^##\s/, '');
          } else if (type === 'heading3') {
            blockContent = trimmedLine.replace(/^###\s/, '');
          } else if (type === 'bullet') {
            blockContent = trimmedLine.replace(/^[-*+]\s/, '');
            // Calculate indent level based on leading whitespace
            const leadingSpaces = line.match(/^ */)?.[0]?.length || 0;
            indentLevel = Math.floor(leadingSpaces / 2); // 2 spaces per indent level
          } else if (type === 'numbered') {
            blockContent = trimmedLine.replace(/^\d+\.\s/, '');
            const leadingSpaces = line.match(/^ */)?.[0]?.length || 0;
            indentLevel = Math.floor(leadingSpaces / 2);
          } else if (type === 'quote') {
            blockContent = trimmedLine.replace(/^>\s/, '');
          } else if (type === 'code') {
            blockContent = '';
            blockType = 'code';
            // For code blocks, collect all content until closing ```
            i++; // Skip the opening ```
            const codeLines = [];
            while (i < lines.length && !lines[i].trim().startsWith('```')) {
              codeLines.push(lines[i]);
              i++;
            }
            blockContent = codeLines.join('\n');
          } else if (type === 'divider') {
            blockContent = '';
          }
          
          break;
        }
      }
      
      blocks.push({
        type: blockType,
        content: blockContent,
        indentLevel: indentLevel
      });
    }
    
    return blocks;
  };

  // Handle paste events to convert markdown
  const handlePaste = (e: React.ClipboardEvent) => {
    const pastedText = e.clipboardData.getData('text');
    console.log('🎯 BlockEditor: Paste detected, text:', pastedText);
    
    // Only process if it looks like markdown (contains markdown patterns)
    const hasMarkdown = Object.values(MARKDOWN_PATTERNS).some(pattern => 
      pastedText.split('\n').some(line => pattern.test(line.trim()))
    );
    
    console.log('🎯 BlockEditor: Has markdown:', hasMarkdown);
    
    if (hasMarkdown) {
      e.preventDefault();
      console.log('🎯 BlockEditor: Processing as markdown paste');
      
      // Pass the markdown parsing up to PageEditor for proper multi-block creation
      if (onMarkdownPaste) {
        console.log('🎯 BlockEditor: Calling onMarkdownPaste');
        onMarkdownPaste(pastedText, block.id);
        return;
      }
      
      console.log('🎯 BlockEditor: No onMarkdownPaste handler, using fallback');
      
      // Fallback: parse and convert just the first line for single block
      const parsedBlocks = parseMarkdownContent(pastedText);
      
      if (parsedBlocks.length > 0) {
        const firstBlock = parsedBlocks[0];
        console.log('🎯 BlockEditor: Updating with fallback:', firstBlock);
        onUpdate({ 
          type: firstBlock.type, 
          content: firstBlock.content,
          indentLevel: firstBlock.indentLevel || 0
        });
        return;
      }
    }
    
    console.log('🎯 BlockEditor: Not markdown, using default paste behavior');
    // If not markdown or single line, let default paste behavior handle it
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
      
      // Check for markdown patterns BEFORE checking for commands
      // Only convert if we're at the beginning of a block or line
      const isAtLineStart = currentLineStart === 0 || currentLineStart === textBeforeCursor.lastIndexOf('\n') + 1;
      
      if (isAtLineStart) {
        // Check each markdown pattern
        for (const [blockType, pattern] of Object.entries(MARKDOWN_PATTERNS)) {
          if (pattern.test(currentLine)) {
            console.log(`🎯 BlockEditor: Markdown pattern detected: ${blockType} from "${currentLine}"`);
            
            // Extract content after the markdown syntax
            let newContent = '';
            
            if (blockType === 'heading1') {
              newContent = currentLine.replace(/^#\s/, '');
            } else if (blockType === 'heading2') {
              newContent = currentLine.replace(/^##\s/, '');
            } else if (blockType === 'heading3') {
              newContent = currentLine.replace(/^###\s/, '');
            } else if (blockType === 'bullet') {
              newContent = currentLine.replace(/^[-*+]\s/, '');
            } else if (blockType === 'numbered') {
              newContent = currentLine.replace(/^\d+\.\s/, '');
            } else if (blockType === 'quote') {
              newContent = currentLine.replace(/^>\s/, '');
                         } else if (blockType === 'code') {
               newContent = currentLine.replace(/^```\s*$/, '');
             } else if (blockType === 'divider') {
               newContent = '';
             }
            
            // Include any content after the current line
            const remainingContent = content.substring(cursorPosition);
            const fullNewContent = newContent + remainingContent;
            
            // Convert the block type and update content
            onUpdate({ 
              type: blockType as Block['type'], 
              content: fullNewContent,
              // Preserve indent level for lists, reset for others
              ...(blockType === 'bullet' || blockType === 'numbered' 
                ? { indentLevel: block.indentLevel || 0 }
                : { indentLevel: 0 }
              )
            });
            
            setJustCreatedFromSlash(true); // Prevent immediate new block creation
            
            // Focus the textarea after conversion
            setTimeout(() => {
              if (textareaRef.current) {
                textareaRef.current.focus();
                // Position cursor at the end of the converted content
                const newCursorPos = newContent.length;
                textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
              }
            }, 0);
            
            return; // Exit early, don't process other commands
          }
        }
      }
      
      // Check if current line starts with '/' for block type selector or chart commands
      if (currentLine.startsWith('/') && !currentLine.startsWith('//')) {
        const query = currentLine.slice(1);
        
        // Check for chart commands
        if (query.startsWith('chart') || query.startsWith('graph')) {
          // Convert to graphing block and extract query
          const chartQuery = query.startsWith('chart') 
            ? query.slice(5).trim() // Remove 'chart' prefix
            : query.slice(5).trim(); // Remove 'graph' prefix
          
          // Switch to graphing block type
          onUpdate({ 
            type: 'graphing',
            content: chartQuery,
            properties: {
              ...block.properties,
              graphingData: {
                query: chartQuery,
                lastGenerated: new Date()
              }
            }
          });
          setShowTypeSelector(false);
          setJustCreatedFromSlash(true);
          return;
        }
        
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
      // Check if current line starts with '@' for diff mode
      else if (currentLine.startsWith('@')) {
        const query = currentLine.slice(1);
        
        // Immediately activate diff mode when @ is detected
        console.log(`🔄 BlockEditor: @ detected, activating diff mode`);
        
        // Remove the @ command from content to get original text
        const contentWithoutCommand = content.substring(0, currentLineStart) + content.substring(cursorPosition);
        setOriginalTextForDiff(contentWithoutCommand.trim());
        setDiffMode(true);
        
        // Don't show AI query selector for @ commands
        setShowAIQuery(false);
        setShowTypeSelector(false);
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
        } else if (trimmedLine.startsWith('@')) {
          const query = trimmedLine.slice(1);
          
          // Immediately activate diff mode when @ is detected
          console.log(`🔄 BlockEditor: @ detected in fallback, activating diff mode`);
          setOriginalTextForDiff(content.replace('@' + query, '').trim());
          setDiffMode(true);
          
          // Don't show AI query selector for @ commands
          setShowAIQuery(false);
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
    
    // Check if this is a diff mode command (triggered by @)
    if (query.startsWith('diff:') || query === 'diff' || query === '') {
      console.log(`🔄 BlockEditor: Diff mode command detected: ${query}`);
      setOriginalTextForDiff(block.content);
      setDiffMode(true);
      setShowAIQuery(false);
      setAIQuery('');
      setAIQueryPosition(null);
      return;
    }
    
    setIsAILoading(true);
    console.log(`⏳ BlockEditor: AI loading state set to true`);
    
    // Enhanced command removal logic
    const content = block.content;
    let newContent = content;
    let newCursorPosition = 0;
    
    console.log(`🧹 BlockEditor: Starting command removal from content: "${content}"`);
    
    // Method 1: Try to find exact pattern match
    const patterns = [`//${query}`, `@${query}`];
    let patternFound = false;
    
    for (const searchPattern of patterns) {
      const patternIndex = content.indexOf(searchPattern);
      if (patternIndex >= 0) {
        console.log(`🎯 BlockEditor: Found exact pattern '${searchPattern}' at position ${patternIndex}`);
        
        const beforePattern = content.substring(0, patternIndex);
        const afterPattern = content.substring(patternIndex + searchPattern.length);
        
        // Remove trailing whitespace or newline after the command
        let extraCharsToRemove = 0;
        if (afterPattern.startsWith(' ')) {
          extraCharsToRemove = 1;
        } else if (afterPattern.startsWith('\n')) {
          extraCharsToRemove = 1;
        }
        
        newContent = beforePattern + afterPattern.substring(extraCharsToRemove);
        newCursorPosition = patternIndex;
        patternFound = true;
        
        console.log(`🔧 BlockEditor: Exact pattern removal:`, {
          originalLength: content.length,
          newLength: newContent.length,
          patternIndex,
          searchPattern,
          extraCharsToRemove,
          newCursorPosition
        });
        break;
      }
    }
    
    // Method 2: If exact pattern not found, try regex-based removal
    if (!patternFound) {
      console.log(`⚠️ BlockEditor: Exact pattern not found, trying regex-based removal`);
      
      // Create regex patterns for more flexible matching
      const regexPatterns = [
        new RegExp(`//\\s*${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*`, 'g'),
        new RegExp(`@\\s*${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*`, 'g'),
        // Also try to match just the command markers if query is empty or whitespace
        /\/\/\s*$/gm,
        /@\s*$/gm
      ];
      
      let regexFound = false;
      for (const regex of regexPatterns) {
        const match = content.match(regex);
        if (match && match[0]) {
          console.log(`🎯 BlockEditor: Found regex match: "${match[0]}"`);
          newContent = content.replace(regex, '');
          regexFound = true;
          break;
        }
      }
      
      if (!regexFound) {
        console.log(`⚠️ BlockEditor: No regex matches, trying line-by-line removal`);
        
        // Method 3: Line-by-line removal as final fallback
        const lines = content.split('\n');
        const newLines = lines.map(line => {
          const trimmedLine = line.trim();
          
          // Remove lines that are just commands
          if (trimmedLine === '//' || trimmedLine === '@' || 
              trimmedLine === `//${query}` || trimmedLine === `@${query}` ||
              trimmedLine.startsWith('// ') || trimmedLine.startsWith('@ ')) {
            return '';
          }
          
          // Remove command from within lines
          return line
            .replace(new RegExp(`//\\s*${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*`, 'g'), '')
            .replace(new RegExp(`@\\s*${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*`, 'g'), '')
            .replace(/\/\/\s*$/, '')
            .replace(/@\s*$/, '');
        });
        
        newContent = newLines.join('\n');
        
        // Clean up multiple consecutive newlines and trim
        newContent = newContent.replace(/\n\s*\n\s*\n/g, '\n\n').trim();
        
        console.log(`🔧 BlockEditor: Line-by-line removal applied`);
      }
    }
    
    // Final cleanup: remove any remaining isolated command markers
    newContent = newContent
      .replace(/^\s*\/\/\s*$/gm, '')  // Remove lines with just //
      .replace(/^\s*@\s*$/gm, '')    // Remove lines with just @
      .replace(/\n\s*\n\s*\n/g, '\n\n') // Clean up multiple newlines
      .trim();
    
    console.log(`🧹 BlockEditor: Final content after cleanup: "${newContent}"`);
    console.log(`📊 BlockEditor: Content length change: ${content.length} → ${newContent.length}`);
    
    // Update the block content
    onUpdate({ content: newContent });
    console.log(`✅ BlockEditor: Block content updated after command removal`);
    
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

  const handleDiffAccept = (newText: string) => {
    console.log(`✅ BlockEditor: Diff accepted, updating content`);
    onUpdate({ content: newText });
    setDiffMode(false);
    setOriginalTextForDiff('');
  };

  const handleDiffCancel = () => {
    console.log(`❌ BlockEditor: Diff cancelled`);
    setDiffMode(false);
    setOriginalTextForDiff('');
    // Restore original content
    onUpdate({ content: originalTextForDiff });
  };

  // Handle external diff mode trigger
  useEffect(() => {
    if (triggerDiffMode && !diffMode) {
      console.log(`🔄 BlockEditor: External diff mode trigger activated`);
      setOriginalTextForDiff(block.content || '');
      setDiffMode(true);
    }
  }, [triggerDiffMode, diffMode, block.content]);

  const handleDiffInsertBelow = (newText: string) => {
    console.log(`⬇️ BlockEditor: Diff insert below`);
    setDiffMode(false);
    setOriginalTextForDiff('');
    // Add a new block below with the new content
    onAddBlock();
    // Note: We'd need to update the newly created block with newText
    // This would require changes to the parent component's onAddBlock handler
  };

  const handleDiffTryAgain = () => {
    console.log(`🔄 BlockEditor: Diff try again`);
    // This will be handled by the InlineDiffEditor component
    // which will reset to input mode when try again is clicked
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
      case 'bullet': return "List";
      case 'numbered': return "List";
      case 'quote': return "Quote";
      case 'code': return "Code";
      case 'divider': return "---";
      case 'table': return "Table";
      case 'toggle': return "Toggle list";
      case 'subpage': return "Sub-page link";
      case 'canvas': return "Canvas analysis";
      case 'stats': return "Statistics";
      default: return "Type '/' for commands, '//' for AI • Select text for formatting";
    }
  };

  // Calculate numbered list position
  const getNumberedListIndex = () => {
    if (!page || block.type !== 'numbered') return 1;
    
    const currentIndentLevel = block.indentLevel || 0;
    const blocksBeforeThis = page.blocks
      .filter(b => b.order < block.order)
      .sort((a, b) => a.order - b.order);
    
    let listNumber = 1;
    let consecutiveNumberedBlocks = 0;
    
    // Count consecutive numbered blocks at the same indent level before this one
    for (let i = blocksBeforeThis.length - 1; i >= 0; i--) {
      const prevBlock = blocksBeforeThis[i];
      const prevIndentLevel = prevBlock.indentLevel || 0;
      
      if (prevBlock.type === 'numbered' && prevIndentLevel === currentIndentLevel) {
        consecutiveNumberedBlocks++;
      } else if (prevBlock.type === 'numbered' && prevIndentLevel < currentIndentLevel) {
        // If we encounter a less indented numbered block, stop counting
        break;
      } else if (prevBlock.type !== 'numbered' && prevIndentLevel <= currentIndentLevel) {
        // If we encounter a non-numbered block at same or less indent level, stop counting
        break;
      }
    }
    
    return consecutiveNumberedBlocks + 1;
  };

  // Get indentation classes and left positioning
  const getIndentStyle = () => {
    const indentLevel = block.indentLevel || 0;
    const baseIndent = 32; // 8 * 4px (pl-8)
    const additionalIndent = indentLevel * 24; // 24px per indent level
    return {
      paddingLeft: `${baseIndent + additionalIndent}px`,
      marginLeft: `${indentLevel * 24}px`
    };
  };

  const getMarkerPosition = () => {
    const indentLevel = block.indentLevel || 0;
    const baseLeft = indentLevel * 24; // Match the margin-left
    return {
      bullet: baseLeft + 12, // 12px from the indented position
      number: baseLeft // Right-aligned within 24px width from indented position
    };
  };

  const getClassName = () => {
    const baseClasses = "w-full resize-none border-none outline-none bg-transparent overflow-hidden";
    const indentLevel = block.indentLevel || 0;
    
    switch (block.type) {
      case 'heading1':
        return `${baseClasses} text-3xl font-semibold py-2 leading-tight`;
      case 'heading2':
        return `${baseClasses} text-2xl font-semibold py-2 leading-tight`;
      case 'heading3':
        return `${baseClasses} text-xl font-semibold py-1 leading-tight`;
      case 'bullet':
        return `${baseClasses} py-1 leading-relaxed`;
      case 'numbered':
        return `${baseClasses} py-1 leading-relaxed`;
      case 'quote':
        return `${baseClasses} pl-4 border-l-3 border-border text-muted-foreground leading-relaxed`;
      case 'code':
        return `${baseClasses} font-mono text-sm bg-muted/50 p-3 rounded-md leading-relaxed`;
      case 'divider':
        return `${baseClasses} text-center text-muted-foreground`;
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

  // Get markdown rendered content classes
  const getMarkdownClassName = () => {
    const baseClasses = "w-full cursor-text transition-colors hover:bg-muted/20 rounded-sm px-1 -mx-1";
    
    switch (block.type) {
      case 'heading1':
        return `${baseClasses} text-3xl font-semibold py-2 leading-tight`;
      case 'heading2':
        return `${baseClasses} text-2xl font-semibold py-2 leading-tight`;
      case 'heading3':
        return `${baseClasses} text-xl font-semibold py-1 leading-tight`;
      case 'bullet':
        return `${baseClasses} py-1 leading-relaxed`;
      case 'numbered':
        return `${baseClasses} py-1 leading-relaxed`;
      case 'quote':
        return `${baseClasses} pl-4 border-l-3 border-border text-muted-foreground leading-relaxed`;
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
          <hr className="flex-1 border-border" />
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
        {/* Improved list item markers */}
        {block.type === 'bullet' && (
          <div 
            className="absolute top-[7px] text-sm font-medium text-gray-600 dark:text-gray-400 select-none pointer-events-none leading-relaxed"
            style={{ left: `${getMarkerPosition().bullet}px` }}
          >
            •
          </div>
        )}
        
        {block.type === 'numbered' && (
          <div 
            className="absolute top-[7px] w-6 text-sm font-medium text-gray-600 dark:text-gray-400 text-right select-none pointer-events-none leading-relaxed"
            style={{ left: `${getMarkerPosition().number}px` }}
          >
            {getNumberedListIndex()}.
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
        
        {block.type === 'graphing' && (
          <GraphingBlock
            block={block}
            onUpdate={(blockId: string, updates: any) => onUpdate(updates)}
            isFocused={isFocused}
            workspace={workspace}
            page={page}
            onAIQuery={onAIQuery ? async (query: string, blockId: string) => {
              onAIQuery(query, blockId);
              return {};
            } : (() => Promise.resolve({}))}
            streamingState={streamingState}
          />
        )}
        
        {/* Streaming Status Block - shown when AI is processing */}
        {streamingState?.isStreaming && streamingState?.blockId === block.id && (
          <StreamingStatusBlock
            status={streamingState.status}
            progress={streamingState.progress}
            query={streamingState.query || block.content || ''}
            streamingHistory={streamingState.history}
            onCancel={() => {
              // TODO: Implement streaming cancellation
              console.log('Cancel streaming requested');
            }}
          />
        )}
        
        {/* Rendered markdown content (shown when not focused and content has markdown) */}
        {shouldRenderMarkdown(block.type) && 
         !isFocused && 
         !isTransitioningToEdit &&
         !showAIQuery && 
         !diffMode && 
         !(streamingState?.isStreaming && streamingState?.blockId === block.id) &&
         block.content && 
         block.content.trim() && 
         hasMarkdownFormatting(block.content) ? (
          // Unified click-to-edit handling for all block types
          <div 
            className="relative cursor-text hover:bg-muted/20 rounded-sm transition-colors"
            style={{
              // Extend click area for bullet/numbered lists to cover bullet marker
              ...(block.type === 'bullet' || block.type === 'numbered' ? {
                marginLeft: `${-((block.indentLevel || 0) * 24 + 24)}px`,
                paddingLeft: `${(block.indentLevel || 0) * 24 + 24}px`,
              } : {}),
              minHeight: '24px'
            }}
            onClick={(e) => {
              e.stopPropagation();
              console.log('🎯 Markdown content clicked - starting edit transition');
              
              // Set transition state immediately to ensure textarea becomes visible
              setIsTransitioningToEdit(true);
              
              // Call onFocus to update the parent's focus state
              onFocus();
              
              // Use requestAnimationFrame to ensure the DOM updates before focusing
              requestAnimationFrame(() => {
                if (textareaRef.current) {
                  console.log('🎯 Focusing textarea after markdown transition');
                  textareaRef.current.focus();
                  
                  // Position cursor at the end of content by default
                  const length = textareaRef.current.value.length;
                  textareaRef.current.setSelectionRange(length, length);
                  
                  // Adjust height after focusing
                  adjustTextareaHeight();
                }
              });
            }}
          >
            <div 
              className={getMarkdownClassName()}
              style={block.type === 'bullet' || block.type === 'numbered' ? getIndentStyle() : {}}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]} // Enable GitHub Flavored Markdown (includes strikethrough)
                rehypePlugins={[rehypeRaw]} // Enable HTML parsing for HTML tags like <u> and <span>
                components={{
                  // Disable paragraph wrapper for inline content
                  p: ({ children }) => <span>{children}</span>,
                  // Style inline elements
                  strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                  em: ({ children }) => <em className="italic">{children}</em>,
                  code: ({ children }) => (
                    <code className="bg-muted/80 text-muted-foreground px-1 py-0.5 rounded text-sm font-mono">
                      {children}
                    </code>
                  ),
                  del: ({ children }) => <del className="line-through text-muted-foreground">{children}</del>,
                  // Support HTML underline tags
                  u: ({ children }) => <u className="underline">{children}</u>,
                  // Support HTML spans with inline styles for colors
                  span: ({ children, style, ...props }) => (
                    <span style={style} {...props}>{children}</span>
                  ),
                  // Support HTML mark tags for highlights
                  mark: ({ children }) => (
                    <mark className="bg-yellow-200 dark:bg-yellow-800 px-1 rounded">{children}</mark>
                  ),
                  a: ({ href, children }) => (
                    <a 
                      href={href} 
                      className="text-blue-600 hover:text-blue-800 underline"
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {block.content}
              </ReactMarkdown>
            </div>
          </div>
        ) : null}

        {/* Show plain text when not focused, no markdown formatting */}
        {shouldRenderMarkdown(block.type) && 
         !isFocused && 
         !isTransitioningToEdit &&
         !showAIQuery && 
         !diffMode && 
         !(streamingState?.isStreaming && streamingState?.blockId === block.id) &&
         block.content && 
         block.content.trim() && 
         !hasMarkdownFormatting(block.content) ? (
          // Unified click-to-edit handling for all block types (plain text)
          <div 
            className="relative cursor-text hover:bg-muted/20 rounded-sm transition-colors"
            style={{
              // Extend click area for bullet/numbered lists to cover bullet marker
              ...(block.type === 'bullet' || block.type === 'numbered' ? {
                marginLeft: `${-((block.indentLevel || 0) * 24 + 24)}px`,
                paddingLeft: `${(block.indentLevel || 0) * 24 + 24}px`,
              } : {}),
              minHeight: '24px'
            }}
            onClick={(e) => {
              e.stopPropagation();
              console.log('🎯 Plain text clicked - starting edit transition');
              
              // Set transition state immediately
              setIsTransitioningToEdit(true);
              
              // Call onFocus to update the parent's focus state
              onFocus();
              
              // Use requestAnimationFrame to ensure the DOM updates before focusing
              requestAnimationFrame(() => {
                if (textareaRef.current) {
                  console.log('🎯 Focusing textarea after plain text transition');
                  textareaRef.current.focus();
                  // Position cursor at end of content
                  const length = textareaRef.current.value.length;
                  textareaRef.current.setSelectionRange(length, length);
                  adjustTextareaHeight();
                }
              });
            }}
          >
            <div 
              className={cn(getMarkdownClassName(), "px-1 -mx-1")}
              style={block.type === 'bullet' || block.type === 'numbered' ? getIndentStyle() : {}}
            >
              {block.content}
            </div>
          </div>
        ) : null}

        <textarea
          ref={textareaRef}
          value={block.content}
          onChange={(e) => handleContentChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={(e) => {
            console.log('🎯 Textarea focused');
            onFocus();
            // Reset transition state when properly focused
            setIsTransitioningToEdit(false);
          }}
          onBlur={(e) => {
            console.log('🎯 Textarea blurred');
            // Reset transition state when focus is lost
            setIsTransitioningToEdit(false);
            // Hide formatting toolbar when focus is lost
            setShowFormattingToolbar(false);
          }}
          onInput={adjustTextareaHeight}
          onPaste={handlePaste}
          onMouseUp={handleTextSelection}
          onKeyUp={handleTextSelection}
          onSelect={handleTextSelection}
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
            
            // Handle text selection for formatting toolbar
            setTimeout(handleTextSelection, 10);
          }}
          placeholder={getPlaceholder()}
          className={getClassName()}
          rows={1}
          style={{
            minHeight: getMinHeight(),
            height: 'auto',
            ...(block.type === 'bullet' || block.type === 'numbered' ? getIndentStyle() : {}),
            display: showAIQuery || 
                    diffMode ||
                    ['table', 'toggle', 'subpage', 'canvas', 'stats', 'graphing'].includes(block.type) || 
                    (streamingState?.isStreaming && streamingState?.blockId === block.id) ||
                    // Hide textarea when showing markdown content (not focused and not transitioning)
                    (shouldRenderMarkdown(block.type) && !isFocused && !isTransitioningToEdit && block.content && block.content.trim())
                    ? 'none' : 'block' // Show textarea when focused, transitioning to edit, or when content doesn't have markdown
          }}
        />
        
        {/* Formatting Toolbar */}
        {showFormattingToolbar && formattingToolbarPosition && (
          <FormattingToolbar
            position={formattingToolbarPosition}
            onFormat={applyFormatting}
            onClose={() => setShowFormattingToolbar(false)}
            onColorFormat={applyColorFormatting}
            showColorPicker={showColorPicker}
            showHighlightPicker={showHighlightPicker}
            onToggleColorPicker={() => {
              setShowColorPicker(!showColorPicker);
              setShowHighlightPicker(false);
            }}
            onToggleHighlightPicker={() => {
              setShowHighlightPicker(!showHighlightPicker);
              setShowColorPicker(false);
            }}
          />
        )}

        {/* Trivial LLM Editor - replaces the textarea when in diff mode */}
        {diffMode && (
          <div className="mt-2">
            <TrivialLLMEditor
              originalText={originalTextForDiff}
              onAccept={handleDiffAccept}
              onCancel={handleDiffCancel}
              onReject={handleDiffCancel}
              onTryAgain={handleDiffTryAgain}
              onInsertBelow={handleDiffInsertBelow}
              blockType={block.type}
            />
          </div>
        )}

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
                    
                    // Try to restore cursor to the end of the command line
                    const content = block.content;
                    let atIndex = content.lastIndexOf('//');
                    if (atIndex >= 0) {
                      // Find the end of the current line where command was
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
              // Pass block content as editing text for content generation queries (like "summarize this")
              editingText={(() => {
                console.log('🎯 === BlockEditor calculating editingText ===');
                console.log('🎯 Block ID:', block.id);
                console.log('🎯 Block content:', `"${block.content}"`);
                
                // Check if current block content is just a command (starts with // or @)
                let actualContent = block.content || '';
                const isCommand = actualContent.trim().startsWith('//') || actualContent.trim().startsWith('@');
                
                console.log('🎯 Is command detected:', isCommand);
                
                // If current block has actual content (not just commands), use it for editing operations
                if (actualContent && actualContent.trim() && !isCommand) {
                  console.log('🎯 Using current block content for editing');
                  return actualContent;
                }
                
                // For empty blocks or command blocks, use all page content as source material
                const allPageContent = page?.blocks
                  ?.filter(b => b.id !== block.id && b.content && b.content.trim())
                  ?.filter(b => !b.content.trim().startsWith('//') && !b.content.trim().startsWith('@')) // Exclude command blocks
                  ?.map(b => b.content.trim())
                  ?.join('\n\n') || '';
                
                console.log('🎯 Current block empty or command, using all page content. Length:', allPageContent.length);
                console.log('🎯 All page content preview:', `"${allPageContent.substring(0, 100)}..."`);
                console.log('🎯 === END editingText calculation ===');
                
                return allPageContent;
              })()}
              blockContext={{
                blockId: block.id,
                content: block.content,
                type: block.type,
                // Add neighbor context if available (you can enhance this)
                neighbors: {
                  before: undefined, // TODO: Could be passed from parent
                  after: undefined   // TODO: Could be passed from parent
                }
              }}
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
