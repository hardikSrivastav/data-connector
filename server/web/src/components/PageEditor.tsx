import { useState, useEffect, useRef } from 'react';
import { Page, Workspace } from '@/types';
import { BlockEditor } from './BlockEditor';
import { EmojiPicker } from './EmojiPicker';
import { BottomStatusBar } from './BottomStatusBar';
import { Button } from '@/components/ui/button';
import { useBlockSelection } from '@/hooks/useBlockSelection';
import { agentClient, AgentQueryResponse } from '@/lib/agent-client';

interface PageEditorProps {
  page: Page;
  onUpdateBlock: (blockId: string, updates: any) => void;
  onAddBlock: (afterBlockId?: string) => string;
  onDeleteBlock: (blockId: string) => void;
  onUpdatePage: (updates: Partial<Page>) => void;
  onMoveBlock: (blockId: string, newIndex: number) => void;
  showAgentPanel: boolean;
  onToggleAgentPanel: (show: boolean) => void;
  workspace: Workspace;
}

export const PageEditor = ({
  page,
  onUpdateBlock,
  onAddBlock,
  onDeleteBlock,
  onUpdatePage,
  onMoveBlock,
  showAgentPanel,
  onToggleAgentPanel,
  workspace
}: PageEditorProps) => {
  const [focusedBlockId, setFocusedBlockId] = useState<string | null>(null);
  const [isGlobalDragSelecting, setIsGlobalDragSelecting] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [dragSelection, setDragSelection] = useState<{
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
  } | null>(null);
  const [pendingAIUpdate, setPendingAIUpdate] = useState<{ 
    blockId: string; 
    content?: string;
    canvasData?: any;
  } | null>(null);
  const addingBlockRef = useRef(false); // Track if we're currently adding a block to prevent loops
  
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

  // AI Query handler - Updated to use real agent API and create Canvas blocks
  const handleAIQuery = async (query: string, blockId: string) => {
    console.log(`🎯 PageEditor: handleAIQuery called`);
    console.log(`📝 PageEditor: Query='${query}', BlockId='${blockId}'`);
    
    try {
      console.log(`🔄 PageEditor: Calling agentClient.query...`);
      
      // Call the real agent API
      const response: AgentQueryResponse = await agentClient.query({
        question: query,
        analyze: true // Request analysis for richer responses
      });
      
      console.log(`✅ PageEditor: Agent response received!`);
      console.log(`📊 PageEditor: Response structure:`, {
        rows_count: response.rows?.length || 0,
        sql_length: response.sql?.length || 0,
        has_analysis: !!response.analysis
      });
      
      // Create canvas preview data from the AI response
      const canvasData = createCanvasPreviewFromResponse(response, query);
      
      // Add the AI response as a new Canvas block after the current block
      console.log(`➕ PageEditor: Adding new Canvas block after blockId='${blockId}'`);
      const newBlockId = onAddBlock(blockId);
      console.log(`➕ PageEditor: New Canvas block created with id='${newBlockId}'`);
      
      // Store the canvas data to update when the block appears in state
      console.log(`💾 PageEditor: Storing Canvas data for delayed update`);
      console.log(`💾 PageEditor: Canvas data structure being stored:`, canvasData);
      setPendingAIUpdate({ 
        blockId: newBlockId, 
        canvasData: {
          threadId: `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          threadName: generateThreadName(query),
          isExpanded: false,
          workspaceId: workspace.id,
          pageId: page.id,
          blockId: newBlockId,
          // Explicitly spread the canvas data to ensure all properties are preserved
          fullAnalysis: canvasData.fullAnalysis,
          fullData: canvasData.fullData,
          sqlQuery: canvasData.sqlQuery,
          preview: canvasData.preview,
          blocks: [] // Initialize empty blocks array
        }
      });
      
    } catch (error) {
      console.error('❌ PageEditor: AI Query failed:', error);
      console.error('❌ PageEditor: Error details:', {
        query,
        blockId,
        error: error.message,
        stack: error.stack
      });
      
      // Add error message as a regular text block
      console.log(`⚠️ PageEditor: Adding error block after blockId='${blockId}'`);
      const newBlockId = onAddBlock(blockId);
      const errorMessage = `❌ **Error:** ${error.message || 'Failed to get AI response. Please check that the agent server is running.'}`;
      console.log(`⚠️ PageEditor: Storing error message for delayed update`);
      setPendingAIUpdate({ blockId: newBlockId, content: errorMessage });
    }
  };

  // Generate a smart thread name from the query
  const generateThreadName = (query: string): string => {
    // Clean up the query for a thread name
    const cleaned = query
      .replace(/[^\w\s-]/g, '') // Remove special chars except dashes
      .replace(/\s+/g, ' ')     // Normalize whitespace
      .trim()
      .split(' ')
      .slice(0, 4)              // Take first 4 words
      .join(' ');
    
    // Capitalize first letter
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1) || 'Data Analysis';
  };

  // Create canvas preview data from AI response
  const createCanvasPreviewFromResponse = (response: AgentQueryResponse, query: string) => {
    console.log('🎯 Creating canvas data from response:', response);
    
    const canvasData: any = {};
    
    // Store full analysis text
    if (response.analysis) {
      canvasData.fullAnalysis = response.analysis;
      console.log('✅ Added fullAnalysis, length:', response.analysis.length);
    } else {
      console.log('❌ No analysis in response');
    }
    
    // Store SQL query
    if (response.sql) {
      canvasData.sqlQuery = response.sql;
      console.log('✅ Added sqlQuery, length:', response.sql.length);
    } else {
      console.log('❌ No SQL in response');
    }
    
    // Store full data
    if (response.rows && response.rows.length > 0) {
      const headers = Object.keys(response.rows[0]);
      const rows = response.rows.map(row => 
        headers.map(header => {
          const value = row[header];
          if (value === null || value === undefined) return '';
          return String(value);
        })
      );
      
      canvasData.fullData = {
        headers,
        rows,
        totalRows: response.rows.length
      };
      console.log('✅ Added fullData:', { headers: headers.length, rows: rows.length, totalRows: response.rows.length });
    } else {
      console.log('❌ No rows in response');
    }
    
    // Create preview data for collapsed view
    const preview: any = {};
    
    // Create summary from analysis or a default based on query results
    if (response.analysis) {
      preview.summary = response.analysis.length > 200 
        ? response.analysis.substring(0, 197) + '...' 
        : response.analysis;
    } else if (response.rows && response.rows.length > 0) {
      preview.summary = `Query executed successfully and returned ${response.rows.length} rows of data. Click to expand and explore the results.`;
    } else {
      preview.summary = `Query executed but returned no data. The SQL query was processed successfully.`;
    }
    
    // Create stats
    const stats = [];
    
    if (response.rows) {
      stats.push({ label: 'Rows', value: response.rows.length.toLocaleString() });
      
      if (response.rows.length > 0) {
        const columns = Object.keys(response.rows[0]);
        stats.push({ label: 'Columns', value: columns.length });
        
        // Try to find numeric columns for additional stats
        const numericColumns = columns.filter(col => {
          const value = response.rows[0][col];
          return typeof value === 'number' || !isNaN(Number(value));
        });
        
        if (numericColumns.length > 0) {
          stats.push({ label: 'Numeric Fields', value: numericColumns.length });
        }
      }
    }
    
    if (response.sql) {
      stats.push({ label: 'SQL Lines', value: response.sql.split('\n').length });
    }
    
    if (stats.length > 0) {
      preview.stats = stats;
    }
    
    // Create table preview (limited rows for collapsed view)
    if (response.rows && response.rows.length > 0) {
      const headers = Object.keys(response.rows[0]);
      const rows = response.rows.slice(0, 5).map(row => 
        headers.map(header => {
          const value = row[header];
          if (value === null || value === undefined) return '';
          return String(value);
        })
      );
      
      preview.tablePreview = {
        headers,
        rows,
        totalRows: response.rows.length
      };
    }
    
    // Add placeholder charts if we have numeric data
    if (response.rows && response.rows.length > 0) {
      const headers = Object.keys(response.rows[0]);
      const numericColumns = headers.filter(col => {
        const value = response.rows[0][col];
        return typeof value === 'number' || (!isNaN(Number(value)) && value !== '');
      });
      
      if (numericColumns.length >= 1) {
        const charts = [];
        
        // Always add a trend chart for time series data
        charts.push({ type: 'line', data: {} });
        
        // Add a distribution chart if we have categorical data
        const categoricalColumns = headers.filter(col => !numericColumns.includes(col));
        if (categoricalColumns.length > 0) {
          charts.push({ type: 'pie', data: {} });
        }
        
        preview.charts = charts;
      }
    }
    
    canvasData.preview = preview;
    console.log('🎯 Final canvas data structure:', {
      keys: Object.keys(canvasData),
      hasFullAnalysis: !!canvasData.fullAnalysis,
      hasFullData: !!canvasData.fullData,
      hasSqlQuery: !!canvasData.sqlQuery,
      hasPreview: !!canvasData.preview,
      previewKeys: canvasData.preview ? Object.keys(canvasData.preview) : []
    });
    return canvasData;
  };

  // Global drag selection handlers
  const handleGlobalMouseDown = (e: React.MouseEvent) => {
    // Don't start drag selection if clicking on emoji picker area
    const target = e.target as HTMLElement;
    
    // Don't start drag selection if clicking on interactive elements or emoji picker
    if (
      target.tagName === 'BUTTON' ||
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.closest('.block-editor') ||
      target.closest('.emoji-picker-container')
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

      const newDragSelection = {
        ...dragSelection,
        currentX,
        currentY,
      };

      setDragSelection(newDragSelection);

      // Calculate which blocks intersect with the selection rectangle
      updateBlockSelectionFromRect(newDragSelection, container);
    }
  };

  // Function to update block selection based on rectangle intersection
  const updateBlockSelectionFromRect = (dragRect: typeof dragSelection, container: HTMLElement) => {
    if (!dragRect) return;

    // Calculate selection rectangle bounds
    const selectionLeft = Math.min(dragRect.startX, dragRect.currentX);
    const selectionTop = Math.min(dragRect.startY, dragRect.currentY);
    const selectionRight = Math.max(dragRect.startX, dragRect.currentX);
    const selectionBottom = Math.max(dragRect.startY, dragRect.currentY);

    // Clear current selection first
    clearSelection();

    // Find all block elements and check for intersection
    const blockElements = container.querySelectorAll('.block-editor');
    const containerRect = container.getBoundingClientRect();

    blockElements.forEach((blockElement) => {
      const blockRect = blockElement.getBoundingClientRect();
      
      // Convert block position to container-relative coordinates
      const blockLeft = blockRect.left - containerRect.left;
      const blockTop = blockRect.top - containerRect.top;
      const blockRight = blockLeft + blockRect.width;
      const blockBottom = blockTop + blockRect.height;

      // Check if block intersects with selection rectangle
      const intersects = !(
        blockRight < selectionLeft ||
        blockLeft > selectionRight ||
        blockBottom < selectionTop ||
        blockTop > selectionBottom
      );

      if (intersects) {
        // Get block ID from the element
        const blockId = blockElement.querySelector('[data-block-id]')?.getAttribute('data-block-id');
        if (blockId) {
          selectBlock(blockId, true);
        }
      }
    });
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
      // During global drag selection, we use geometric intersection detection
      // so we don't need to handle selection here anymore
      if (!isGlobalDragSelecting) {
        handleMouseEnter(blockId, e);
      }
    };
  };

  const handleBlockUpdate = (blockId: string, updates: any) => {
    console.log(`🔧 PageEditor: handleBlockUpdate called with blockId='${blockId}'`);
    console.log(`🔧 PageEditor: Update data:`, {
      blockId,
      updates,
      current_block_exists: !!page.blocks.find(b => b.id === blockId),
      total_blocks: page.blocks.length
    });
    
    try {
      onUpdateBlock(blockId, updates);
      console.log(`✅ PageEditor: onUpdateBlock call successful for blockId='${blockId}'`);
    } catch (error) {
      console.error(`❌ PageEditor: Error in handleBlockUpdate:`, error);
    }
  };

  const handleAddBlock = (afterBlockId?: string) => {
    const newBlockId = onAddBlock(afterBlockId);
    setFocusedBlockId(newBlockId);
    clearSelection(); // Clear selection when adding new block
    return newBlockId; // Return the new block ID
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
    console.log('handleDeleteSelected called');
    console.log('Currently selected blocks:', Array.from(selectedBlocks));
    console.log('Blocks to delete from deleteSelected():', blocksToDelete);
    console.log('Page blocks before deletion:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) + '...' })));
    
    if (blocksToDelete.length === 0) {
      console.warn('No blocks to delete!');
      return;
    }
    
    // Delete blocks in reverse order to avoid index issues
    const sortedBlocksToDelete = blocksToDelete.sort((a, b) => {
      const indexA = page.blocks.findIndex(block => block.id === a);
      const indexB = page.blocks.findIndex(block => block.id === b);
      return indexB - indexA; // Reverse order
    });
    
    console.log('Deleting blocks in order:', sortedBlocksToDelete);
    
    sortedBlocksToDelete.forEach((blockId, index) => {
      console.log(`Deleting block ${index + 1}/${sortedBlocksToDelete.length}:`, blockId);
      onDeleteBlock(blockId);
    });
    
    clearSelection();
    console.log('Deletion complete, selection cleared');
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
        console.log('Keyboard shortcut triggered - Cmd+Backspace');
        console.log('Selected blocks at time of deletion:', Array.from(selectedBlocks));
        console.log('Selected blocks size:', selectedBlocks.size);
        handleDeleteSelected();
      }
      if (e.key === 'Escape' && showEmojiPicker) {
        setShowEmojiPicker(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedBlocks, showEmojiPicker, handleDeleteSelected]); // Include selectedBlocks directly instead of just size

  // Close emoji picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.emoji-picker-container') && showEmojiPicker) {
        setShowEmojiPicker(false);
      }
    };

    if (showEmojiPicker) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showEmojiPicker]);

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

  const handleEmojiSelect = (emoji: string) => {
    onUpdatePage({ icon: emoji });
    setShowEmojiPicker(false);
  };

  const handleRemoveEmoji = () => {
    onUpdatePage({ icon: undefined });
    setShowEmojiPicker(false);
  };

  // Handle pending AI update
  useEffect(() => {
    if (pendingAIUpdate) {
      const { blockId, content, canvasData } = pendingAIUpdate;
      console.log(`🎯 PageEditor: Checking pending AI update for blockId='${blockId}'`);
      
      // Check if the block now exists in the page state
      const blockExists = page.blocks.some(block => block.id === blockId);
      console.log(`🎯 PageEditor: Block exists in current page state: ${blockExists}`);
      console.log(`🎯 PageEditor: Current page blocks:`, page.blocks.map(b => ({ id: b.id, content_length: b.content?.length || 0 })));
      
      if (blockExists) {
        if (canvasData) {
          // Create Canvas block with preview data
          console.log(`🎯 PageEditor: Executing pending Canvas update for blockId='${blockId}'`);
          console.log(`🎯 PageEditor: Canvas thread name:`, canvasData.threadName);
          console.log(`🎯 PageEditor: Canvas data being saved:`, {
            keys: Object.keys(canvasData),
            hasFullAnalysis: !!canvasData.fullAnalysis,
            hasFullData: !!canvasData.fullData,
            hasSqlQuery: !!canvasData.sqlQuery,
            hasPreview: !!canvasData.preview,
            fullAnalysisLength: canvasData.fullAnalysis?.length || 0,
            fullDataRows: canvasData.fullData?.rows?.length || 0
          });
          
          onUpdateBlock(blockId, {
            content: canvasData.threadName,
            type: 'canvas',
            properties: {
              canvasData: canvasData
            }
          });
          
          console.log(`✅ PageEditor: Pending Canvas update completed for blockId='${blockId}'`);
        } else if (content) {
          // Create regular content block (for errors)
          console.log(`🎯 PageEditor: Executing pending content update for blockId='${blockId}'`);
        console.log(`🎯 PageEditor: Content preview:`, content.substring(0, 100) + '...');
        
        onUpdateBlock(blockId, {
          content: content,
            type: 'quote' // Style error messages as quotes
        });
        
          console.log(`✅ PageEditor: Pending content update completed for blockId='${blockId}'`);
        }
        
        setPendingAIUpdate(null);
      } else {
        console.log(`⏳ PageEditor: Block not yet available in page state, will retry on next render`);
      }
    }
  }, [pendingAIUpdate, page.blocks, onUpdateBlock]);

  // Handle page navigation for subpage blocks
  const handleNavigateToPage = (pageId: string) => {
    const targetPage = workspace.pages.find(p => p.id === pageId);
    if (targetPage) {
      // For now, we'll just log the navigation. In a real app, this would change the current page
      console.log(`Navigating to page: ${targetPage.title} (${pageId})`);
      // You could implement actual navigation here:
      // onPageChange?.(pageId);
      alert(`Would navigate to: ${targetPage.title}`);
    }
  };

  // Handle clicks in empty space to create new blocks
  const handleEmptySpaceClick = (e: React.MouseEvent) => {
    // Check if the click was on empty space (not on a block or interactive element)
    const target = e.target as HTMLElement;
    
    // Don't create block if:
    // - Clicking on a button, input, or other interactive element
    // - Clicking inside a block editor
    // - Currently dragging/selecting
    // - Emoji picker is open
    if (
      target.closest('.block-editor') || 
      target.closest('button') || 
      target.closest('input') || 
      target.closest('textarea') || 
      target.closest('.emoji-picker-container') ||
      target.closest('[role="button"]') ||
      isDragSelecting || 
      isGlobalDragSelecting ||
      showEmojiPicker ||
      selectedBlocks.size > 0 // Don't interfere with selection
    ) {
      return;
    }

    // Only create block if clicking in the main content area
    if (target.closest('.page-content-area')) {
      e.preventDefault();
      e.stopPropagation();
      
      // Clear any existing selections
      clearSelection();
      
      // Check if there's already an empty block at the end
      const lastBlock = page.blocks.length > 0 ? page.blocks[page.blocks.length - 1] : null;
      const isLastBlockEmpty = lastBlock && (!lastBlock.content || lastBlock.content.trim() === '');
      const isLastBlockFocused = lastBlock && focusedBlockId === lastBlock.id;
      
      if (isLastBlockEmpty && !isLastBlockFocused) {
        // Focus the existing empty block instead of creating a new one
        setFocusedBlockId(lastBlock.id);
      } else if (!isLastBlockEmpty) {
        // Only create a new block if the last block has content
        const lastBlockId = lastBlock ? lastBlock.id : undefined;
        const newBlockId = handleAddBlock(lastBlockId);
        
        // Focus the new block immediately so user can start typing
        setTimeout(() => {
          setFocusedBlockId(newBlockId);
        }, 50);
      }
      // If the last block is empty AND focused, do nothing (user is already typing)
    }
  };

  // Automatically ensure there's always an empty text block after non-text blocks
  useEffect(() => {
    // Prevent infinite loops by checking if we're already adding a block
    if (addingBlockRef.current) {
      return;
    }

    const nonTextBlockTypes = ['table', 'divider', 'toggle', 'subpage', 'canvas'];
    let needsUpdate = false;
    let actionNeeded: 'initial' | 'after-nontext' | null = null;
    let targetBlockId: string | null = null;
    
    // Check if page is empty and needs an initial block
    if (page.blocks.length === 0) {
      needsUpdate = true;
      actionNeeded = 'initial';
    } else {
      // Check if we need to add blocks after non-text blocks
      for (let i = 0; i < page.blocks.length; i++) {
        const currentBlock = page.blocks[i];
        const nextBlock = page.blocks[i + 1];
        
        // If current block is non-text and either:
        // - It's the last block, OR
        // - The next block is also non-text
        // Then we need to add an empty text block after it
        if (nonTextBlockTypes.includes(currentBlock.type)) {
          if (!nextBlock || nonTextBlockTypes.includes(nextBlock.type)) {
            needsUpdate = true;
            actionNeeded = 'after-nontext';
            targetBlockId = currentBlock.id;
            break; // Only handle one at a time
          }
        }
      }
    }
    
    if (needsUpdate && actionNeeded) {
      addingBlockRef.current = true; // Set flag to prevent loops
      
      if (actionNeeded === 'initial') {
        // For initial block, we'll manually add it and focus it
        const newBlockId = onAddBlock();
        setFocusedBlockId(newBlockId);
        setTimeout(() => {
          addingBlockRef.current = false;
        }, 100);
      } else if (actionNeeded === 'after-nontext' && targetBlockId) {
        // For blocks after non-text blocks, don't auto-focus
        onAddBlock(targetBlockId);
        setTimeout(() => {
          addingBlockRef.current = false;
        }, 100);
      }
    }
  }, [page.blocks, onAddBlock]); // Depend on onAddBlock directly

  // Generate breadcrumbs from workspace and page data
  const breadcrumbs = [
    { label: 'Workspace', onClick: () => console.log('Navigate to workspace') },
    { label: workspace.name || 'My Workspace' },
    { label: page.title || 'Untitled Page' }
  ];

  return (
    <div className="flex-1 flex flex-col relative">
      {/* Main content area */}
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
        onClick={handleEmptySpaceClick}
      >
        {/* Global selection rectangle */}
        {dragSelection && (
          <div
            style={getSelectionRectStyle()}
          />
        )}
        
        <div className="max-w-4xl mx-auto p-8 pb-20 relative page-content-area min-h-screen"> {/* Added min-h-screen to ensure clickable space */}
          {/* Page Header with Emoji */}
          <div className="mb-6 relative">
            <div className="flex items-center gap-2 mb-4">
              <div className="relative emoji-picker-container">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-12 w-12 p-0 text-4xl hover:bg-gray-100 rounded-md transition-colors"
                  onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                >
                  {page.icon || '📄'}
                </Button>
                
                {showEmojiPicker && (
                  <div className="relative">
                    <EmojiPicker
                      currentEmoji={page.icon}
                      onEmojiSelect={handleEmojiSelect}
                      onClose={() => setShowEmojiPicker(false)}
                    />
                    {page.icon && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute top-full left-0 mt-1 text-xs text-gray-500 hover:text-gray-700"
                        onClick={handleRemoveEmoji}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Selection indicator - Fixed position to not disrupt layout */}
          {selectedBlocks.size > 0 && (
            <div className="fixed top-4 right-4 z-50 p-3 bg-white border border-blue-200 rounded-lg shadow-lg text-sm max-w-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-blue-900">
                  {selectedBlocks.size} block{selectedBlocks.size !== 1 ? 's' : ''} selected
                </span>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    clearSelection();
                  }}
                  className="text-gray-400 hover:text-gray-600 ml-2"
                  title="Clear selection"
                >
                  ✕
                </button>
              </div>
              {selectedBlocks.size === 1 && (
                <div className="text-xs text-gray-600 mb-2">
                  Hold Ctrl/Cmd and click more blocks to select multiple
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    console.log('Delete button clicked, selected blocks:', Array.from(selectedBlocks));
                    handleDeleteSelected();
                  }}
                  className="flex-1 px-3 py-1 bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition-colors text-xs"
                >
                  Delete
                </button>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    clearSelection();
                  }}
                  className="flex-1 px-3 py-1 bg-gray-50 text-gray-700 border border-gray-200 rounded hover:bg-gray-100 transition-colors text-xs"
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
                    onAIQuery={handleAIQuery}
                    workspace={workspace}
                    page={page}
                    onNavigateToPage={handleNavigateToPage}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom Status Bar - positioned relative to PageEditor */}
      <BottomStatusBar
        showAgentPanel={showAgentPanel}
        onToggleAgentPanel={onToggleAgentPanel}
        breadcrumbs={breadcrumbs}
      />
    </div>
  );
};
