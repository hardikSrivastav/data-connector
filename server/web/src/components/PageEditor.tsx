import { useState, useEffect, useRef, useCallback } from 'react';
import { flushSync } from 'react-dom';
import { Page, Workspace, Block } from '@/types';
import { BlockEditor } from './BlockEditor';
import { EmojiPicker } from './EmojiPicker';
import { BottomStatusBar } from './BottomStatusBar';
import { Button } from '@/components/ui/button';
import { useBlockSelection } from '@/hooks/useBlockSelection';
import { agentClient, AgentQueryResponse, StreamingCallbacks } from '@/lib/agent-client';
import { StreamingStatusBlock } from './StreamingStatusBlock';
import { useStorageManager } from '@/hooks/useStorageManager';

interface PageEditorProps {
  page: Page;
  onUpdateBlock: (blockId: string, updates: any) => void;
  onAddBlock: (afterBlockId?: string, type?: Block['type']) => string;
  onDeleteBlock: (blockId: string) => void;
  onUpdatePage: (updates: Partial<Page>) => void;
  onMoveBlock: (blockId: string, newIndex: number) => void;
  showAgentPanel: boolean;
  onToggleAgentPanel: (show: boolean) => void;
  workspace: Workspace;
  onNavigateToPage?: (pageId: string) => void;
  onCreateCanvasPage?: (canvasData: any) => Promise<string>;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
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
  workspace,
  onNavigateToPage,
  onCreateCanvasPage,
  sidebarCollapsed,
  onToggleSidebar
}: PageEditorProps) => {
  const { storageManager } = useStorageManager({
    edition: 'enterprise',
    apiBaseUrl: import.meta.env.VITE_API_BASE || 'http://localhost:8787'
  });
  const [focusedBlockId, setFocusedBlockId] = useState<string | null>(null);
  const [isGlobalDragSelecting, setIsGlobalDragSelecting] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isProcessingKeyboardShortcut, setIsProcessingKeyboardShortcut] = useState(false);
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
    streamingProps?: {
      isStreaming: boolean;
      query: string;
      status: string;
      progress: number;
    };
  } | null>(null);
  const [streamingState, setStreamingState] = useState<{
    isStreaming: boolean;
    status: string;
    progress: number;
    blockId?: string;
    query?: string;
  }>({
    isStreaming: false,
    status: '',
    progress: 0
  });
  const [diffModeBlockId, setDiffModeBlockId] = useState<string | null>(null); // Track which block is in diff mode
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

  // Add logging wrapper for onUpdatePage
  const loggedOnUpdatePage = useCallback((updates: Partial<Page>) => {
    console.log('🔧 loggedOnUpdatePage called with:', updates);
    console.log('🔧 updates.blocks length:', updates.blocks?.length);
    console.log('🔧 updates.blocks:', updates.blocks?.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    console.log('🔧 Calling original onUpdatePage...');
    
    try {
      onUpdatePage(updates);
      console.log('🔧 onUpdatePage completed successfully');
    } catch (error) {
      console.error('🔧 Error in onUpdatePage:', error);
    }
  }, [onUpdatePage]);

  const handleDeleteSelected = useCallback(() => {
    console.log('🚨 === STARTING handleDeleteSelected ===');
    console.log('🚨 selectedBlocks at start:', Array.from(selectedBlocks));
    console.log('🚨 selectedBlocks.size:', selectedBlocks.size);
    console.log('🚨 page.blocks at start:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    
    const blocksToDelete = deleteSelected();
    console.log('🚨 deleteSelected() returned:', blocksToDelete);
    console.log('🚨 blocksToDelete.length:', blocksToDelete.length);
    console.log('🚨 Are blocksToDelete in page.blocks?', blocksToDelete.map(id => ({ 
      id, 
      exists: page.blocks.some(b => b.id === id) 
    })));
    
    if (blocksToDelete.length === 0) {
      console.warn('🚨 No blocks to delete! Selection was empty.');
      console.log('🚨 Final selectedBlocks state:', Array.from(selectedBlocks));
      return;
    }
    
    console.log('🚨 === STEP 1: PREPARING UI UPDATE ===');
    
    // Step 1: Update UI immediately
    let updatedBlocks = page.blocks.filter(block => !blocksToDelete.includes(block.id));
    console.log('🚨 Filtered blocks (after removing selected):', updatedBlocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    
    // If no blocks remain, add a default empty text block
    if (updatedBlocks.length === 0) {
      const newBlock = {
        id: `block_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'text' as const,
        content: '',
        order: 0
      };
      updatedBlocks = [newBlock];
      console.log('🚨 No blocks remaining, added default block:', newBlock);
    } else {
      // Reorder remaining blocks to have clean sequential orders
      const originalUpdatedBlocks = [...updatedBlocks];
      updatedBlocks = updatedBlocks.map((block, index) => ({
        ...block,
        order: index
      }));
      console.log('🚨 Reordered blocks:', {
        before: originalUpdatedBlocks.map(b => ({ id: b.id, order: b.order })),
        after: updatedBlocks.map(b => ({ id: b.id, order: b.order }))
      });
    }
    
    console.log('🚨 === STEP 2: UPDATING UI WITH FLUSHSYNC ===');
    console.log('🚨 About to call flushSync with blocks:', updatedBlocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    console.log('🚨 Current page.blocks before flushSync:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    
    // Force immediate UI update using flushSync
    try {
      flushSync(() => {
        console.log('🚨 INSIDE flushSync - calling loggedOnUpdatePage');
        loggedOnUpdatePage({ blocks: updatedBlocks });
        console.log('🚨 INSIDE flushSync - loggedOnUpdatePage called');
      });
      console.log('🚨 flushSync completed successfully');
      console.log('🚨 page.blocks after flushSync:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    } catch (error) {
      console.error('🚨 Error in flushSync:', error);
    }
    
    console.log('🚨 === STEP 3: STORAGE CLEANUP ===');
    
    // Step 2: Clean up storage (without affecting UI since we already updated it)
    console.log('🚨 Starting storage cleanup for blocks:', blocksToDelete);
    blocksToDelete.forEach((blockId, index) => {
      console.log(`🚨 [${index + 1}/${blocksToDelete.length}] Calling onDeleteBlock for: ${blockId}`);
      console.log(`🚨 [${index + 1}/${blocksToDelete.length}] page.blocks before onDeleteBlock:`, page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
      
      try {
        onDeleteBlock(blockId);
        console.log(`🚨 [${index + 1}/${blocksToDelete.length}] onDeleteBlock completed for: ${blockId}`);
        
        // Log state after each deletion
        setTimeout(() => {
          console.log(`🚨 [${index + 1}/${blocksToDelete.length}] page.blocks after onDeleteBlock for ${blockId}:`, page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
        }, 10);
      } catch (error) {
        console.error(`🚨 [${index + 1}/${blocksToDelete.length}] Error in onDeleteBlock for ${blockId}:`, error);
      }
    });
    
    console.log('🚨 === STEP 4: CLEARING SELECTION ===');
    console.log('🚨 selectedBlocks before clearSelection:', Array.from(selectedBlocks));
    clearSelection();
    console.log('🚨 clearSelection called');
    
    // Log final state after a short delay
    setTimeout(() => {
      console.log('🚨 === FINAL STATE (after 100ms) ===');
      console.log('🚨 Final page.blocks:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
      console.log('🚨 Final selectedBlocks:', Array.from(selectedBlocks));
      console.log('🚨 === END handleDeleteSelected ===');
    }, 100);
    
  }, [deleteSelected, selectedBlocks, page.blocks, loggedOnUpdatePage, onDeleteBlock, clearSelection]);

  // AI Query handler - Updated to use streaming API for real-time progress
  const handleAIQuery = async (query: string, blockId: string) => {
    console.log(`🎯 PageEditor: handleAIQuery called`);
    console.log(`📝 PageEditor: Query='${query}', BlockId='${blockId}'`);
    
    // Initialize streaming state
    setStreamingState({
      isStreaming: true,
      status: 'Starting query processing...',
      progress: 0,
      blockId: blockId,
      query: query
    });

    // Create new block immediately for streaming progress
    const newBlockId = onAddBlock(blockId);
    console.log(`➕ PageEditor: New Canvas block created with id='${newBlockId}'`);

    // Set temporary streaming status block  
    setPendingAIUpdate({ 
      blockId: newBlockId, 
      content: query, // Store query in content for StreamingStatusBlock to read
    });

    try {
      console.log(`🌊 PageEditor: Starting streaming query...`);
      
      // Accumulate streaming data
      let accumulatedData: {
        databases?: string[];
        sqlQuery?: string;
        rows?: any[];
        analysis?: string;
        isCrossDatabase?: boolean;
      } = {};
      
      // Call the streaming agent API
      await agentClient.queryStream({
        question: query,
        analyze: true
      }, {
        onStatus: (message) => {
          console.log(`📊 Status: ${message}`);
          setStreamingState(prev => ({
            ...prev,
            status: message,
            progress: Math.min(prev.progress + 0.1, 0.9)
          }));
        },
        
        onClassifying: (message) => {
          console.log(`🔍 Classifying: ${message}`);
          setStreamingState(prev => ({
            ...prev,
            status: `Analyzing query: ${message}`,
            progress: 0.15
          }));
        },
        
        onDatabasesSelected: (databases, reasoning, isCrossDatabase) => {
          console.log(`🎯 Databases selected:`, databases);
          accumulatedData.databases = databases;
          accumulatedData.isCrossDatabase = isCrossDatabase;
          
          setStreamingState(prev => ({
            ...prev,
            status: `Selected databases: ${databases.join(', ')}`,
            progress: 0.25
          }));
        },
        
        onSchemaLoading: (database, progress) => {
          console.log(`📋 Schema loading for ${database}: ${progress}`);
          setStreamingState(prev => ({
            ...prev,
            status: `Loading ${database} schema...`,
            progress: 0.25 + (progress * 0.2) // 25% to 45%
          }));
        },
        
        onQueryGenerating: (database) => {
          console.log(`⚙️ Generating query for ${database}`);
          setStreamingState(prev => ({
            ...prev,
            status: `Generating query for ${database}...`,
            progress: 0.5
          }));
        },
        
        onQueryExecuting: (database, sql) => {
          console.log(`🚀 Executing query on ${database}`);
          if (sql) accumulatedData.sqlQuery = sql;
          
          setStreamingState(prev => ({
            ...prev,
            status: `Executing query on ${database}...`,
            progress: 0.65
          }));
        },
        
        onPartialResults: (database, rowsCount, isComplete) => {
          console.log(`📊 Partial results from ${database}: ${rowsCount} rows`);
          setStreamingState(prev => ({
            ...prev,
            status: `Received ${rowsCount} rows from ${database}`,
            progress: isComplete ? 0.8 : 0.75
          }));
        },
        
        onAnalysisGenerating: (message) => {
          console.log(`🧠 Analysis: ${message}`);
          setStreamingState(prev => ({
            ...prev,
            status: message,
            progress: 0.85
          }));
        },
        
        onPlanning: (step, operationsPlanned) => {
          console.log(`📋 Planning: ${step}`);
          setStreamingState(prev => ({
            ...prev,
            status: `Planning: ${step}`,
            progress: 0.4
          }));
        },
        
        onAggregating: (step, progress) => {
          console.log(`🔗 Aggregating: ${step}`);
          const aggProgress = progress || 0;
          setStreamingState(prev => ({
            ...prev,
            status: `Aggregating data: ${step}`,
            progress: 0.7 + (aggProgress * 0.1)
          }));
        },
        
        onComplete: (results, sessionId) => {
          console.log(`✅ PageEditor: Streaming completed!`);
          console.log(`📊 PageEditor: Final results:`, results);
          
          setStreamingState(prev => ({
            ...prev,
            status: 'Processing complete!',
            progress: 1.0
          }));
          
          // Process final results
          if (results) {
            accumulatedData.rows = results.rows;
            accumulatedData.analysis = results.analysis;
            accumulatedData.sqlQuery = results.sql || accumulatedData.sqlQuery;
          }
          
          // Create canvas data from accumulated streaming data
          const response = {
            rows: accumulatedData.rows || [],
            sql: accumulatedData.sqlQuery || '',
            analysis: accumulatedData.analysis || ''
          };
          
          const canvasData = createCanvasPreviewFromResponse(response, query);
          
          // Update the block with final canvas data
          console.log(`💾 PageEditor: Updating with final Canvas data`);
      setPendingAIUpdate({ 
        blockId: newBlockId, 
        canvasData: {
              threadId: sessionId || `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          threadName: generateThreadName(query),
          isExpanded: false,
          workspaceId: workspace.id,
          pageId: page.id,
          blockId: newBlockId,
          fullAnalysis: canvasData.fullAnalysis,
          fullData: canvasData.fullData,
          sqlQuery: canvasData.sqlQuery,
          preview: canvasData.preview,
              blocks: []
            }
          });
          
          // Clear streaming state
          setTimeout(() => {
            setStreamingState({
              isStreaming: false,
              status: '',
              progress: 0
            });
          }, 1000);
        },
        
        onError: (error, errorCode, recoverable) => {
          console.error('❌ PageEditor: Streaming error:', error);
          setStreamingState(prev => ({
            ...prev,
            status: `Error: ${error}`,
            progress: 0
          }));
          
          // Show error in the block
          const errorMessage = `❌ **Error:** ${error}\n\n${recoverable ? '🔄 You can try again.' : ''}`;
      setPendingAIUpdate({ blockId: newBlockId, content: errorMessage });
          
          // Clear streaming state
          setTimeout(() => {
            setStreamingState({
              isStreaming: false,
              status: '',
              progress: 0
            });
          }, 2000);
        }
      });
      
    } catch (error) {
      console.error('❌ PageEditor: Streaming setup failed:', error);
      
      // Fallback error handling
      const errorMessage = `❌ **Error:** ${error.message || 'Failed to start streaming query. Please check that the agent server is running.'}`;
      setPendingAIUpdate({ blockId: newBlockId, content: errorMessage });
      
      setStreamingState({
        isStreaming: false,
        status: '',
        progress: 0
      });
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
    const canvasData: any = {};
    
    // Store full analysis text
    if (response.analysis) {
      canvasData.fullAnalysis = response.analysis;
    }
    
    // Store SQL query
    if (response.sql) {
      canvasData.sqlQuery = response.sql;
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
    }
    
    // Create preview data for collapsed view
    const preview: any = {};
    
    // Create summary from analysis or a default based on query results
    if (response.analysis) {
      // If the analysis is already markdown or has structured content, use it as-is
      // Otherwise, enhance it with markdown formatting
      let formattedSummary = response.analysis;
      
      // If summary is too long, truncate but preserve markdown structure
      if (formattedSummary.length > 300) {
        formattedSummary = formattedSummary.substring(0, 297) + '...';
      }
      
      preview.summary = formattedSummary;
    } else if (response.rows && response.rows.length > 0) {
      const rowCount = response.rows.length;
      const columnCount = Object.keys(response.rows[0]).length;
      
      preview.summary = `**Query Results Summary**\n\n✅ Query executed successfully\n\n📊 **${rowCount.toLocaleString()}** rows returned across **${columnCount}** columns\n\n*Click to expand and explore the full dataset with interactive charts and analysis.*`;
    } else {
      preview.summary = `**Query Executed**\n\n✅ The SQL query processed successfully but returned no data rows.\n\n*This might indicate the query conditions didn't match any records, or the target dataset is empty.*`;
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
    return canvasData;
  };

  // Global drag selection handlers
  const handleGlobalMouseDown = (e: React.MouseEvent) => {
    // Don't interfere if processing keyboard shortcuts
    if (isProcessingKeyboardShortcut) {
      console.log('🚨 Skipping global mouse down - processing keyboard shortcut');
      return;
    }

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
    
    // Account for scroll position within the container
    const startX = e.clientX - rect.left + container.scrollLeft;
    const startY = e.clientY - rect.top + container.scrollTop;

    // Clear existing selection and start global drag selection
    // But only if we don't have selected blocks (to preserve multi-selection for keyboard shortcuts)
    if (selectedBlocks.size === 0) {
      clearSelection();
    }
    
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
      
      // Account for scroll position within the container
      const currentX = e.clientX - rect.left + container.scrollLeft;
      const currentY = e.clientY - rect.top + container.scrollTop;

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

    // Don't update selection if processing keyboard shortcuts
    if (isProcessingKeyboardShortcut) {
      console.log('🚨 Skipping selection update - processing keyboard shortcut');
      return;
    }

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
      
      // Convert block position to container-relative coordinates, accounting for scroll
      const blockLeft = blockRect.left - containerRect.left + container.scrollLeft;
      const blockTop = blockRect.top - containerRect.top + container.scrollTop;
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
      backgroundColor: 'rgba(59, 130, 246, 0.15)', // Blue with slightly higher opacity since no border
      border: 'none', // Remove border
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

  const handleAddBlock = (afterBlockId?: string, type?: Block['type']) => {
    const newBlockId = onAddBlock(afterBlockId, type);
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
      console.log('🎯 handleBlockSelect called for:', blockId);
      console.log('🎯 Event details:', { 
        ctrlKey: e?.ctrlKey, 
        metaKey: e?.metaKey, 
        shiftKey: e?.shiftKey 
      });
      console.log('🎯 Current selection before click:', Array.from(selectedBlocks));
      
      if (e) {
        e.preventDefault();
        e.stopPropagation();
        handleBlockClick(blockId, e);
      } else {
        selectBlock(blockId);
      }
      
      // Log selection after a small delay to see the result
      setTimeout(() => {
        console.log('🎯 Selection after click:', Array.from(selectedBlocks));
      }, 10);
    };
  };

  const handleBlockMouseDown = (blockId: string) => {
    return (e: React.MouseEvent) => {
      handleMouseDown(blockId, e);
    };
  };

  // New function that takes explicit block list instead of relying on current selection state
  const handleDeleteSelectedWithBlocks = useCallback((blocksToDelete: string[]) => {
    console.log('🚨 === STARTING handleDeleteSelectedWithBlocks ===');
    console.log('🚨 blocksToDelete parameter:', blocksToDelete);
    console.log('🚨 blocksToDelete.length:', blocksToDelete.length);
    console.log('🚨 page.blocks at start:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    console.log('🚨 Are blocksToDelete in page.blocks?', blocksToDelete.map(id => ({ 
      id, 
      exists: page.blocks.some(b => b.id === id) 
    })));
    
    if (blocksToDelete.length === 0) {
      console.warn('🚨 No blocks to delete! blocksToDelete parameter was empty.');
      return;
    }
    
    console.log('🚨 === STEP 1: PREPARING UI UPDATE ===');
    
    // Step 1: Update UI immediately
    let updatedBlocks = page.blocks.filter(block => !blocksToDelete.includes(block.id));
    console.log('🚨 Filtered blocks (after removing selected):', updatedBlocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    
    // If no blocks remain, add a default empty text block
    if (updatedBlocks.length === 0) {
      const newBlock = {
        id: `block_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'text' as const,
        content: '',
        order: 0
      };
      updatedBlocks = [newBlock];
      console.log('🚨 No blocks remaining, added default block:', newBlock);
    } else {
      // Reorder remaining blocks to have clean sequential orders
      const originalUpdatedBlocks = [...updatedBlocks];
      updatedBlocks = updatedBlocks.map((block, index) => ({
        ...block,
        order: index
      }));
      console.log('🚨 Reordered blocks:', {
        before: originalUpdatedBlocks.map(b => ({ id: b.id, order: b.order })),
        after: updatedBlocks.map(b => ({ id: b.id, order: b.order }))
      });
    }
    
    console.log('🚨 === STEP 2: UPDATING UI WITH FLUSHSYNC ===');
    console.log('🚨 About to call flushSync with blocks:', updatedBlocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    console.log('🚨 Current page.blocks before flushSync:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    
    // Force immediate UI update using flushSync
    try {
      flushSync(() => {
        console.log('🚨 INSIDE flushSync - calling loggedOnUpdatePage');
        loggedOnUpdatePage({ blocks: updatedBlocks });
        console.log('🚨 INSIDE flushSync - loggedOnUpdatePage called');
      });
      console.log('🚨 flushSync completed successfully');
      console.log('🚨 page.blocks after flushSync:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
    } catch (error) {
      console.error('🚨 Error in flushSync:', error);
    }
    
    console.log('🚨 === STEP 3: CLEARING SELECTION IMMEDIATELY ===');
    clearSelection();
    console.log('🚨 clearSelection called');
    
    console.log('🚨 === STEP 4: DEFERRED STORAGE CLEANUP ===');
    
    // Step 3: Clean up storage (deferred to avoid interfering with UI)
    console.log('🚨 Scheduling deferred storage cleanup for blocks:', blocksToDelete);
    setTimeout(() => {
      console.log('🚨 Starting deferred storage cleanup for blocks:', blocksToDelete);
      blocksToDelete.forEach((blockId, index) => {
        console.log(`🚨 [DEFERRED ${index + 1}/${blocksToDelete.length}] Calling onDeleteBlock for: ${blockId}`);
        
        try {
          onDeleteBlock(blockId);
          console.log(`🚨 [DEFERRED ${index + 1}/${blocksToDelete.length}] onDeleteBlock completed for: ${blockId}`);
        } catch (error) {
          console.error(`🚨 [DEFERRED ${index + 1}/${blocksToDelete.length}] Error in onDeleteBlock for ${blockId}:`, error);
        }
      });
      
      console.log('🚨 === DEFERRED STORAGE CLEANUP COMPLETED ===');
    }, 50); // Small delay to ensure UI update is processed first
    
    // Log final state after a short delay
    setTimeout(() => {
      console.log('🚨 === FINAL STATE (after 100ms) ===');
      console.log('🚨 Final page.blocks:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
      console.log('🚨 Final selectedBlocks:', Array.from(selectedBlocks));
      console.log('🚨 === END handleDeleteSelectedWithBlocks ===');
    }, 100);
    
  }, [page.blocks, loggedOnUpdatePage, onDeleteBlock, clearSelection, selectedBlocks]);

  // Handle keyboard shortcuts for selection
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Backspace' && selectedBlocks.size > 0) {
        e.preventDefault();
        console.log('🎯 Keyboard shortcut triggered - Cmd+Backspace');
        console.log('🎯 Selected blocks at time of keydown:', Array.from(selectedBlocks));
        console.log('🎯 Selected blocks size at keydown:', selectedBlocks.size);
        
        // IMMEDIATELY capture the current selection before any mouse events can interfere
        const blocksToDeleteNow = Array.from(selectedBlocks);
        console.log('🎯 Captured blocks for deletion:', blocksToDeleteNow);
        
        // Set flag to prevent mouse events from interfering
        setIsProcessingKeyboardShortcut(true);
        
        // Call deletion immediately with captured selection
        console.log('🎯 About to call handleDeleteSelectedWithBlocks with captured blocks...');
        handleDeleteSelectedWithBlocks(blocksToDeleteNow);
        
        // Clear flag after processing
        setTimeout(() => {
          setIsProcessingKeyboardShortcut(false);
        }, 100);
        
        console.log('🎯 handleDeleteSelectedWithBlocks call completed');
      }
      if (e.key === 'Escape' && showEmojiPicker) {
        setShowEmojiPicker(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedBlocks, showEmojiPicker, handleDeleteSelectedWithBlocks]);

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
      onNavigateToPage?.(pageId);
    }
  };

  // Handle clicks in empty space to clear selection or create new blocks
  const handleEmptySpaceClick = (e: React.MouseEvent) => {
    // Don't interfere if processing keyboard shortcuts
    if (isProcessingKeyboardShortcut) {
      console.log('🚨 Skipping empty space click - processing keyboard shortcut');
      return;
    }

    // Check if the click was on empty space (not on a block or interactive element)
    const target = e.target as HTMLElement;
    
    // Don't do anything if:
    // - Clicking on a button, input, or other interactive element
    // - Clicking inside a block editor (but not empty space within it)
    // - Currently dragging/selecting
    // - Emoji picker is open
    if (
      target.closest('button') || 
      target.closest('input') || 
      target.closest('textarea') || 
      target.closest('.emoji-picker-container') ||
      target.closest('[role="button"]') ||
      isDragSelecting || 
      isGlobalDragSelecting ||
      showEmojiPicker
    ) {
      return;
    }

    // If clicking on a block but not on interactive content, just clear selection
    if (target.closest('.block-editor')) {
      // Check if clicking on interactive content within the block
      if (
        target.closest('.canvas-preview') ||
        target.closest('.table-display') ||
        target.closest('[contenteditable]') ||
        target.closest('textarea') ||
        target.closest('input') ||
        target.closest('button')
      ) {
        return; // Don't clear selection if clicking on interactive content
      }
      
      // Clicking on block but not interactive content - just clear selection
      if (selectedBlocks.size > 0) {
        clearSelection();
        setFocusedBlockId(null);
      }
      return;
    }

    // Only create block if clicking in the main content area (empty space)
    if (target.closest('.page-content-area')) {
      e.preventDefault();
      e.stopPropagation();
      
      // Clear any existing selections
      clearSelection();
      setFocusedBlockId(null);
      
      // Only create a new block if there are no selected blocks (i.e., we're not just clearing selection)
      if (selectedBlocks.size === 0) {
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

  // Markdown patterns for parsing pasted content
  const MARKDOWN_PATTERNS = {
    heading1: /^#\s/,
    heading2: /^##\s/,
    heading3: /^###\s/,
    bullet: /^[-*+]\s/,
    numbered: /^\d+\.\s/,
    quote: /^>\s/,
    code: /^```\s*$/,
    divider: /^---+\s*$/,
  };

  // Parse markdown content into block data
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
            const leadingSpaces = line.match(/^ */)?.[0]?.length || 0;
            indentLevel = Math.floor(leadingSpaces / 2);
          } else if (type === 'numbered') {
            blockContent = trimmedLine.replace(/^\d+\.\s/, '');
            const leadingSpaces = line.match(/^ */)?.[0]?.length || 0;
            indentLevel = Math.floor(leadingSpaces / 2);
          } else if (type === 'quote') {
            blockContent = trimmedLine.replace(/^>\s/, '');
          } else if (type === 'code') {
            blockContent = '';
            blockType = 'code';
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

  // Handle markdown paste from BlockEditor  
  const handleMarkdownPaste = (markdownText: string, targetBlockId: string) => {
    console.log('🎯 PageEditor: Handling markdown paste for block:', targetBlockId);
    console.log('🎯 PageEditor: Markdown text:', markdownText);
    
    const parsedBlocks = parseMarkdownContent(markdownText);
    console.log('🎯 PageEditor: Parsed blocks:', parsedBlocks);
    
    if (parsedBlocks.length === 0) {
      console.log('🎯 PageEditor: No blocks parsed, returning');
      return;
    }
    
    // Verify the target block exists
    const targetBlockExists = page.blocks.some(block => block.id === targetBlockId);
    if (!targetBlockExists) {
      console.error('🎯 PageEditor: Target block does not exist:', targetBlockId);
      return;
    }
    
    const targetBlockIndex = page.blocks.findIndex(block => block.id === targetBlockId);
    if (targetBlockIndex === -1) {
      console.error('🎯 PageEditor: Could not find target block index');
      return;
    }

    // Update the target block with the first parsed block
    const firstBlock = parsedBlocks[0];
    console.log('🎯 PageEditor: Updating target block with:', firstBlock);
    
    // Start with current page blocks
    let updatedBlocks = [...page.blocks];
    
    // Update the target block with the first parsed block
    const updatedTargetBlock = {
      ...updatedBlocks[targetBlockIndex],
      type: firstBlock.type,
      content: firstBlock.content,
      indentLevel: firstBlock.indentLevel || 0
    };
    updatedBlocks[targetBlockIndex] = updatedTargetBlock;
    
    // For multiple blocks, create additional blocks
    if (parsedBlocks.length > 1) {
      // Create new blocks for the remaining parsed content
      const newBlocks = parsedBlocks.slice(1).map((blockData, index) => ({
        id: `block_${Date.now()}_${Math.random().toString(36).substr(2, 9)}_${index}`,
        type: blockData.type,
        content: blockData.content,
        order: targetBlockIndex + 1 + index,
        indentLevel: blockData.indentLevel || 0
      }));
      
      console.log('🎯 PageEditor: Creating new blocks:', newBlocks);
      
      // Insert the new blocks after the target block
      updatedBlocks.splice(targetBlockIndex + 1, 0, ...newBlocks);
      
      // Save each new block to storage individually
      newBlocks.forEach((block, index) => {
        setTimeout(async () => {
          console.log(`🎯 PageEditor: Saving block ${block.id} to storage`);
          try {
            await storageManager.saveBlock(block, page.id);
            console.log(`✅ PageEditor: Block ${block.id} saved to storage successfully`);
          } catch (error) {
            console.warn(`⚠️ PageEditor: Could not save block ${block.id} to storage:`, error);
          }
        }, 100 * (index + 1));
      });
    }
    
    // Reorder all blocks to have clean sequential orders
    const reorderedBlocks = updatedBlocks.map((block, index) => ({
      ...block,
      order: index
    }));
    
    console.log('🎯 PageEditor: Updating page with all blocks (including updated target)');
    loggedOnUpdatePage({ blocks: reorderedBlocks });
    
    // Save the updated target block to storage
    setTimeout(async () => {
      console.log(`🎯 PageEditor: Saving updated target block ${targetBlockId} to storage`);
      try {
        const finalTargetBlock = reorderedBlocks.find(b => b.id === targetBlockId);
        if (finalTargetBlock) {
          await storageManager.saveBlock(finalTargetBlock, page.id);
          console.log(`✅ PageEditor: Updated target block ${targetBlockId} saved to storage successfully`);
        } else {
          console.warn(`⚠️ PageEditor: Could not find target block ${targetBlockId} in reordered blocks`);
        }
      } catch (error) {
        console.warn(`⚠️ PageEditor: Could not save updated target block ${targetBlockId} to storage:`, error);
      }
    }, 50); // Save target block first, before the new blocks
  };

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
        className="flex-1 overflow-y-auto relative bg-background"
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
          <div className="mb-8 relative">
            <div className="flex items-center gap-3 mb-6">
              <div className="relative emoji-picker-container">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-16 w-16 p-0 text-5xl hover:bg-gray-50/50 rounded-lg transition-colors"
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
            <div className="fixed top-4 right-4 z-50 p-3 bg-card border border-blue-200 dark:border-blue-700 rounded-lg shadow-lg text-sm max-w-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-blue-900 dark:text-blue-100">
                  {selectedBlocks.size} block{selectedBlocks.size !== 1 ? 's' : ''} selected
                </span>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    clearSelection();
                  }}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 ml-2"
                  title="Clear selection"
                >
                  ✕
                </button>
              </div>
              {selectedBlocks.size === 1 && (
                <div className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                  Hold Ctrl/Cmd and click more blocks to select multiple
                </div>
              )}
              <div className="flex gap-2">
                {selectedBlocks.size === 1 && (
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      const selectedBlockId = Array.from(selectedBlocks)[0];
                      console.log('Edit text button clicked for block:', selectedBlockId);
                      
                      // Trigger diff mode for the selected block
                      setDiffModeBlockId(selectedBlockId);
                      
                      // Focus the block and clear selection
                      setFocusedBlockId(selectedBlockId);
                      clearSelection();
                      
                      // Clear the trigger after a short delay
                      setTimeout(() => {
                        setDiffModeBlockId(null);
                      }, 100);
                    }}
                    className="flex-1 px-3 py-1 bg-muted text-muted-foreground border border-border rounded hover:bg-accent transition-colors text-xs"
                  >
                    Edit text
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    console.log('Delete button clicked, selected blocks:', Array.from(selectedBlocks));
                    handleDeleteSelected();
                  }}
                  className="flex-1 px-3 py-1 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-700 rounded hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors text-xs"
                >
                  Delete
                </button>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    clearSelection();
                  }}
                  className="flex-1 px-3 py-1 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-xs"
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
                    onAddBlock={(type) => handleAddBlock(block.id, type)}
                    onDeleteBlock={() => handleDeleteBlock(block.id)}
                    onFocus={() => {
                      console.log('🔍 Block focused:', block.id);
                      console.log('🔍 Current selection before focus:', Array.from(selectedBlocks));
                      console.log('🔍 Is this block selected?', selectedBlocks.has(block.id));
                      
                      setFocusedBlockId(block.id);
                      if (!selectedBlocks.has(block.id)) {
                        console.log('🔍 Clearing selection because block is not selected');
                        clearSelection();
                      } else {
                        console.log('🔍 NOT clearing selection because block is selected');
                      }
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
                    triggerDiffMode={diffModeBlockId === block.id}
                    workspace={workspace}
                    page={page}
                    onNavigateToPage={handleNavigateToPage}
                    onCreateCanvasPage={onCreateCanvasPage}
                    streamingState={block.id === streamingState.blockId ? streamingState : undefined}
                    onMarkdownPaste={handleMarkdownPaste}
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
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={onToggleSidebar}
      />
    </div>
  );
};
