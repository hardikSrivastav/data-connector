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

  const handleBlockUpdate = (blockId: string, updates: any) => {
    onUpdateBlock(blockId, updates);
  };

  const handleAddBlock = (afterBlockId?: string) => {
    const newBlockId = onAddBlock(afterBlockId);
    setFocusedBlockId(newBlockId);
    clearSelection(); // Clear selection when adding new block
  };

  const handleDeleteBlock = (blockId: string) => {
    const blockIndex = page.blocks.findIndex(b => b.id === blockId);
    onDeleteBlock(blockId);
    
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

  const handleBlockMouseEnter = (blockId: string) => {
    return (e: React.MouseEvent) => {
      handleMouseEnter(blockId, e);
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

  return (
    <div 
      className="flex-1 overflow-y-auto"
      tabIndex={0}
      style={{ userSelect: isDragSelecting ? 'none' : 'auto' }}
    >
      <div className="max-w-4xl mx-auto p-8">
        {/* Page Title */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-6xl">{page.icon || '📄'}</span>
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
              <BlockEditor
                key={block.id}
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
                onMouseEnter={handleBlockMouseEnter(block.id)}
                onMouseUp={handleMouseUp}
                onDragStart={handleBlockDragStart(block.id)}
                onDragOver={handleDragOver}
                onDrop={handleBlockDrop(block.id)}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};
