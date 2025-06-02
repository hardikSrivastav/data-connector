import { useState, useCallback, useEffect } from 'react';
import { Block } from '@/types';

export interface SelectionState {
  selectedBlocks: Set<string>;
  isDragging: boolean;
  dragStartId: string | null;
  // Drag selection state
  isDragSelecting: boolean;
  dragSelectStart: string | null;
  dragSelectCurrent: string | null;
}

export const useBlockSelection = (blocks: Block[]) => {
  const [selectionState, setSelectionState] = useState<SelectionState>({
    selectedBlocks: new Set(),
    isDragging: false,
    dragStartId: null,
    isDragSelecting: false,
    dragSelectStart: null,
    dragSelectCurrent: null,
  });

  const selectBlock = useCallback((blockId: string, isMultiSelect = false) => {
    console.log('🎯 selectBlock called:', { blockId, isMultiSelect });
    console.log('🎯 Current selection before selectBlock:', Array.from(selectionState.selectedBlocks));
    
    setSelectionState(prev => {
      const newSelected = new Set(isMultiSelect ? prev.selectedBlocks : []);
      
      if (isMultiSelect && prev.selectedBlocks.has(blockId)) {
        console.log('🎯 Removing block from selection (was already selected)');
        newSelected.delete(blockId);
      } else {
        console.log('🎯 Adding block to selection');
        newSelected.add(blockId);
      }
      
      console.log('🎯 New selection after selectBlock:', Array.from(newSelected));
      
      return {
        ...prev,
        selectedBlocks: newSelected,
      };
    });
  }, []);

  const selectRange = useCallback((startId: string, endId: string) => {
    const startIndex = blocks.findIndex(b => b.id === startId);
    const endIndex = blocks.findIndex(b => b.id === endId);
    
    if (startIndex === -1 || endIndex === -1) return;
    
    const [start, end] = startIndex < endIndex ? [startIndex, endIndex] : [endIndex, startIndex];
    const newSelected = new Set<string>();
    
    for (let i = start; i <= end; i++) {
      newSelected.add(blocks[i].id);
    }
    
    setSelectionState(prev => ({
      ...prev,
      selectedBlocks: newSelected,
    }));
  }, [blocks]);

  const clearSelection = useCallback(() => {
    console.log('🚨 clearSelection called');
    console.log('🚨 Selection before clear:', Array.from(selectionState.selectedBlocks));
    console.trace('🚨 clearSelection call stack');
    
    setSelectionState(prev => ({
      ...prev,
      selectedBlocks: new Set(),
      isDragSelecting: false,
      dragSelectStart: null,
      dragSelectCurrent: null,
    }));
  }, []);

  const selectAll = useCallback(() => {
    const allIds = new Set(blocks.map(b => b.id));
    setSelectionState(prev => ({
      ...prev,
      selectedBlocks: allIds,
    }));
  }, [blocks]);

  const deleteSelected = useCallback(() => {
    console.log('🚨 deleteSelected called');
    console.log('🚨 Current selection state:', Array.from(selectionState.selectedBlocks));
    const result = Array.from(selectionState.selectedBlocks);
    console.log('🚨 deleteSelected returning:', result);
    return result;
  }, [selectionState.selectedBlocks]);

  const handleBlockClick = useCallback((blockId: string, event: React.MouseEvent) => {
    console.log('🎯 handleBlockClick called:', { blockId });
    console.log('🎯 Event modifiers:', { 
      shiftKey: event.shiftKey, 
      ctrlKey: event.ctrlKey, 
      metaKey: event.metaKey 
    });
    console.log('🎯 Current selection before handleBlockClick:', Array.from(selectionState.selectedBlocks));
    
    const isShiftClick = event.shiftKey;
    const isCtrlClick = event.ctrlKey || event.metaKey;
    
    if (isShiftClick && selectionState.selectedBlocks.size > 0) {
      console.log('🎯 Shift+click detected - doing range selection');
      // Range selection
      const lastSelected = Array.from(selectionState.selectedBlocks).pop();
      if (lastSelected) {
        selectRange(lastSelected, blockId);
      }
    } else if (isCtrlClick) {
      console.log('🎯 Ctrl+click detected - doing multi-select');
      // Multi-select
      selectBlock(blockId, true);
    } else {
      console.log('🎯 Regular click detected - doing single select');
      // Single select
      selectBlock(blockId, false);
    }
  }, [selectBlock, selectRange, selectionState.selectedBlocks]);

  // Drag selection handlers
  const handleMouseDown = useCallback((blockId: string, event: React.MouseEvent) => {
    // Only start drag selection if it's a left click without modifiers
    if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
      setSelectionState(prev => ({
        ...prev,
        isDragSelecting: true,
        dragSelectStart: blockId,
        dragSelectCurrent: blockId,
        selectedBlocks: new Set([blockId]),
      }));
    }
  }, []);

  const handleMouseEnter = useCallback((blockId: string, event: React.MouseEvent) => {
    if (selectionState.isDragSelecting && selectionState.dragSelectStart) {
      selectRange(selectionState.dragSelectStart, blockId);
      setSelectionState(prev => ({
        ...prev,
        dragSelectCurrent: blockId,
      }));
    }
  }, [selectionState.isDragSelecting, selectionState.dragSelectStart, selectRange]);

  const handleMouseUp = useCallback(() => {
    setSelectionState(prev => ({
      ...prev,
      isDragSelecting: false,
    }));
  }, []);

  const handleDragStart = useCallback((blockId: string, event: React.DragEvent) => {
    event.dataTransfer.setData('text/plain', blockId);
    setSelectionState(prev => ({
      ...prev,
      isDragging: true,
      dragStartId: blockId,
    }));
  }, []);

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
  }, []);

  const handleDrop = useCallback((targetBlockId: string, event: React.DragEvent) => {
    event.preventDefault();
    const draggedBlockId = event.dataTransfer.getData('text/plain');
    
    setSelectionState(prev => ({
      ...prev,
      isDragging: false,
      dragStartId: null,
    }));
    
    // Return the drag operation details for the parent component to handle
    return { draggedBlockId, targetBlockId };
  }, []);

  // Get selection boundary info for UI styling
  const getSelectionInfo = useCallback((blockId: string) => {
    const selectedArray = Array.from(selectionState.selectedBlocks);
    const isSelected = selectedArray.includes(blockId);
    
    if (!isSelected) {
      return {
        isSelected: false,
        isFirstSelected: false,
        isLastSelected: false,
        isInSelection: false,
      };
    }

    // Sort selected blocks by their position in the blocks array
    const selectedIndices = selectedArray
      .map(id => blocks.findIndex(b => b.id === id))
      .filter(index => index !== -1)
      .sort((a, b) => a - b);

    const currentIndex = blocks.findIndex(b => b.id === blockId);
    const firstSelectedIndex = selectedIndices[0];
    const lastSelectedIndex = selectedIndices[selectedIndices.length - 1];

    return {
      isSelected: true,
      isFirstSelected: currentIndex === firstSelectedIndex,
      isLastSelected: currentIndex === lastSelectedIndex,
      isInSelection: currentIndex >= firstSelectedIndex && currentIndex <= lastSelectedIndex,
    };
  }, [blocks, selectionState.selectedBlocks]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey) {
        switch (event.key) {
          case 'a':
            event.preventDefault();
            selectAll();
            break;
          case 'Escape':
            clearSelection();
            break;
        }
      } else if (event.key === 'Escape') {
        clearSelection();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectAll, clearSelection]);

  // Global mouse up handler for drag selection
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (selectionState.isDragSelecting) {
        handleMouseUp();
      }
    };

    document.addEventListener('mouseup', handleGlobalMouseUp);
    return () => document.removeEventListener('mouseup', handleGlobalMouseUp);
  }, [selectionState.isDragSelecting, handleMouseUp]);

  return {
    selectedBlocks: selectionState.selectedBlocks,
    isDragging: selectionState.isDragging,
    isDragSelecting: selectionState.isDragSelecting,
    selectBlock,
    selectRange,
    clearSelection,
    selectAll,
    deleteSelected,
    handleBlockClick,
    handleMouseDown,
    handleMouseEnter,
    handleMouseUp,
    handleDragStart,
    handleDragOver,
    handleDrop,
    getSelectionInfo,
  };
}; 