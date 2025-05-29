import { useState, useEffect } from 'react';
import { Page } from '@/types';
import { BlockEditor } from './BlockEditor';
import { Input } from '@/components/ui/input';
import { useBlockSelection } from '@/hooks/useBlockSelection';

interface PageEditorProps {
  page: Page;
  onUpdateBlock: (blockId: string, updates: any) => void;
  onAddBlock: (afterBlockId?: string) => string;
  onDeleteBlock: (blockId: string) => void;
  onUpdatePage: (updates: Partial<Page>) => void;
  onMoveBlock: (blockId: string, newIndex: number) => void;
}

export const PageEditor = ({
  page,
  onUpdateBlock,
  onAddBlock,
  onDeleteBlock,
  onUpdatePage,
  onMoveBlock
}: PageEditorProps) => {
  const [focusedBlockId, setFocusedBlockId] = useState<string | null>(null);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isGlobalDragSelecting, setIsGlobalDragSelecting] = useState(false);
  const [dragSelection, setDragSelection] = useState<{
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
  } | null>(null);
  
  const {
    selectedBlocks,
    isDragging,
    isDragSelecting,
    selectBlock,
    clearSelection,
    deleteSelected,
    handleBlockClick,
    handleMouseDown,
    handleMouseEnter,
    handleMouseUp,
    handleDragStart,
    handleDragOver,
    handleDrop,
    getSelectionInfo,
  } = useBlockSelection(page.blocks);

  // Find the first H1 block to use as title
  const firstH1Block = page.blocks.find(block => block.type === 'heading1');
  const isFirstBlockH1 = page.blocks[0]?.type === 'heading1';

  // Common emoji options (you can expand this list)
  const emojiOptions = [
    '📄', '📝', '📋', '📖', '📚', '💼', '🏢', '🌐', '💡', '🚀',
    '🎯', '📊', '📈', '🔧', '⚙️', '🎨', '🖥️', '📱', '⭐', '🔥',
    '💭', '✅', '❓', '💰', '🏆', '🎉', '🌟', '💎', '🔍', '📌'
  ];

  const handleEmojiSelect = (emoji: string) => {
    onUpdatePage({ icon: emoji });
    setShowEmojiPicker(false);
  };

  const handleEmojiClick = () => {
    setShowEmojiPicker(!showEmojiPicker);
  };

  // Global drag selection handlers
  const handleGlobalMouseDown = (e: React.MouseEvent) => {
    // Only start global drag selection if clicking on empty space (not on blocks or UI elements)
    const target = e.target as HTMLElement;
    
    // Don't start drag selection if clicking on interactive elements
    if (
      target.tagName === 'BUTTON' ||
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.closest('.emoji-picker-container') ||
      target.closest('.block-editor') ||
      showEmojiPicker
    ) {
      return;
    }

    // Prevent default to stop text selection
    e.preventDefault();

    // Get the container element for proper positioning
    const container = e.currentTarget as HTMLElement;
    const rect = container.getBoundingClientRect();
    
    const startX = e.clientX - rect.left;
    const startY = e.clientY - rect.top;

    // Clear existing selection and start global drag selection
    clearSelection();
    setIsGlobalDragSelecting(true);
    setShowEmojiPicker(false); // Close emoji picker if open
    setDragSelection({
      startX,
      startY,
      currentX: startX,
      currentY: startY,
    });
  };

  const handleGlobalMouseMove = (e: React.MouseEvent) => {
    if (isGlobalDragSelecting && dragSelection) {
      e.preventDefault();
      
      const container = e.currentTarget as HTMLElement;
      const rect = container.getBoundingClientRect();
      
      const currentX = e.clientX - rect.left;
      const currentY = e.clientY - rect.top;

      setDragSelection(prev => prev ? {
        ...prev,
        currentX,
        currentY,
      } : null);
    }
  };

  const handleGlobalMouseUp = () => {
    setIsGlobalDragSelecting(false);
    setDragSelection(null);
  };

  // Calculate selection rectangle dimensions
  const getSelectionRectStyle = () => {
    if (!dragSelection) return { display: 'none' };

    const left = Math.min(dragSelection.startX, dragSelection.currentX);
    const top = Math.min(dragSelection.startY, dragSelection.currentY);
    const width = Math.abs(dragSelection.currentX - dragSelection.startX);
    const height = Math.abs(dragSelection.currentY - dragSelection.startY);

    return {
      position: 'absolute' as const,
      left: `${left}px`,
      top: `${top}px`,
      width: `${width}px`,
      height: `${height}px`,
      backgroundColor: 'rgba(59, 130, 246, 0.1)', // Blue with opacity
      border: '1px solid rgb(59, 130, 246)', // Blue border
      pointerEvents: 'none' as const,
      zIndex: 1000,
    };
  };

  const handleBlockMouseEnterDuringGlobalDrag = (blockId: string) => {
    return (e: React.MouseEvent) => {
      if (isGlobalDragSelecting) {
        selectBlock(blockId, true); // Add to selection
      } else {
        handleMouseEnter(blockId, e);
      }
    };
  };

  const handleBlockUpdate = (blockId: string, updates: any) => {
    onUpdateBlock(blockId, updates);
    
    // If this is the first H1 block and content is being updated, sync with page title
    if (firstH1Block && firstH1Block.id === blockId && updates.content !== undefined) {
      onUpdatePage({ title: updates.content || 'Untitled' });
    }
  };

  const handleAddBlock = (afterBlockId?: string) => {
    const newBlockId = onAddBlock(afterBlockId);
    setFocusedBlockId(newBlockId);
    clearSelection(); // Clear selection when adding new block
  };

  const handleDeleteBlock = (blockId: string) => {
    const blockIndex = page.blocks.findIndex(b => b.id === blockId);
    onDeleteBlock(blockId);
    
    // If we deleted the first H1 (title block), update page title
    if (firstH1Block && firstH1Block.id === blockId) {
      const nextH1 = page.blocks.slice(blockIndex + 1).find(b => b.type === 'heading1');
      onUpdatePage({ title: nextH1?.content || 'Untitled' });
    }
    
    // Focus previous block if available
    if (blockIndex > 0) {
      setFocusedBlockId(page.blocks[blockIndex - 1].id);
    } else if (page.blocks.length > 1) {
      setFocusedBlockId(page.blocks[1].id);
    }
  };

  const handleDeleteSelected = () => {
    const blocksToDelete = deleteSelected();
    console.log('Deleting blocks:', blocksToDelete); // Debug log
    blocksToDelete.forEach(blockId => {
      console.log('Deleting block:', blockId); // Debug log
      onDeleteBlock(blockId);
    });
    clearSelection();
  };

  const handleMoveBlock = (blockId: string, direction: 'up' | 'down') => {
    const currentIndex = page.blocks.findIndex(b => b.id === blockId);
    if (currentIndex === -1) return;
    
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    
    if (newIndex >= 0 && newIndex < page.blocks.length) {
      onMoveBlock(blockId, newIndex);
    }
  };

  const handleBlockDragStart = (blockId: string) => {
    return (e: React.DragEvent) => {
      handleDragStart(blockId, e);
    };
  };

  const handleBlockDrop = (targetBlockId: string) => {
    return (e: React.DragEvent) => {
      const result = handleDrop(targetBlockId, e);
      if (result) {
        const { draggedBlockId, targetBlockId: target } = result;
        const draggedIndex = page.blocks.findIndex(b => b.id === draggedBlockId);
        const targetIndex = page.blocks.findIndex(b => b.id === target);
        
        if (draggedIndex !== -1 && targetIndex !== -1) {
          onMoveBlock(draggedBlockId, targetIndex);
        }
      }
    };
  };

  const handleBlockSelect = (blockId: string) => {
    return (e?: React.MouseEvent) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
        handleBlockClick(blockId, e);
      } else {
        selectBlock(blockId);
      }
    };
  };

  const handleBlockMouseDown = (blockId: string) => {
    return (e: React.MouseEvent) => {
      handleMouseDown(blockId, e);
    };
  };

  // Handle keyboard shortcuts for selection
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Backspace' && selectedBlocks.size > 0) {
        e.preventDefault();
        handleDeleteSelected();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedBlocks.size]); // Add dependency to ensure latest selectedBlocks

  // Prevent text selection globally during drag operations
  useEffect(() => {
    if (isDragSelecting || isGlobalDragSelecting) {
      document.body.style.userSelect = 'none';
      (document.body.style as any).webkitUserSelect = 'none';
      (document.body.style as any).MozUserSelect = 'none';
      document.body.classList.add('prevent-selection');
    } else {
      document.body.style.userSelect = '';
      (document.body.style as any).webkitUserSelect = '';
      (document.body.style as any).MozUserSelect = '';
      document.body.classList.remove('prevent-selection');
    }

    return () => {
      // Cleanup on unmount
      document.body.style.userSelect = '';
      (document.body.style as any).webkitUserSelect = '';
      (document.body.style as any).MozUserSelect = '';
      document.body.classList.remove('prevent-selection');
    };
  }, [isDragSelecting, isGlobalDragSelecting]);

  // Close emoji picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showEmojiPicker) {
        const target = e.target as HTMLElement;
        if (!target.closest('.emoji-picker-container')) {
          setShowEmojiPicker(false);
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showEmojiPicker]);

  return (
    <div 
      className="flex-1 overflow-y-auto relative"
      tabIndex={0}
      style={{ 
        userSelect: isDragSelecting || isGlobalDragSelecting ? 'none' : 'auto',
        WebkitUserSelect: isDragSelecting || isGlobalDragSelecting ? 'none' : 'auto',
        MozUserSelect: isDragSelecting || isGlobalDragSelecting ? 'none' : 'auto',
      }}
      onMouseDown={handleGlobalMouseDown}
      onMouseMove={handleGlobalMouseMove}
      onMouseUp={handleGlobalMouseUp}
    >
      {/* Global selection rectangle */}
      {dragSelection && (
        <div
          style={getSelectionRectStyle()}
        />
      )}
      
      <div className="max-w-4xl mx-auto p-8 relative">
        {/* Page Title - only show if first block is not H1 */}
        {!isFirstBlockH1 && (
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="relative">
                <button 
                  onClick={handleEmojiClick}
                  className="text-6xl hover:bg-gray-100 rounded-lg p-2 transition-colors"
                  title="Change icon"
                >
                  {page.icon || '📄'}
                </button>
                {showEmojiPicker && (
                  <div className="emoji-picker-container absolute top-full left-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-3 grid grid-cols-6 gap-2 z-50 max-w-xs">
                    {emojiOptions.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => handleEmojiSelect(emoji)}
                        className="text-2xl hover:bg-gray-100 rounded p-1 transition-colors"
                        title={emoji}
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex-1">
                <Input
                  value={page.title}
                  onChange={(e) => onUpdatePage({ title: e.target.value })}
                  className="text-4xl font-bold border-none shadow-none px-0 py-2 h-auto bg-transparent font-baskerville"
                  placeholder="Untitled"
                  onFocus={clearSelection}
                />
              </div>
            </div>
          </div>
        )}

        {/* Page Icon for H1 title - above the title like Notion */}
        {isFirstBlockH1 && (
          <div className="mb-4 relative">
            <button 
              onClick={handleEmojiClick}
              className="text-6xl hover:bg-gray-100 rounded-lg p-2 transition-colors"
              title="Change icon"
            >
              {page.icon || '📄'}
            </button>
            {showEmojiPicker && (
              <div className="emoji-picker-container absolute top-full left-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-3 grid grid-cols-6 gap-2 z-50 max-w-xs">
                {emojiOptions.map((emoji) => (
                  <button
                    key={emoji}
                    onClick={() => handleEmojiSelect(emoji)}
                    className="text-2xl hover:bg-gray-100 rounded p-1 transition-colors"
                    title={emoji}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Selection indicator */}
        {selectedBlocks.size > 0 && (
          <div className="mb-4 p-2 bg-blue-50 border border-blue-200 rounded-md flex items-center justify-between text-sm">
            <span>{selectedBlocks.size} block{selectedBlocks.size !== 1 ? 's' : ''} selected</span>
            <div className="flex gap-2">
              <button
                onClick={(e) => {
                  e.preventDefault();
                  handleDeleteSelected();
                }}
                className="text-red-600 hover:text-red-800 px-2 py-1 hover:bg-red-50 rounded"
              >
                Delete
              </button>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  clearSelection();
                }}
                className="text-gray-600 hover:text-gray-800 px-2 py-1 hover:bg-gray-50 rounded"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        {/* Blocks */}
        <div className="space-y-0"> {/* Changed from space-y-1 to space-y-0 for continuous selection */}
          {page.blocks.map((block, index) => {
            const selectionInfo = getSelectionInfo(block.id);
            
            return (
              <div key={block.id} className="block-editor">
                <BlockEditor
                  block={block}
                  isSelected={selectionInfo.isSelected}
                  isFirstSelected={selectionInfo.isFirstSelected}
                  isLastSelected={selectionInfo.isLastSelected}
                  isInSelection={selectionInfo.isInSelection}
                  onUpdate={(updates) => handleBlockUpdate(block.id, updates)}
                  onAddBlock={() => handleAddBlock(block.id)}
                  onDeleteBlock={() => handleDeleteBlock(block.id)}
                  onFocus={() => {
                    setFocusedBlockId(block.id);
                    clearSelection();
                  }}
                  isFocused={focusedBlockId === block.id}
                  onMoveUp={() => handleMoveBlock(block.id, 'up')}
                  onMoveDown={() => handleMoveBlock(block.id, 'down')}
                  onSelect={handleBlockSelect(block.id)}
                  onMouseDown={handleBlockMouseDown(block.id)}
                  onMouseEnter={handleBlockMouseEnterDuringGlobalDrag(block.id)}
                  onMouseUp={handleMouseUp}
                  onDragStart={handleBlockDragStart(block.id)}
                  onDragOver={handleDragOver}
                  onDrop={handleBlockDrop(block.id)}
                />
              </div>
            );
          })}
        </div>

      </div>
    </div>
  );
};
