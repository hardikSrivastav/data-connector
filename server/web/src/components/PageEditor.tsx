import { useState, useEffect, useRef, useCallback } from 'react';
import { flushSync } from 'react-dom';
import { Page, Workspace, Block } from '@/types';
import { BlockEditor } from './BlockEditor';
import { EmojiPicker } from './EmojiPicker';
import { BottomStatusBar } from './BottomStatusBar';
import { Button } from '@/components/ui/button';
import { useBlockSelection } from '@/hooks/useBlockSelection';
import { agentClient, AgentQueryResponse, StreamingCallbacks } from '@/lib/agent-client';
import { orchestrationAgent } from '@/lib/orchestration/agent';
import { StreamingStatusBlock } from './StreamingStatusBlock';
import { useStorageManager } from '@/hooks/useStorageManager';

// Enhanced markdown detection patterns for streaming
const STREAMING_MARKDOWN_PATTERNS = {
  heading: /^#{1,3}\s/m,
  list: /^[-*+]\s|^\d+\.\s/m,
  quote: /^>\s/m,
  code: /^```/m,
  divider: /^---+/m
};

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

// Enhanced reasoning chain interface for better typing
interface ReasoningChainEvent {
  type: 'status' | 'progress' | 'error' | 'complete' | 'partial_sql' | 'analysis_chunk' | 'classifying' | 'database_selected' | 'schema_loading' | 'query_generating' | 'query_executing' | 'partial_results' | 'planning' | 'aggregating';
  message: string;
  timestamp: string;
  metadata?: any;
}

interface ReasoningChainData {
  events: ReasoningChainEvent[];
  originalQuery: string;
  sessionId?: string;
  blockId?: string;
  isComplete: boolean;
  lastUpdated: string;
  status: 'streaming' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  currentStep?: string;
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
    history: Array<{
      type: 'status' | 'progress' | 'error' | 'complete' | 'partial_sql' | 'analysis_chunk' |
            // ✅ NEW: Add all detailed reasoning event types
            'detailed_reasoning_start' | 'session_updated' | 
            'sql_queries_section' | 'sql_query_executed' | 'no_sql_queries' |
            'tool_executions_section' | 'tool_execution_completed' | 'no_tool_executions' |
            'schema_discovery_section' | 'schema_discovered' | 'no_schema_discovery' |
            'execution_plans_section' | 'execution_plan_detail' | 'no_execution_plans' |
            'final_synthesis_analysis' | 'no_final_synthesis' | 'detailed_reasoning_complete' |
            'reasoning_chain_warning';
      message: string;
      timestamp: string;
      metadata?: any;
    }>;
  }>({
    isStreaming: false,
    status: '',
    progress: 0,
    history: []
  });
  const [diffModeBlockId, setDiffModeBlockId] = useState<string | null>(null);
  const addingBlockRef = useRef(false);
  
  // New state for reasoning chain persistence
  const [activeReasoningChains, setActiveReasoningChains] = useState<Map<string, ReasoningChainData>>(new Map());
  const saveReasoningChainTimeoutRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const [reasoningChainsLoaded, setReasoningChainsLoaded] = useState<Set<string>>(new Set());
  const [isLoadingReasoningChains, setIsLoadingReasoningChains] = useState(false);
  
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

  // Enhanced reasoning chain persistence functions
  const saveReasoningChainDebounced = useCallback((sessionId: string, reasoningData: ReasoningChainData) => {
    console.log(`🧠 Debounced save reasoning chain for session ${sessionId}`);
    
    // Clear existing timeout for this session
    const existingTimeout = saveReasoningChainTimeoutRef.current.get(sessionId);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
    }
    
    // Set new timeout
    const timeout = setTimeout(async () => {
      console.log(`💾 Executing save reasoning chain for session ${sessionId}`);
      try {
        // Save directly to reasoning chain storage (not block properties)
        const enhancedReasoningData = {
          ...reasoningData,
          pageId: page.id,
          sessionId
        };
        
        await storageManager.saveReasoningChain(enhancedReasoningData);
        console.log(`✅ Reasoning chain saved for session ${sessionId}`);
        
      } catch (error) {
        console.error(`❌ Failed to save reasoning chain for session ${sessionId}:`, error);
      }
      
      // Remove timeout reference
      saveReasoningChainTimeoutRef.current.delete(sessionId);
    }, 2000); // 2 second debounce
    
    saveReasoningChainTimeoutRef.current.set(sessionId, timeout);
  }, [page.id, storageManager]);

  const addReasoningChainEvent = useCallback((sessionId: string, event: ReasoningChainEvent) => {
    // Skip reasoning chain events for trivial operations
    if (sessionId.startsWith('trivial_')) {
      console.log(`🧠 Skipping reasoning chain event for trivial session ${sessionId}:`, event.type, event.message);
      return;
    }
    
    console.log(`🧠 Adding reasoning chain event for session ${sessionId}:`, event.type, event.message);
    
    setActiveReasoningChains(prev => {
      const current = prev.get(sessionId) || {
        events: [],
        originalQuery: '',
        sessionId,
        isComplete: false,
        lastUpdated: new Date().toISOString(),
        status: 'streaming',
        progress: 0
      };
      
      // Don't add duplicate events to prevent infinite loops
      const lastEvent = current.events[current.events.length - 1];
      if (lastEvent && 
          lastEvent.type === event.type && 
          lastEvent.message === event.message && 
          lastEvent.timestamp === event.timestamp) {
        console.log(`🧠 Skipping duplicate event for session ${sessionId}`);
        return prev; // Return unchanged map
      }
      
      const updated: ReasoningChainData = {
        ...current,
        events: [...current.events, event],
        lastUpdated: new Date().toISOString(),
        progress: event.type === 'complete' ? 1.0 : Math.min(current.progress + 0.1, 0.9),
        currentStep: event.message,
        sessionId
      };
      
      const newMap = new Map(prev);
      newMap.set(sessionId, updated);
      
      // Always trigger save for reasoning chains (independent of blocks)
      saveReasoningChainDebounced(sessionId, updated);
      
      return newMap;
    });
  }, [saveReasoningChainDebounced]);

  const initializeReasoningChain = useCallback((sessionId: string, query: string, blockId?: string) => {
    // Skip reasoning chain creation for trivial operations
    if (sessionId.startsWith('trivial_')) {
      console.log(`🧠 Skipping reasoning chain initialization for trivial session ${sessionId}`);
      return;
    }
    
    console.log(`🧠 Initializing reasoning chain for session ${sessionId} with query: ${query}`);
    
    const initialData: ReasoningChainData = {
      events: [{
        type: 'status',
        message: 'Starting AI query processing...',
        timestamp: new Date().toISOString(),
        metadata: { sessionId, blockId }
      }],
      originalQuery: query,
      sessionId,
      blockId, // Optional link to block
      isComplete: false,
      lastUpdated: new Date().toISOString(),
      status: 'streaming',
      progress: 0,
      currentStep: 'Starting AI query processing...'
    };
    
    setActiveReasoningChains(prev => {
      const newMap = new Map(prev);
      newMap.set(sessionId, initialData);
      return newMap;
    });
    
    // Immediate save for initialization
    saveReasoningChainDebounced(sessionId, initialData);
  }, [saveReasoningChainDebounced]);

  const completeReasoningChain = useCallback((sessionId: string, success: boolean = true, finalMessage?: string, blockId?: string) => {
    // Skip reasoning chain completion for trivial operations
    if (sessionId.startsWith('trivial_')) {
      console.log(`🧠 Skipping reasoning chain completion for trivial session ${sessionId}, success: ${success}`);
      return;
    }
    
    console.log(`🧠 Completing reasoning chain for session ${sessionId}, success: ${success}`);
    
    setActiveReasoningChains(prev => {
      const current = prev.get(sessionId);
      if (!current) return prev;
      
      const finalEvent: ReasoningChainEvent = {
        type: success ? 'complete' : 'error',
        message: finalMessage || (success ? 'Processing completed successfully' : 'Processing failed'),
        timestamp: new Date().toISOString(),
        metadata: { success, completedAt: new Date().toISOString(), blockId }
      };
      
      const completed: ReasoningChainData = {
        ...current,
        events: [...current.events, finalEvent],
        isComplete: true,
        lastUpdated: new Date().toISOString(),
        status: success ? 'completed' : 'failed',
        progress: 1.0,
        currentStep: finalEvent.message,
        blockId: blockId || current.blockId // Update block ID if provided
      };
      
      const newMap = new Map(prev);
      newMap.set(sessionId, completed);
      
      // Force immediate save for completion
      setTimeout(() => saveReasoningChainDebounced(sessionId, completed), 100);
      
      return newMap;
    });
  }, [saveReasoningChainDebounced]);

  // Load existing reasoning chains on page load (with debouncing and caching)
  useEffect(() => {
    const loadExistingReasoningChains = async () => {
      // Only load reasoning chains if we have a valid page ID that's not a placeholder/default
      if (!page?.id || page.id === 'default' || page.id === 'temp' || page.id === 'undefined') {
        console.log(`🧠 Skipping reasoning chain load - invalid page ID: ${page?.id}`);
        return;
      }

      // Check if storageManager is ready
      if (!storageManager) {
        console.log(`🧠 Skipping reasoning chain load - storageManager not ready`);
        return;
      }

      // Check if page is properly initialized
      if (!Array.isArray(page.blocks)) {
        console.log(`🧠 Skipping reasoning chain load - page blocks not initialized`);
        return;
      }

      // Check if already loaded for this page
      if (reasoningChainsLoaded.has(page.id)) {
        console.log(`🧠 Skipping reasoning chain load - already loaded for page ${page.id}`);
        return;
      }

      // Check if already loading
      if (isLoadingReasoningChains) {
        console.log(`🧠 Skipping reasoning chain load - already in progress`);
        return;
      }

      setIsLoadingReasoningChains(true);
      console.log(`🧠 Loading existing reasoning chains for page ${page.id}`);
      
      try {
        // Load reasoning chains from dedicated storage
        const reasoningChains = await storageManager.getReasoningChainsForPage(page.id);
        console.log(`🧠 Found ${reasoningChains.length} reasoning chains for page ${page.id}`);
        
        setActiveReasoningChains(prev => {
          const newMap = new Map(prev);
          reasoningChains.forEach(chain => {
            if (chain.sessionId) {
              newMap.set(chain.sessionId, chain);
              console.log(`🧠 Loaded reasoning chain session ${chain.sessionId}, events: ${chain.events?.length || 0}, complete: ${chain.isComplete}`);
              console.log(`🧠 Chain details:`, {
                sessionId: chain.sessionId,
                blockId: chain.blockId,
                originalQuery: chain.originalQuery,
                status: chain.status
              });
              
              // Try to find and update the corresponding canvas block
              let targetBlock = null;
              
              // Log available canvas blocks for debugging
              const canvasBlocks = page.blocks.filter(b => b.type === 'canvas');
              console.log(`🧠 Looking for canvas block match. Available canvas blocks:`, canvasBlocks.map(b => ({
                id: b.id,
                threadId: b.properties?.canvasData?.threadId,
                originalQuery: b.properties?.canvasData?.originalQuery
              })));
              
              // First try: direct blockId match
              if (chain.blockId) {
                targetBlock = page.blocks.find(b => b.id === chain.blockId && b.type === 'canvas');
                console.log(`🧠 BlockId match attempt for ${chain.blockId}:`, !!targetBlock);
              }
              
              // Second try: match by sessionId/threadId in canvasData
              if (!targetBlock && chain.sessionId) {
                targetBlock = page.blocks.find(b => 
                  b.type === 'canvas' && 
                  b.properties?.canvasData?.threadId === chain.sessionId
                );
                console.log(`🧠 ThreadId match attempt for ${chain.sessionId}:`, !!targetBlock);
              }
              
              // Third try: match by originalQuery
              if (!targetBlock && chain.originalQuery) {
                targetBlock = page.blocks.find(b => 
                  b.type === 'canvas' && 
                  b.properties?.canvasData?.originalQuery === chain.originalQuery
                );
                console.log(`🧠 OriginalQuery match attempt for "${chain.originalQuery}":`, !!targetBlock);
              }
              
              if (targetBlock && targetBlock.properties?.canvasData) {
                console.log(`🧠 Updating canvas block ${targetBlock.id} with loaded reasoning chain (matched by ${chain.blockId ? 'blockId' : chain.sessionId ? 'sessionId' : 'query'})`);
                
                // Update the block's canvasData with the reasoning chain
                const updatedCanvasData = {
                  ...targetBlock.properties.canvasData,
                  reasoningChain: chain
                };
                
                // Update the block properties
                setTimeout(() => {
                  onUpdateBlock(targetBlock.id, {
                    properties: {
                      ...targetBlock.properties,
                      canvasData: updatedCanvasData
                    }
                  });
                }, 100);
              } else {
                console.log(`🧠 No matching canvas block found for reasoning chain ${chain.sessionId}`);
              }
            }
          });
          return newMap;
        });
        
        // Also check for legacy reasoning chains in block properties (for migration)
        page.blocks.forEach(block => {
          if (block.properties?.reasoningChain) {
            const reasoningData = block.properties.reasoningChain as ReasoningChainData;
            console.log(`🧠 Found legacy reasoning chain in block ${block.id}, events: ${reasoningData.events?.length || 0}, complete: ${reasoningData.isComplete}`);
            
            // Use block ID as session ID for legacy chains
            setActiveReasoningChains(prev => {
              const newMap = new Map(prev);
              newMap.set(block.id, reasoningData);
              return newMap;
            });
          }
        });
        
        // Mark this page as loaded
        setReasoningChainsLoaded(prev => {
          const newSet = new Set(prev);
          newSet.add(page.id);
          return newSet;
        });
        
      } catch (error) {
        console.error(`❌ Failed to load reasoning chains for page ${page.id}:`, error);
        
        // Fallback to legacy loading from block properties only
        page.blocks.forEach(block => {
          if (block.properties?.reasoningChain) {
            const reasoningData = block.properties.reasoningChain as ReasoningChainData;
            console.log(`🧠 Fallback: Found reasoning chain in block ${block.id}, events: ${reasoningData.events?.length || 0}, complete: ${reasoningData.isComplete}`);
            
            setActiveReasoningChains(prev => {
              const newMap = new Map(prev);
              newMap.set(block.id, reasoningData);
              return newMap;
            });
          }
        });
        
        // Still mark as loaded to prevent infinite retries
        setReasoningChainsLoaded(prev => {
          const newSet = new Set(prev);
          newSet.add(page.id);
          return newSet;
        });
      } finally {
        setIsLoadingReasoningChains(false);
      }
    };
    
    // Only run if we have a valid page ID and storageManager
    // Also ensure the page is properly initialized (has blocks array)
    // REMOVED page.blocks dependency to prevent streaming interference
    if (page?.id && 
        page.id !== 'default' && 
        page.id !== 'temp' && 
        page.id !== 'undefined' && 
        Array.isArray(page.blocks) && 
        storageManager) {
      
      // Debounce the loading to prevent rapid successive calls
      const debounceTimeout = setTimeout(() => {
        loadExistingReasoningChains();
      }, 500); // 500ms debounce
      
      return () => clearTimeout(debounceTimeout);
    } else {
      console.log(`🧠 Skipping reasoning chain load - page not ready:`, {
        hasPageId: !!page?.id,
        pageId: page?.id,
        hasBlocks: Array.isArray(page?.blocks),
        hasStorageManager: !!storageManager
      });
    }
  }, [page?.id, storageManager, reasoningChainsLoaded, isLoadingReasoningChains]); // Removed page.blocks dependency

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
        order: 0,
        createdAt: new Date(),
        updatedAt: new Date()
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

  // AI Query handler - Updated to use reasoning chain persistence
  const handleAIQuery = async (query: string, blockId: string) => {
    console.log(`🎯 PageEditor: handleAIQuery called`);
    console.log(`📝 PageEditor: Query='${query}', BlockId='${blockId}'`);
    
    // Get the current block for context
    const currentBlock = page.blocks.find(b => b.id === blockId);
    if (!currentBlock) {
      console.error(`❌ PageEditor: Block ${blockId} not found`);
      return;
    }

    // Create block context for orchestration agent
    const blockContext = {
      blockId: currentBlock.id,
      content: currentBlock.content || '',
      type: currentBlock.type || 'text',
      pageContext: {
        title: page.title || 'Untitled Page',
        tags: []
      }
    };

    console.log(`🤖 PageEditor: Starting orchestration classification...`);
    console.log(`🤖 PageEditor: Block context:`, blockContext);

    try {
      // Use orchestration agent to classify the operation
      const classification = await orchestrationAgent.classifyOperation(query, blockContext);
      console.log(`🤖 PageEditor: Classification result:`, classification);
      console.log(`🎯 PageEditor: Routing to ${classification.tier} tier (${Math.round(classification.confidence * 100)}% confidence)`);

      // Route based on classification
      if (classification.tier === 'trivial') {
        console.log(`⚡ PageEditor: Routing to trivial client for fast processing`);
        await handleTrivialQuery(query, blockId, classification);
      } else {
        console.log(`🚀 PageEditor: Routing to overpowered LLM for complex processing`);
        await handleOverpoweredQuery(query, blockId, classification);
      }

    } catch (error) {
      console.error(`❌ PageEditor: Orchestration classification failed:`, error);
      console.log(`🔄 PageEditor: Falling back to overpowered LLM`);
      
      // Fallback to overpowered LLM
      await handleOverpoweredQuery(query, blockId, {
        tier: 'overpowered',
        confidence: 0.5,
        reasoning: 'Fallback due to classification error',
        estimatedTime: 3000,
        operationType: 'fallback_operation'
      });
    }
  };

  // Handle trivial operations using fast Bedrock client
  const handleTrivialQuery = async (query: string, blockId: string, classification: any) => {
    console.log(`⚡ PageEditor: Processing trivial query with fast client`);
    console.log(`⚡ PageEditor: Query='${query}', Current BlockId='${blockId}'`);
    console.log(`⚡ PageEditor: Current page state:`, {
      pageId: page.id,
      totalBlocks: page.blocks.length,
      blockIds: page.blocks.map(b => b.id),
      currentBlockExists: page.blocks.some(b => b.id === blockId),
      currentBlockDetails: page.blocks.find(b => b.id === blockId) ? {
        id: blockId,
        type: page.blocks.find(b => b.id === blockId)?.type,
        content: page.blocks.find(b => b.id === blockId)?.content?.substring(0, 50) + '...'
      } : 'NOT FOUND'
    });
    
    // Initialize streaming state for trivial operation
    setStreamingState({
      isStreaming: true,
      status: 'Processing with fast AI...',
      progress: 0,
      blockId: blockId,
      query: query,
      history: []
    });

    // Create new block immediately after the current block
    console.log(`⚡ PageEditor: About to call onAddBlock with afterBlockId='${blockId}'...`);
    const newBlockId = onAddBlock(blockId);
    console.log(`➕ PageEditor: New block created for trivial operation: ${newBlockId} (after block: ${blockId})`);
    console.log(`➕ PageEditor: Page state after onAddBlock:`, {
      totalBlocks: page.blocks.length,
      blockIds: page.blocks.map(b => b.id),
      newBlockExists: page.blocks.some(b => b.id === newBlockId),
      newBlockDetails: page.blocks.find(b => b.id === newBlockId) ? {
        id: newBlockId,
        type: page.blocks.find(b => b.id === newBlockId)?.type,
        content: page.blocks.find(b => b.id === newBlockId)?.content?.substring(0, 50) + '...'
      } : 'NOT FOUND YET'
    });

    // Generate session ID for reasoning chain
    const sessionId = `trivial_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Initialize reasoning chain for trivial operations too
    initializeReasoningChain(sessionId, query, newBlockId);
    addReasoningChainEvent(sessionId, {
      type: 'status',
      message: `Fast AI processing (${classification.tier}): ${classification.operationType}`,
      timestamp: new Date().toISOString(),
      metadata: { classification, provider: 'trivial', blockId: newBlockId }
    });

    // Set temporary status
    setPendingAIUpdate({ 
      blockId: newBlockId, 
      content: `⚡ Processing: ${query}`, 
    });

    try {
      console.log(`🌊 PageEditor: Starting real trivial client streaming...`);
      
      // Map classification operation to trivial operation
      const operationMap = {
        'text_editing': 'improve_clarity',
        'grammar_fix': 'fix_grammar', 
        'tone_adjustment': 'improve_tone',
        'content_generation': 'expand_text',
        'content_transformation': 'improve_clarity',
        'formatting': 'improve_clarity'
      };
      
      const trivialOperation = operationMap[classification.operationType] || 'improve_clarity';
      console.log(`⚡ PageEditor: Mapped ${classification.operationType} -> ${trivialOperation}`);
      
      addReasoningChainEvent(sessionId, {
        type: 'status',
        message: `Mapped operation: ${classification.operationType} → ${trivialOperation}`,
        timestamp: new Date().toISOString(),
        metadata: { mapping: operationMap, selectedOperation: trivialOperation }
      });
      
      // Prepare request for trivial client
      const trivialRequest = {
        operation: trivialOperation,
        text: query,
        context: {
          block_type: 'text',
          classification: classification,
          original_query: query
        }
      };
      
      console.log(`⚡ PageEditor: Trivial request:`, trivialRequest);
      
      // Call real trivial client streaming
      await agentClient.streamTrivialOperation(
        trivialRequest,
        (chunk) => {
          console.log(`⚡ PageEditor: Received trivial chunk:`, chunk);
          
          if (chunk.type === 'start') {
            setStreamingState(prev => ({
              ...prev,
              status: `⚡ ${chunk.provider} (${chunk.model}) processing...`,
              progress: 0.1
            }));
            
            addReasoningChainEvent(sessionId, {
              type: 'status',
              message: `Connected to ${chunk.provider} (${chunk.model})`,
              timestamp: new Date().toISOString(),
              metadata: { provider: chunk.provider, model: chunk.model }
            });
          } else if (chunk.type === 'chunk') {
            // Update progress
            setStreamingState(prev => ({
              ...prev,
              status: `⚡ Generating response...`,
              progress: Math.min(prev.progress + 0.1, 0.9)
            }));
            
            // Enhanced progress tracking with multiline detection
            const chunkLines = chunk.partial_result ? chunk.partial_result.split('\n').length : 0;
            addReasoningChainEvent(sessionId, {
              type: 'progress',
              message: `Generating content chunk (${chunk.partial_result?.length || 0} chars, ${chunkLines} lines)`,
              timestamp: new Date().toISOString(),
              metadata: { 
                chunkSize: chunk.partial_result?.length, 
                linesDetected: chunkLines,
                isMultiline: chunkLines > 1
              }
            });
            
            // Enhanced streaming preview with multiline detection
            if (chunk.partial_result) {
              const hasNewlines = chunk.partial_result.includes('\n');
              const lineCount = chunk.partial_result.split('\n').length;
              
              if (hasNewlines && lineCount > 1) {
                // Show multiline preview during streaming
                setPendingAIUpdate({ 
                  blockId: newBlockId
                  //content: `⚡ **Fast AI Streaming** (${lineCount} lines detected)\n\n${chunk.partial_result}\n\n`
                });
              } else {
                // Regular streaming preview
                setPendingAIUpdate({ 
                  blockId: newBlockId 
                  //content: `⚡ **Fast AI Streaming...**\n\n${chunk.partial_result}\n\n`
                });
              }
            }
            
          } else if (chunk.type === 'complete') {
            const result = chunk.result || query;
            const duration = chunk.duration || 0;
            const cached = chunk.cached || false;
            
            console.log(`✅ PageEditor: Trivial operation complete in ${duration.toFixed(2)}s ${cached ? '(cached)' : ''}`);
            
            addReasoningChainEvent(sessionId, {
              type: 'complete',
              message: `Completed in ${duration.toFixed(2)}s ${cached ? '(cached)' : ''}`,
              timestamp: new Date().toISOString(),
              metadata: { duration, cached, resultLength: result.length }
            });
            
            // Check for multiline content that should be split into separate blocks
            const lines = result.split('\n');
            const nonEmptyLines = lines.filter(line => line.trim()).length;
            const hasMultipleLines = lines.length > 1;
            
            console.log(`📝 PageEditor: COMPLETION ANALYSIS:`, {
              resultLength: result.length,
              totalLines: lines.length,
              nonEmptyLines: nonEmptyLines,
              hasMultipleLines: hasMultipleLines,
              shouldTriggerMultiline: hasMultipleLines && nonEmptyLines > 1,
              resultPreview: result.substring(0, 100) + (result.length > 100 ? '...' : ''),
              linesPreview: lines.slice(0, 3)
            });
            
            if (hasMultipleLines && nonEmptyLines > 1) {
              console.log(`📝 PageEditor: ✅ TRIGGERING MULTILINE - ${lines.length} lines (${nonEmptyLines} non-empty)`);
              console.log(`📝 PageEditor: Lines to process:`, lines.map((line, i) => `${i}: "${line}"`));
              
              addReasoningChainEvent(sessionId, {
                type: 'status',
                message: `Processing multiline result into ${lines.length} separate blocks`,
                timestamp: new Date().toISOString(),
                metadata: { 
                  totalLines: lines.length,
                  nonEmptyLines: nonEmptyLines,
                  multilineDetected: true
                }
              });
              
              // Clear any pending update to avoid conflicts
              setPendingAIUpdate(null);
              
              // Use the new multiline handler for line-by-line block creation
              console.log(`📝 PageEditor: About to call handleTrivialMultilineResult with blockId: ${newBlockId}`);
              handleTrivialMultilineResult(result, newBlockId);
              
            } else {
              console.log(`📝 PageEditor: ❌ NOT MULTILINE - Using direct block update`);
              console.log(`📝 PageEditor: Reason: hasMultipleLines=${hasMultipleLines}, nonEmptyLines=${nonEmptyLines}`);
              setPendingAIUpdate({ 
                blockId: newBlockId, 
                content: result
              });
            }

            completeReasoningChain(sessionId, true, `Fast AI processing completed successfully in ${duration.toFixed(2)}s`, newBlockId);

            setStreamingState({
              isStreaming: false,
              status: '',
              progress: 0,
              history: []
            });
          } else if (chunk.type === 'error') {
            console.error(`❌ PageEditor: Trivial streaming error:`, chunk.message);
            
            addReasoningChainEvent(sessionId, {
              type: 'error',
              message: `Trivial client error: ${chunk.message}`,
              timestamp: new Date().toISOString(),
              metadata: { error: chunk.message }
            });
            
            throw new Error(chunk.message || 'Trivial operation failed');
          }
        },
        (error) => {
          console.error(`❌ PageEditor: Trivial streaming failed:`, error);
          
          addReasoningChainEvent(sessionId, {
            type: 'error',
            message: `Streaming failed: ${error}`,
            timestamp: new Date().toISOString(),
            metadata: { error: error.toString() }
          });
          
          throw new Error(error);
        }
      );

    } catch (error) {
      console.error(`❌ PageEditor: Trivial query failed:`, error);
      
      // Show error and fallback to overpowered
      setPendingAIUpdate({ 
        blockId: newBlockId, 
        content: `❌ **Trivial Client Error**\n\n${error.message}\n\n🔄 Falling back to main LLM...`
      });
      
      addReasoningChainEvent(sessionId, {
        type: 'error',
        message: `Trivial client failed: ${error.message}. Falling back to main LLM.`,
        timestamp: new Date().toISOString(),
        metadata: { error: error.message, fallback: true }
      });
      
      completeReasoningChain(sessionId, false, `Trivial client failed: ${error.message}`, newBlockId);
      
      // Wait a moment then fallback
      setTimeout(async () => {
        await handleOverpoweredQuery(query, blockId, classification);
      }, 2000);
    }
  };

  // Handle overpowered operations using main LLM
  const handleOverpoweredQuery = async (query: string, blockId: string, classification: any) => {
    console.log(`🚀 PageEditor: Processing overpowered query with main LLM`);
    
    // Initialize streaming state
    setStreamingState({
      isStreaming: true,
      status: 'Starting query processing...',
      progress: 0,
      blockId: blockId,
      query: query,
      history: []
    });

    // Create new block immediately for streaming progress
    const newBlockId = onAddBlock(blockId);
    console.log(`➕ PageEditor: New Canvas block created with id='${newBlockId}'`);

    // Initialize reasoning chain
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    initializeReasoningChain(sessionId, query, newBlockId);
    
    addReasoningChainEvent(sessionId, {
      type: 'status',
      message: `Starting overpowered LLM processing (${classification.tier})`,
      timestamp: new Date().toISOString(),
      metadata: { classification, sessionId }
    });

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
        finalRowCount?: number;
      } = {};
      
      // Call the streaming agent API with captured data enabled
      await agentClient.queryStream({
        question: query,
        analyze: true,
        show_captured_data: true,  // ✅ Enable captured data display
        verbose: true,             // Also enable verbose output
        show_outputs: true         // And comprehensive output breakdown
      }, {
        onStatus: (message) => {
          console.log(`📊 Status: ${message}`);
          setStreamingState(prev => ({
            ...prev,
            status: message,
            progress: Math.min(prev.progress + 0.1, 0.9),
            history: [...prev.history, {
              type: 'status',
              message,
              timestamp: new Date().toISOString()
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'status',
            message,
            timestamp: new Date().toISOString()
          });
        },
        
        onClassifying: (message) => {
          console.log(`🔍 Classifying: ${message}`);
          const statusMessage = `Analyzing query: ${message}`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.15,
            history: [...prev.history, {
              type: 'status',
              message: statusMessage,
              timestamp: new Date().toISOString()
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'classifying',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { classifyingMessage: message }
          });
        },
        
        onDatabasesSelected: (databases, reasoning, isCrossDatabase) => {
          console.log(`🎯 Databases selected:`, databases);
          accumulatedData.databases = databases;
          accumulatedData.isCrossDatabase = isCrossDatabase;
          
          const statusMessage = `Selected databases: ${databases.join(', ')}`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.25,
            history: [...prev.history, {
              type: 'status',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { databases, reasoning, isCrossDatabase }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'database_selected',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { databases, reasoning, isCrossDatabase }
          });
        },
        
        onSchemaLoading: (database, progress) => {
          console.log(`📋 Schema loading for ${database}: ${progress}`);
          const statusMessage = `Loading ${database} schema...`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.25 + (progress * 0.2), // 25% to 45%
            history: [...prev.history, {
              type: 'progress',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { database, schemaProgress: progress }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'schema_loading',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { database, schemaProgress: progress }
          });
        },
        
        onQueryGenerating: (database) => {
          console.log(`⚙️ Generating query for ${database}`);
          const statusMessage = `Generating query for ${database}...`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.5,
            history: [...prev.history, {
              type: 'status',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { database }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'query_generating',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { database }
          });
        },
        
        onQueryExecuting: (database, sql) => {
          console.log(`🚀 Executing query on ${database}`);
          if (sql) accumulatedData.sqlQuery = sql;
          
          const statusMessage = `Executing query on ${database}...`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.65,
            history: [...prev.history, {
              type: 'status',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { database, sql }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'query_executing',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { database, sql: sql?.substring(0, 200) + (sql?.length > 200 ? '...' : '') }
          });
        },
        
        onPartialResults: (database, rowsCount, isComplete) => {
          console.log(`📊 Partial results from ${database}: ${rowsCount} rows`);
          const statusMessage = `Received ${rowsCount} rows from ${database}`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: isComplete ? 0.8 : 0.75,
            history: [...prev.history, {
              type: 'progress',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { database, rowsCount, isComplete }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'partial_results',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { database, rowsCount, isComplete }
          });
          
          // Store partial results count for later use
          if (isComplete) {
            console.log(`🔍 PageEditor: Storing final row count: ${rowsCount}`);
            accumulatedData.finalRowCount = rowsCount;
          }
        },
        
        onAnalysisGenerating: (message) => {
          console.log(`🧠 Analysis: ${message}`);
          setStreamingState(prev => ({
            ...prev,
            status: message,
            progress: 0.85,
            history: [...prev.history, {
              type: 'analysis_chunk',
              message,
              timestamp: new Date().toISOString()
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'analysis_chunk',
            message,
            timestamp: new Date().toISOString()
          });
        },

        // ✅ NEW: Handle detailed reasoning events from backend
        onDetailedReasoningEvent: (event) => {
          console.log(`🧠 PageEditor: Received detailed reasoning event: ${event.type}`, event);
          
          // Update streaming state with detailed reasoning event
          setStreamingState(prev => ({
            ...prev,
            status: event.message || `Processing ${event.type}...`,
            history: [...prev.history, {
              type: event.type as any, // Cast to allow new event types
              message: event.message || '',
              timestamp: event.timestamp,
              metadata: {
                // Pass through all the detailed event data
                query_number: event.query_number,
                source: event.source,
                query_text: event.query_text,
                execution_time_ms: event.execution_time_ms,
                rows_returned: event.rows_returned,
                execution_number: event.execution_number,
                tool_id: event.tool_id,
                success: event.success,
                call_id: event.call_id,
                error_message: event.error_message,
                tables_found: event.tables_found,
                content_preview: event.content_preview,
                plan_number: event.plan_number,
                plan_id: event.plan_id,
                strategy: event.strategy,
                operations_count: event.operations_count,
                synthesis_length: event.synthesis_length,
                confidence_score: event.confidence_score,
                sources_used: event.sources_used,
                synthesis_preview: event.synthesis_preview,
                ...event // Include any other fields
              }
            }]
          }));

          // Also add to reasoning chain with more specific typing
          addReasoningChainEvent(sessionId, {
            type: 'status' as any, // Map to allowed types for now
            message: event.message || `${event.type}: Processing...`,
            timestamp: event.timestamp,
            metadata: event
          });
        },
        
        onPlanning: (step, operationsPlanned) => {
          console.log(`📋 Planning: ${step}`);
          const statusMessage = `Planning: ${step}`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.4,
            history: [...prev.history, {
              type: 'status',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { operationsPlanned }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'planning',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { operationsPlanned }
          });
        },
        
        onAggregating: (step, progress) => {
          console.log(`🔗 Aggregating: ${step}`);
          const aggProgress = progress || 0;
          const statusMessage = `Aggregating data: ${step}`;
          setStreamingState(prev => ({
            ...prev,
            status: statusMessage,
            progress: 0.7 + (aggProgress * 0.1),
            history: [...prev.history, {
              type: 'progress',
              message: statusMessage,
              timestamp: new Date().toISOString(),
              metadata: { aggregationProgress: aggProgress }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'aggregating',
            message: statusMessage,
            timestamp: new Date().toISOString(),
            metadata: { aggregationProgress: aggProgress }
          });
        },
        
        onComplete: async (results, sessionId) => {
          console.log(`🎯 PageEditor: Query completed with sessionId: ${sessionId}`);
          console.log(`🎯 PageEditor: Results:`, results);
          
          // Update reasoning chain as complete
          if (sessionId && activeReasoningChains.has(sessionId)) {
            const reasoningChain = activeReasoningChains.get(sessionId);
            if (reasoningChain) {
              reasoningChain.isComplete = true;
              reasoningChain.status = 'completed';
              reasoningChain.progress = 1.0;
              reasoningChain.lastUpdated = new Date().toISOString();
              
              // Save completed reasoning chain
              try {
                await storageManager.saveReasoningChain(reasoningChain);
                await storageManager.completeReasoningChain(sessionId, true, newBlockId);
                console.log(`✅ PageEditor: Reasoning chain marked as complete: ${sessionId}`);
              } catch (error) {
                console.error(`❌ PageEditor: Failed to complete reasoning chain: ${error}`);
              }
            }
            
            // Clean up active reasoning chain
            activeReasoningChains.delete(sessionId);
          }
          
          // Extract canvas data from results using existing function
          const extractedCanvasData = createCanvasPreviewFromResponse(results, query);
          
          console.log(`🎯 PageEditor: Extracted canvas data:`, {
            hasAnalysis: !!extractedCanvasData.fullAnalysis,
            hasData: !!extractedCanvasData.fullData,
            hasSqlQuery: !!extractedCanvasData.sqlQuery,
            hasPreview: !!extractedCanvasData.preview
          });
          
          // Create comprehensive canvas data object
          const fullCanvasData: any = {
            threadId: sessionId || `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            threadName: generateThreadName(query),
            isExpanded: false,
            workspaceId: workspace.id,
            pageId: page.id,  // This is the original page where query was made
            blockId: newBlockId,
            fullAnalysis: extractedCanvasData.fullAnalysis,
            fullData: extractedCanvasData.fullData,
            sqlQuery: extractedCanvasData.sqlQuery,
            preview: extractedCanvasData.preview,
            blocks: [],
            // Store the complete reasoning chain with proper page references
            reasoningChain: {
              ...activeReasoningChains.get(sessionId),
              originalPageId: page.id,  // Original page where query was made
              // pageId will be set to Canvas page when it's created
            },
            originalQuery: query,
            originalPageId: page.id  // Store original page reference
          };
          
          // Create analysis commit for Canvas system integration
          if (sessionId && extractedCanvasData.fullAnalysis) {
            try {
              const analysisCommit = {
                id: `commit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                threadId: sessionId,
                commitMessage: `Analysis: ${query.substring(0, 50)}...`,
                queryText: query,
                resultData: {
                  fullData: extractedCanvasData.fullData,
                  sqlQuery: extractedCanvasData.sqlQuery,
                  workspaceId: workspace.id,
                  pageId: page.id,
                  blockId: newBlockId
                },
                analysisSummary: extractedCanvasData.fullAnalysis,
                previewData: extractedCanvasData.preview,
                performanceMetrics: {
                  queryTime: results.executionTime || 0,
                  rowCount: extractedCanvasData.fullData?.rows?.length || 0,
                  completedAt: new Date().toISOString()
                },
                isHead: true,
                createdAt: new Date()
              };
              
              console.log(`🎯 PageEditor: Creating analysis commit for Canvas system:`, analysisCommit);
              
              // Save analysis commit via storage manager
              // Note: This will require adding an endpoint for analysis commits
              // For now, we'll store it in the canvas data
              fullCanvasData.analysisCommit = analysisCommit;
              
            } catch (error) {
              console.warn(`⚠️ PageEditor: Failed to create analysis commit: ${error}`);
            }
          }
          
          // Process final results
          if (results) {
            console.log(`🔍 PageEditor: Processing results object...`);            
            console.log(`🔍 PageEditor: results type:`, typeof results);
            console.log(`🔍 PageEditor: results.rows before assignment:`, results.rows);
            console.log(`🔍 PageEditor: results.analysis before assignment:`, results.analysis);
            console.log(`🔍 PageEditor: results.sql before assignment:`, results.sql);
            
            // Handle case where results might be a string (should be rare now with backend fix)
            let parsedResults = results;
            if (typeof results === 'string') {
              console.log(`🔧 PageEditor: Results is a string, attempting JSON parse...`);
              try {
                parsedResults = JSON.parse(results);
                console.log(`✅ PageEditor: Successfully parsed JSON results:`, {
                  hasRows: !!parsedResults.rows,
                  rowsLength: parsedResults.rows?.length || 0,
                  hasAnalysis: !!parsedResults.analysis,
                  hasSql: !!parsedResults.sql
                });
              } catch (parseError) {
                console.error(`❌ PageEditor: JSON parse failed:`, parseError);
                console.log(`🔍 PageEditor: Raw string preview:`, results.substring(0, 200) + '...');
                // Keep original string if parsing fails
                parsedResults = results;
              }
            }
            
            // Extract data from parsed results
            accumulatedData.rows = parsedResults.rows;
            accumulatedData.analysis = parsedResults.analysis;
            accumulatedData.sqlQuery = parsedResults.sql || accumulatedData.sqlQuery;
            
            console.log(`🔍 PageEditor: accumulatedData after assignment:`, {
              hasRows: !!accumulatedData.rows,
              rowsLength: accumulatedData.rows?.length || 0,
              rowsType: typeof accumulatedData.rows,
              hasAnalysis: !!accumulatedData.analysis,
              hasSql: !!accumulatedData.sqlQuery,
              firstRowSample: accumulatedData.rows?.[0]
            });
          } else {
            console.warn(`⚠️ PageEditor: results is null/undefined in onComplete`);
          }
          
          // WORKAROUND: If we don't have rows data but we know there should be some (from finalRowCount),
          // try to fetch the data directly from the backend
          if ((!accumulatedData.rows || accumulatedData.rows.length === 0) && accumulatedData.finalRowCount && accumulatedData.finalRowCount > 0) {
            console.log(`🔧 PageEditor: WORKAROUND - Attempting to fetch missing data directly...`);
            console.log(`🔧 PageEditor: Expected ${accumulatedData.finalRowCount} rows but got ${accumulatedData.rows?.length || 0}`);
            
            try {
              // Try to re-execute the query to get the data
              const fallbackResponse = await agentClient.query({
                question: query,
                analyze: !!accumulatedData.analysis
              });
              
              console.log(`🔧 PageEditor: Fallback query response:`, {
                hasRows: !!fallbackResponse.rows,
                rowsLength: fallbackResponse.rows?.length || 0,
                hasAnalysis: !!fallbackResponse.analysis,
                hasSql: !!fallbackResponse.sql
              });
              
              if (fallbackResponse.rows && fallbackResponse.rows.length > 0) {
                console.log(`✅ PageEditor: Successfully retrieved ${fallbackResponse.rows.length} rows via fallback`);
                accumulatedData.rows = fallbackResponse.rows;
                accumulatedData.analysis = fallbackResponse.analysis || accumulatedData.analysis;
                accumulatedData.sqlQuery = fallbackResponse.sql || accumulatedData.sqlQuery;
              }
            } catch (fallbackError) {
              console.error(`❌ PageEditor: Fallback query failed:`, fallbackError);
            }
          }
          
          // Create canvas data from accumulated streaming data
          const response = {
            rows: accumulatedData.rows || [],
            sql: accumulatedData.sqlQuery || '',
            analysis: accumulatedData.analysis || ''
          };
          
          console.log(`🎯 PageEditor: About to create canvas preview from response:`, {
            hasRows: !!response.rows,
            rowsLength: response.rows?.length || 0,
            hasAnalysis: !!response.analysis,
            hasSql: !!response.sql,
            firstRowSample: response.rows?.[0],
            responseStructure: {
              rowsType: typeof response.rows,
              rowsIsArray: Array.isArray(response.rows),
              analysisLength: response.analysis?.length || 0,
              sqlLength: response.sql?.length || 0
            }
          });
          
          const canvasData = createCanvasPreviewFromResponse(response, query);
          
          console.log(`🎯 PageEditor: Canvas data created:`, {
            hasFullAnalysis: !!canvasData.fullAnalysis,
            hasFullData: !!canvasData.fullData,
            hasSqlQuery: !!canvasData.sqlQuery,
            hasPreview: !!canvasData.preview,
            fullDataStructure: canvasData.fullData ? {
              headers: canvasData.fullData.headers?.length,
              rows: canvasData.fullData.rows?.length
            } : null,
            previewStructure: canvasData.preview ? {
              hasSummary: !!canvasData.preview.summary,
              hasStats: !!canvasData.preview.stats,
              hasTablePreview: !!canvasData.preview.tablePreview,
              tablePreviewStructure: canvasData.preview.tablePreview ? {
                headers: canvasData.preview.tablePreview.headers?.length,
                rows: canvasData.preview.tablePreview.rows?.length
              } : null
            } : null
          });
          
          // Update the block with final canvas data
          console.log(`💾 PageEditor: Setting pending AI update for blockId=${newBlockId}`);
          setPendingAIUpdate({ 
            blockId: newBlockId, 
            canvasData: fullCanvasData
          });
          
          // Complete reasoning chain
          completeReasoningChain(sessionId, true, 'Overpowered LLM processing completed successfully', newBlockId);
          
          // Clear streaming state
          setTimeout(() => {
            setStreamingState({
              isStreaming: false,
              status: '',
              progress: 0,
              history: []
            });
          }, 1000);
        },
        
        onError: (error, errorCode, recoverable) => {
          console.error('❌ PageEditor: Streaming error:', error);
          setStreamingState(prev => ({
            ...prev,
            status: `Error: ${error}`,
            progress: 0,
            history: [...prev.history, {
              type: 'error',
              message: `Error: ${error}`,
              timestamp: new Date().toISOString(),
              metadata: { errorCode, recoverable }
            }]
          }));
          
          addReasoningChainEvent(sessionId, {
            type: 'error',
            message: `Error: ${error}`,
            timestamp: new Date().toISOString(),
            metadata: { errorCode, recoverable }
          });
          
          // Show error in the block
          const errorMessage = `❌ **Error:** ${error}\n\n${recoverable ? '🔄 You can try again.' : ''}`;
          setPendingAIUpdate({ blockId: newBlockId, content: errorMessage });
          
          // Complete reasoning chain with error
          completeReasoningChain(sessionId, false, `Processing failed: ${error}`, newBlockId);
          
          // Clear streaming state
          setTimeout(() => {
            setStreamingState({
              isStreaming: false,
              status: '',
              progress: 0,
              history: []
            });
          }, 2000);
        }
      });
      
    } catch (error) {
      console.error('❌ PageEditor: Streaming setup failed:', error);
      
      addReasoningChainEvent(sessionId, {
        type: 'error',
        message: `Streaming setup failed: ${error.message}`,
        timestamp: new Date().toISOString(),
        metadata: { error: error.message }
      });
      
      // Fallback error handling
      const errorMessage = `❌ **Error:** ${error.message || 'Failed to start streaming query. Please check that the agent server is running.'}`;
      setPendingAIUpdate({ blockId: newBlockId, content: errorMessage });
      
      completeReasoningChain(sessionId, false, `Setup failed: ${error.message}`);
      
      setStreamingState({
        isStreaming: false,
        status: '',
        progress: 0,
        history: []
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
    console.log('🎯 createCanvasPreviewFromResponse: Processing response:', {
      hasRows: !!response.rows,
      rowsLength: response.rows?.length || 0,
      hasAnalysis: !!response.analysis,
      hasSql: !!response.sql,
      hasCapturedData: !!(response as any).captured_data,
      capturedDataStructure: (response as any).captured_data ? {
        sqlQueries: (response as any).captured_data.sql_queries?.length || 0,
        toolExecutions: (response as any).captured_data.tool_executions?.length || 0,
        schemaData: (response as any).captured_data.schema_data?.length || 0,
        hasFinalSynthesis: !!(response as any).captured_data.final_synthesis
      } : null,
      firstRowSample: response.rows?.[0] ? Object.keys(response.rows[0]).slice(0, 5) : []
    });
    
    const canvasData: any = {};
    
    // Store full analysis text
    if (response.analysis) {
      canvasData.fullAnalysis = response.analysis;
      console.log('🎯 createCanvasPreviewFromResponse: Stored analysis:', response.analysis.substring(0, 100) + '...');
    }
    
    // Store SQL query
    if (response.sql) {
      canvasData.sqlQuery = response.sql;
      console.log('🎯 createCanvasPreviewFromResponse: Stored SQL query:', response.sql.substring(0, 100) + '...');
    }

    // Store captured execution data
    const capturedData = (response as any).captured_data;
    if (capturedData) {
      canvasData.capturedExecutionData = {
        sqlQueries: capturedData.sql_queries || [],
        toolExecutions: capturedData.tool_executions || [],
        schemaData: capturedData.schema_data || [],
        finalSynthesis: capturedData.final_synthesis || null,
        executionSummary: capturedData.execution_summary || {}
      };
      console.log('🎯 createCanvasPreviewFromResponse: Stored captured execution data:', {
        sqlQueries: canvasData.capturedExecutionData.sqlQueries.length,
        toolExecutions: canvasData.capturedExecutionData.toolExecutions.length,
        schemaData: canvasData.capturedExecutionData.schemaData.length,
        totalExecutionTime: canvasData.capturedExecutionData.executionSummary.total_execution_time,
        databasesAccessed: canvasData.capturedExecutionData.executionSummary.databases_accessed?.length || 0
      });
    }
    
    // Store full data - Handle mixed schemas from cross-database queries
    if (response.rows && response.rows.length > 0) {
      console.log('🎯 createCanvasPreviewFromResponse: Processing rows data...');
      console.log('🎯 createCanvasPreviewFromResponse: Raw first row sample:', response.rows[0]);
      
      // Enhanced Decimal conversion function
      const convertValue = (value: any): string => {
        if (value === null || value === undefined) return '';
        
        // Handle Decimal objects specifically
        if (typeof value === 'object' && value !== null) {
          // Check for Decimal objects (they have a toString method and specific structure)
          if (value.constructor && value.constructor.name === 'Decimal') {
            console.log('🎯 createCanvasPreviewFromResponse: Converting Decimal:', value, '→', value.toString());
            return value.toString();
          }
          // Handle other objects that might have toString
          if (typeof value.toString === 'function') {
            return value.toString();
          }
          // Fallback for complex objects
          return JSON.stringify(value);
        }
        
        // Handle Date objects
        if (value instanceof Date) return value.toISOString();
        
        // Handle primitives
        return String(value);
      };
      
      // Get all unique headers across all rows to handle mixed schemas
      const allHeaders = new Set<string>();
      response.rows.forEach(row => {
        if (row && typeof row === 'object') {
          Object.keys(row).forEach(key => allHeaders.add(key));
        }
      });
      
      const headers = Array.from(allHeaders);
      console.log('🎯 createCanvasPreviewFromResponse: Extracted headers:', headers.slice(0, 10), '... (showing first 10)');
      
      // Convert rows to consistent format, filling missing values with empty strings
      const processedRows = response.rows.map((row, index) => {
        if (!row || typeof row !== 'object') {
          console.warn(`🎯 createCanvasPreviewFromResponse: Invalid row at index ${index}:`, row);
          return headers.map(() => '');
        }
        
        const convertedRow = headers.map(header => {
          const value = row[header];
          const converted = convertValue(value);
          
          // Log Decimal conversions for debugging
          if (typeof value === 'object' && value !== null && value.constructor && value.constructor.name === 'Decimal') {
            console.log(`🎯 Row ${index}, Header ${header}: Decimal ${value} → ${converted}`);
          }
          
          return converted;
        });
        
        return convertedRow;
      }).filter(row => row.some(cell => cell !== '')); // Remove completely empty rows
      
      canvasData.fullData = {
        headers,
        rows: processedRows,
        totalRows: processedRows.length
      };
      
      console.log('🎯 createCanvasPreviewFromResponse: Processed data:', {
        headers: headers.length,
        rows: processedRows.length,
        sampleRow: processedRows[0]?.slice(0, 5) || [],
        firstProcessedRow: processedRows[0]
      });
    } else {
      console.log('🎯 createCanvasPreviewFromResponse: No rows data to process');
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
      console.log('🎯 createCanvasPreviewFromResponse: Created summary from analysis');
    } else if (response.rows && response.rows.length > 0) {
      const rowCount = response.rows.length;
      const uniqueHeaders = new Set<string>();
      response.rows.forEach(row => {
        if (row && typeof row === 'object') {
          Object.keys(row).forEach(key => uniqueHeaders.add(key));
        }
      });
      const columnCount = uniqueHeaders.size;
      
      preview.summary = `**Query Results Summary**\n\n✅ Query executed successfully\n\n📊 **${rowCount.toLocaleString()}** rows returned across **${columnCount}** columns\n\n*Click to expand and explore the full dataset with interactive charts and analysis.*`;
      console.log('🎯 createCanvasPreviewFromResponse: Created default summary for rows');
    } else {
      preview.summary = `**Query Executed**\n\n✅ The SQL query processed successfully but returned no data rows.\n\n*This might indicate the query conditions didn't match any records, or the target dataset is empty.*`;
      console.log('🎯 createCanvasPreviewFromResponse: Created empty results summary');
    }
    
    // Create stats
    const stats = [];
    
    if (response.rows && response.rows.length > 0) {
      stats.push({ label: 'Rows', value: response.rows.length.toLocaleString() });
      
      // Count unique columns across all rows
      const uniqueHeaders = new Set<string>();
      response.rows.forEach(row => {
        if (row && typeof row === 'object') {
          Object.keys(row).forEach(key => uniqueHeaders.add(key));
        }
      });
      
      if (uniqueHeaders.size > 0) {
        stats.push({ label: 'Columns', value: uniqueHeaders.size.toString() });
        
        // Try to find numeric columns for additional stats
        const sampleRow = response.rows.find(row => row && typeof row === 'object');
        if (sampleRow) {
          const numericColumns = Array.from(uniqueHeaders).filter(col => {
            const value = sampleRow[col];
            return typeof value === 'number' || 
                   (typeof value === 'string' && !isNaN(Number(value)) && value !== '') ||
                   (typeof value === 'object' && value && typeof value.toString === 'function' && !isNaN(Number(value.toString())));
          });
          
          if (numericColumns.length > 0) {
            stats.push({ label: 'Numeric Fields', value: numericColumns.length.toString() });
          }
        }
      }
    }
    
    if (response.sql) {
      stats.push({ label: 'SQL Lines', value: response.sql.split('\n').length.toString() });
    }
    
    if (stats.length > 0) {
      preview.stats = stats;
      console.log('🎯 createCanvasPreviewFromResponse: Created stats:', stats);
    }
    
    // Create table preview (limited rows for collapsed view)
    if (canvasData.fullData && canvasData.fullData.headers && canvasData.fullData.rows) {
      const { headers, rows } = canvasData.fullData;
      
      preview.tablePreview = {
        headers,
        rows: rows.slice(0, 5), // Show first 5 rows for preview
        totalRows: rows.length
      };
      
      console.log('🎯 createCanvasPreviewFromResponse: Created table preview:', {
        headers: headers.length,
        previewRows: preview.tablePreview.rows.length,
        totalRows: preview.tablePreview.totalRows,
        samplePreviewRow: preview.tablePreview.rows[0]
      });
    }
    
    // Add placeholder charts if we have numeric data
    if (canvasData.fullData && canvasData.fullData.headers && canvasData.fullData.rows.length > 0) {
      const { headers, rows } = canvasData.fullData;
      
      // Find numeric columns by checking first few rows
      const numericColumns = headers.filter(header => {
        const headerIndex = headers.indexOf(header);
        return rows.slice(0, Math.min(10, rows.length)).some(row => {
          const value = row[headerIndex];
          return value && !isNaN(Number(value)) && value !== '';
        });
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
        console.log('🎯 createCanvasPreviewFromResponse: Created chart placeholders:', charts.length);
      }
    }
    
    canvasData.preview = preview;
    console.log('🎯 createCanvasPreviewFromResponse: Final canvasData structure:', {
      hasFullAnalysis: !!canvasData.fullAnalysis,
      hasFullData: !!canvasData.fullData,
      hasSqlQuery: !!canvasData.sqlQuery,
      hasPreview: !!canvasData.preview,
      previewHasSummary: !!canvasData.preview?.summary,
      previewHasStats: !!(canvasData.preview?.stats?.length),
      previewHasTablePreview: !!canvasData.preview?.tablePreview,
      fullDataStructure: canvasData.fullData ? {
        headers: canvasData.fullData.headers?.length,
        rows: canvasData.fullData.rows?.length,
        sampleRow: canvasData.fullData.rows?.[0]?.slice(0, 3)
      } : null
    });
    
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

  // Navigation functions for up/down arrow keys
  const handleFocusNextBlock = useCallback(() => {
    if (!focusedBlockId) return;
    
    const currentIndex = page.blocks.findIndex(b => b.id === focusedBlockId);
    if (currentIndex === -1 || currentIndex >= page.blocks.length - 1) return;
    
    const nextBlock = page.blocks[currentIndex + 1];
    if (nextBlock) {
      setFocusedBlockId(nextBlock.id);
      clearSelection(); // Clear any selection when navigating
      
      // Focus the textarea in the next block after a brief delay
      setTimeout(() => {
        const nextBlockElement = document.querySelector(`[data-block-id="${nextBlock.id}"] textarea`);
        if (nextBlockElement) {
          (nextBlockElement as HTMLTextAreaElement).focus();
          // Position cursor at the beginning of the content
          (nextBlockElement as HTMLTextAreaElement).setSelectionRange(0, 0);
        }
      }, 10);
    }
  }, [focusedBlockId, page.blocks, clearSelection]);

  const handleFocusPreviousBlock = useCallback(() => {
    if (!focusedBlockId) return;
    
    const currentIndex = page.blocks.findIndex(b => b.id === focusedBlockId);
    if (currentIndex <= 0) return;
    
    const previousBlock = page.blocks[currentIndex - 1];
    if (previousBlock) {
      setFocusedBlockId(previousBlock.id);
      clearSelection(); // Clear any selection when navigating
      
      // Focus the textarea in the previous block after a brief delay
      setTimeout(() => {
        const prevBlockElement = document.querySelector(`[data-block-id="${previousBlock.id}"] textarea`);
        if (prevBlockElement) {
          (prevBlockElement as HTMLTextAreaElement).focus();
          // Position cursor at the end of the content
          const content = (prevBlockElement as HTMLTextAreaElement).value;
          (prevBlockElement as HTMLTextAreaElement).setSelectionRange(content.length, content.length);
        }
      }, 10);
    }
  }, [focusedBlockId, page.blocks, clearSelection]);

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
        order: 0,
        createdAt: new Date(),
        updatedAt: new Date()
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
    
    console.log('🚨 === STEP 4: STORAGE CLEANUP (BATCH) ===');
    
    // Step 3: Clean up storage in batch to avoid race conditions
    // For multi-block deletion, we handle storage cleanup differently to avoid racing calls to onDeleteBlock
    if (blocksToDelete.length === 1) {
      // Single block deletion - use the existing onDeleteBlock function
      console.log('🚨 Single block deletion - using onDeleteBlock');
      const blockId = blocksToDelete[0];
    setTimeout(() => {
        console.log(`🚨 [SINGLE] Calling onDeleteBlock for: ${blockId}`);
        try {
          onDeleteBlock(blockId);
          console.log(`🚨 [SINGLE] onDeleteBlock completed for: ${blockId}`);
        } catch (error) {
          console.error(`🚨 [SINGLE] Error in onDeleteBlock for ${blockId}:`, error);
        }
      }, 50);
    } else {
      // Multi-block deletion - handle storage cleanup directly to avoid race conditions
      console.log('🚨 Multi-block deletion - handling storage cleanup directly');
      setTimeout(async () => {
        console.log('🚨 Starting batch storage cleanup for blocks:', blocksToDelete);
        
        try {
          // Use the existing storageManager from the hook
          if (!storageManager) {
            throw new Error('StorageManager not available');
          }
          
          // Check for canvas blocks and handle their cleanup
          const canvasBlocksToCleanup: string[] = [];
          blocksToDelete.forEach(blockId => {
            const blockToDelete = page.blocks.find(b => b.id === blockId);
            if (blockToDelete?.type === 'canvas' && blockToDelete.properties?.canvasPageId) {
              canvasBlocksToCleanup.push(blockToDelete.properties.canvasPageId);
            }
          });
          
          // Clean up canvas pages if any
          if (canvasBlocksToCleanup.length > 0) {
            console.log('🎨 Cleaning up canvas pages:', canvasBlocksToCleanup);
            for (const canvasPageId of canvasBlocksToCleanup) {
              try {
                await storageManager.deletePage(canvasPageId);
                console.log('✅ Canvas page deleted from storage:', canvasPageId);
              } catch (error) {
                console.warn('⚠️ Failed to delete canvas page from storage:', canvasPageId, error);
              }
            }
          }
          
          // Delete blocks from storage in batch
          console.log(`🚨 Deleting ${blocksToDelete.length} blocks from storage...`);
          for (const blockId of blocksToDelete) {
            try {
              await storageManager.deleteBlock(blockId);
              console.log(`🚨 [BATCH] Block deleted from storage: ${blockId}`);
            } catch (error) {
              console.warn(`🚨 [BATCH] Failed to delete block from storage: ${blockId}`, error);
            }
          }
          
          console.log('✅ Batch storage cleanup completed');
        } catch (error) {
          console.error('❌ Error in batch storage cleanup:', error);
          // Fallback to individual onDeleteBlock calls if storage manager approach fails
          console.log('🔄 Falling back to individual onDeleteBlock calls');
          blocksToDelete.forEach((blockId, index) => {
            setTimeout(() => {
              console.log(`🚨 [FALLBACK ${index + 1}/${blocksToDelete.length}] Calling onDeleteBlock for: ${blockId}`);
              try {
                onDeleteBlock(blockId);
                console.log(`🚨 [FALLBACK ${index + 1}/${blocksToDelete.length}] onDeleteBlock completed for: ${blockId}`);
              } catch (error) {
                console.error(`🚨 [FALLBACK ${index + 1}/${blocksToDelete.length}] Error in onDeleteBlock for ${blockId}:`, error);
              }
            }, index * 50); // Stagger the calls to avoid race conditions
          });
        }
      }, 50);
    }
    
    // Log final state after a short delay
    setTimeout(() => {
      console.log('🚨 === FINAL STATE (after 100ms) ===');
      console.log('🚨 Final page.blocks:', page.blocks.map(b => ({ id: b.id, content: b.content?.substring(0, 20) })));
      console.log('🚨 Final selectedBlocks:', Array.from(selectedBlocks));
      console.log('🚨 === END handleDeleteSelectedWithBlocks ===');
    }, 100);
    
  }, [page.blocks, loggedOnUpdatePage, onDeleteBlock, clearSelection, selectedBlocks, storageManager]);

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
      console.log(`🎯 PageEditor: pendingAIUpdate contents:`, {
        blockId,
        hasContent: !!content,
        hasCanvasData: !!canvasData,
        canvasDataKeys: canvasData ? Object.keys(canvasData) : [],
        contentPreview: content?.substring(0, 50) + '...'
      });
      
      // Check if the block now exists in the page state
      const blockExists = page.blocks.some(block => block.id === blockId);
      console.log(`🎯 PageEditor: Block exists in current page state: ${blockExists}`);
      console.log(`🎯 PageEditor: Current page blocks:`, page.blocks.map(b => ({ id: b.id, content_length: b.content?.length || 0, type: b.type })));
      
      if (blockExists) {
        if (canvasData) {
          // Create Canvas block with preview data
          console.log(`🎯 PageEditor: Executing pending Canvas update for blockId='${blockId}'`);
          console.log(`🎯 PageEditor: Canvas data being applied:`, {
            threadName: canvasData.threadName,
            hasFullAnalysis: !!canvasData.fullAnalysis,
            hasFullData: !!canvasData.fullData,
            fullDataSample: canvasData.fullData ? {
              headers: canvasData.fullData.headers?.slice(0, 3),
              firstRow: canvasData.fullData.rows?.[0]?.slice(0, 3),
              totalRows: canvasData.fullData.rows?.length
            } : null,
            hasPreview: !!canvasData.preview,
            previewSample: canvasData.preview ? {
              summaryLength: canvasData.preview.summary?.length,
              hasTablePreview: !!canvasData.preview.tablePreview,
              tablePreviewStructure: canvasData.preview.tablePreview ? {
                headers: canvasData.preview.tablePreview.headers?.length,
                rows: canvasData.preview.tablePreview.rows?.length,
                firstPreviewRow: canvasData.preview.tablePreview.rows?.[0]?.slice(0, 3)
              } : null
            } : null
          });
          
          const blockUpdate = {
            content: canvasData.threadName,
            type: 'canvas' as const,
            properties: {
              canvasData: canvasData
            }
          };
          
          console.log(`🎯 PageEditor: Block update object:`, {
            content: blockUpdate.content,
            type: blockUpdate.type,
            hasCanvasData: !!blockUpdate.properties?.canvasData,
            canvasDataStructure: blockUpdate.properties?.canvasData ? {
              hasFullData: !!blockUpdate.properties.canvasData.fullData,
              hasPreview: !!blockUpdate.properties.canvasData.preview
            } : null
          });
          
          console.log(`🎯 PageEditor: About to call onUpdateBlock...`);
          onUpdateBlock(blockId, blockUpdate);
          console.log(`✅ PageEditor: onUpdateBlock called for Canvas update`);
          
        } else if (content) {
          // Create regular content block (for errors and trivial results)
          console.log(`🎯 PageEditor: Executing pending content update for blockId='${blockId}'`);
          console.log(`🎯 PageEditor: Content preview:`, content.substring(0, 100) + '...');
        
          onUpdateBlock(blockId, {
            content: content,
            type: 'text' // Use regular text blocks to allow markdown parsing
          });
        
          console.log(`✅ PageEditor: Pending content update completed for blockId='${blockId}'`);
        }
        
        console.log(`🎯 PageEditor: Clearing pending AI update`);
        setPendingAIUpdate(null);
      } else {
        console.log(`⏳ PageEditor: Block not yet available in page state, will retry on next render`);
        console.log(`⏳ PageEditor: Expected blockId: ${blockId}`);
        console.log(`⏳ PageEditor: Available blockIds:`, page.blocks.map(b => b.id));
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
  const handleMarkdownPaste = useCallback((markdownText: string, targetBlockId: string) => {
    console.log('🎯 PageEditor: Handling markdown paste for block:', targetBlockId);
    console.log('🎯 PageEditor: Markdown text:', markdownText);
    
    const parsedBlocks = parseMarkdownContent(markdownText);
    console.log('🎯 PageEditor: Parsed blocks:', parsedBlocks);
    
    if (parsedBlocks.length === 0) {
      console.log('🎯 PageEditor: No blocks parsed, returning');
      return;
    }
    
    // Helper function to attempt block processing with retries
    const attemptBlockProcessing = (retryCount = 0) => {
      const maxRetries = 5; // Shorter retry for paste operations
      
      // Verify the target block exists
      const targetBlockExists = page.blocks.some(block => block.id === targetBlockId);
      
      if (!targetBlockExists) {
        if (retryCount < maxRetries) {
          console.log(`🎯 PageEditor: Target block ${targetBlockId} not found for paste, retrying in 50ms (attempt ${retryCount + 1}/${maxRetries})`);
          setTimeout(() => attemptBlockProcessing(retryCount + 1), 50);
          return;
        } else {
          console.error('🎯 PageEditor: Target block does not exist for paste after max retries:', targetBlockId);
          return;
        }
      }
      
      console.log(`🎯 PageEditor: Target block ${targetBlockId} found after ${retryCount} retries, proceeding with paste processing`);
      
      const targetBlockIndex = page.blocks.findIndex(block => block.id === targetBlockId);
      if (targetBlockIndex === -1) {
        console.error('🎯 PageEditor: Could not find target block index for paste after retries');
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
    
    // Start the block processing attempt
    attemptBlockProcessing();
  }, [page.blocks, page.id, storageManager, loggedOnUpdatePage]);

  // Handle multiline results from trivial AI client (line-by-line block creation)
  const handleTrivialMultilineResult = useCallback((resultText: string, targetBlockId: string) => {
    console.log('🔥 === MULTILINE HANDLER CALLED ===');
    console.log('⚡ PageEditor: Handling trivial multiline result for block:', targetBlockId);
    console.log('⚡ PageEditor: Result text length:', resultText.length);
    console.log('⚡ PageEditor: Result text preview:', resultText.substring(0, 200) + '...');
    console.log('⚡ PageEditor: Current page.blocks count at handler start:', page.blocks.length);
    console.log('⚡ PageEditor: Current page.blocks IDs:', page.blocks.map(b => b.id));
    
    // Split by newlines to create individual blocks
    const lines = resultText.split('\n');
    console.log('⚡ PageEditor: Split into', lines.length, 'lines');
    console.log('⚡ PageEditor: Lines preview:', lines.slice(0, 5).map((line, i) => `${i}: "${line}"`));
    
    if (lines.length === 0) {
      console.log('⚡ PageEditor: No lines found, falling back to simple content');
      setPendingAIUpdate({ 
        blockId: targetBlockId, 
        content: resultText
      });
      return;
    }
    
    // OPTIMISTIC APPROACH: Create all blocks at once without waiting for target block
    console.log('⚡ PageEditor: Using optimistic multiline block creation');
    
    // We know the target block should be created at the end of current blocks
    // So we'll work with current page state and add the target block + new blocks
    const currentBlocks = [...page.blocks];
    const targetBlockIndex = currentBlocks.length; // Target block will be at the end
    
    console.log('⚡ PageEditor: Current blocks count:', currentBlocks.length);
    console.log('⚡ PageEditor: Target block will be at index:', targetBlockIndex);
    
    // Generate standard block IDs using the same format as normal blocks
    const generateStandardBlockId = (): string => {
      // Generate a random 9-character alphanumeric string (same format as normal blocks)
      const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
      let result = '';
      for (let i = 0; i < 9; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
      }
      return result;
    };

    // Create blocks directly in page state with standard IDs
    const allBlocks = [...currentBlocks]; // Start with existing blocks
    const createdBlockIds: string[] = []; // Track created block IDs
    
    lines.forEach((line, index) => {
      const trimmedLine = line.trim();
      
      // Determine block type based on content
      let blockType: Block['type'] = 'text';
      let blockContent = line; // Keep original spacing for text blocks
      
      // Check for markdown patterns
      if (trimmedLine.startsWith('## ')) {
        blockType = 'heading2';
        blockContent = trimmedLine.replace(/^##\s/, '');
      } else if (trimmedLine.startsWith('### ')) {
        blockType = 'heading3';
        blockContent = trimmedLine.replace(/^###\s/, '');
      } else if (trimmedLine.startsWith('# ')) {
        blockType = 'heading1';
        blockContent = trimmedLine.replace(/^#\s/, '');
      } else if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('* ') || trimmedLine.startsWith('+ ')) {
        blockType = 'bullet';
        blockContent = trimmedLine.replace(/^[-*+]\s/, '');
      } else if (/^\d+\.\s/.test(trimmedLine)) {
        blockType = 'numbered';
        blockContent = trimmedLine.replace(/^\d+\.\s/, '');
      } else if (trimmedLine.startsWith('> ')) {
        blockType = 'quote';
        blockContent = trimmedLine.replace(/^>\s/, '');
      } else if (trimmedLine === '---' || trimmedLine === '---') {
        blockType = 'divider';
        blockContent = '';
      } else {
        // Regular text block - preserve original spacing
        blockType = 'text';
        blockContent = line; // Keep original line with spacing
      }
      
      // For the first line, use the target block ID (already created by onAddBlock)
      // For subsequent lines, generate standard block IDs
      let blockId: string;
      if (index === 0) {
        blockId = targetBlockId;
      } else {
        // Generate a standard block ID (same format as normal blocks)
        blockId = generateStandardBlockId();
      }
      
      createdBlockIds.push(blockId);
      
      // Create the block object
      const block = {
        id: blockId,
        type: blockType,
        content: blockContent,
        order: targetBlockIndex + index,
        indentLevel: 0,
        properties: {},
        pageId: page.id
      };
      
      allBlocks.push(block);
      
      console.log(`⚡ PageEditor: Created block ${index + 1}/${lines.length}:`, {
        id: blockId,
        type: blockType,
        content: blockContent.substring(0, 30) + (blockContent.length > 30 ? '...' : ''),
        isTarget: index === 0,
        usedStandardId: index > 0
      });
    });
    
    // Reorder all blocks to have clean sequential orders
    const reorderedBlocks = allBlocks.map((block, index) => ({
      ...block,
      order: index
    }));
    
    console.log('⚡ PageEditor: Optimistically updating page with all multiline blocks');
    console.log('⚡ PageEditor: Total blocks:', reorderedBlocks.length);
    console.log('⚡ PageEditor: New blocks added:', lines.length);
    
    // Update page state with all blocks at once
    console.log('🔥 === ABOUT TO UPDATE PAGE STATE ===');
    console.log('⚡ PageEditor: Calling loggedOnUpdatePage with', reorderedBlocks.length, 'blocks');
    loggedOnUpdatePage({ blocks: reorderedBlocks });
    console.log('🔥 === PAGE STATE UPDATE COMPLETED ===');
    
    // Save all new blocks to storage directly (excluding the target block which was already created)
    const blocksToSave = reorderedBlocks.slice(targetBlockIndex + 1); // Skip the target block
    console.log('⚡ PageEditor: Saving', blocksToSave.length, 'new multiline blocks to storage');
    
    blocksToSave.forEach((block, index) => {
      setTimeout(async () => {
        console.log(`⚡ PageEditor: Saving multiline block ${block.id} to storage (${index + 1}/${blocksToSave.length})`);
        try {
          await storageManager.saveBlock(block, page.id);
          console.log(`✅ PageEditor: Multiline block ${block.id} saved to storage successfully`);
        } catch (error) {
          console.warn(`⚠️ PageEditor: Could not save multiline block ${block.id} to storage:`, error);
        }
      }, 100 * (index + 1)); // Staggered saves with delays
    });
    
  }, [page.blocks, page.id, storageManager, loggedOnUpdatePage, setPendingAIUpdate]);

  // Handle markdown results from trivial AI client
  const handleTrivialMarkdownResult = useCallback((markdownText: string, targetBlockId: string) => {
    console.log('⚡ PageEditor: Handling trivial markdown result for block:', targetBlockId);
    console.log('⚡ PageEditor: Trivial markdown text:', markdownText);
    
    // Use the same parsing logic as regular markdown paste
    const parsedBlocks = parseMarkdownContent(markdownText);
    console.log('⚡ PageEditor: Parsed trivial blocks:', parsedBlocks);
    
    if (parsedBlocks.length === 0) {
      console.log('⚡ PageEditor: No trivial blocks parsed, falling back to simple content');
      setPendingAIUpdate({ 
        blockId: targetBlockId, 
        content: markdownText
      });
      return;
    }
    
    // Helper function to attempt block processing with retries
    const attemptBlockProcessing = (retryCount = 0) => {
      const maxRetries = 10; // Maximum 10 retries (1 second total)
      
      // Verify the target block exists
      const targetBlockExists = page.blocks.some(block => block.id === targetBlockId);
      
      if (!targetBlockExists) {
        if (retryCount < maxRetries) {
          console.log(`⚡ PageEditor: Target block ${targetBlockId} not found, retrying in 100ms (attempt ${retryCount + 1}/${maxRetries})`);
          setTimeout(() => attemptBlockProcessing(retryCount + 1), 100);
          return;
        } else {
          console.error('⚡ PageEditor: Target block does not exist after max retries, falling back to pendingAIUpdate:', targetBlockId);
          // Fallback: use the pending update mechanism instead
          setPendingAIUpdate({ 
            blockId: targetBlockId, 
            content: markdownText
          });
          return;
        }
      }
      
      console.log(`⚡ PageEditor: Target block ${targetBlockId} found after ${retryCount} retries, proceeding with markdown processing`);
      
      const targetBlockIndex = page.blocks.findIndex(block => block.id === targetBlockId);
      if (targetBlockIndex === -1) {
        console.error('⚡ PageEditor: Could not find target block index for trivial result after retries');
        setPendingAIUpdate({ 
          blockId: targetBlockId, 
          content: markdownText
        });
        return;
      }

      // Update the target block with the first parsed block
      const firstBlock = parsedBlocks[0];
      console.log('⚡ PageEditor: Updating target block with trivial result:', firstBlock);
      
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
      
      // For multiple blocks, create additional blocks using onAddBlock
      if (parsedBlocks.length > 1) {
        // Create new blocks using onAddBlock for proper ID generation
        const newBlockIds: string[] = [];
        let lastBlockId = targetBlockId;
        
        parsedBlocks.slice(1).forEach((blockData, index) => {
          const newBlockId = onAddBlock(lastBlockId, blockData.type);
          newBlockIds.push(newBlockId);
          lastBlockId = newBlockId; // Update for next iteration
          
          console.log(`⚡ PageEditor: Created trivial block ${index + 1}/${parsedBlocks.length - 1} with ID: ${newBlockId}`);
        });
        
        console.log('⚡ PageEditor: Created trivial block IDs:', newBlockIds);
        
        // Update content for all created blocks (they already exist from onAddBlock calls)
        newBlockIds.forEach((blockId, index) => {
          const blockData = parsedBlocks[index + 1]; // Skip first block (already handled)
          setTimeout(() => {
            console.log(`⚡ PageEditor: Updating trivial block ${blockId} content (${index + 1}/${newBlockIds.length})`);
            onUpdateBlock(blockId, {
              type: blockData.type,
              content: blockData.content,
              indentLevel: blockData.indentLevel || 0
            });
            console.log(`✅ PageEditor: Trivial block ${blockId} content updated successfully`);
          }, 50 * (index + 1)); // Staggered updates
        });
      }
      
      // Update the target block with the first parsed block content
      console.log('⚡ PageEditor: Updating target block content');
      onUpdateBlock(targetBlockId, {
        type: firstBlock.type,
        content: firstBlock.content,
        indentLevel: firstBlock.indentLevel || 0
      });
    };
    
    // Start the block processing attempt
    attemptBlockProcessing();
  }, [page.blocks, page.id, storageManager, loggedOnUpdatePage, onAddBlock, onUpdateBlock]);

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
                    onFocusNextBlock={handleFocusNextBlock}
                    onFocusPreviousBlock={handleFocusPreviousBlock}
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
