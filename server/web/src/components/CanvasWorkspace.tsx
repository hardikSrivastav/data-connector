import { useState, useEffect } from 'react';
import { Page, Workspace, Block, ReasoningChainData } from '@/types';
import { agentClient, AgentQueryResponse } from '@/lib/agent-client';
import { useStorageManager } from '@/hooks/useStorageManager';
import { 
  BarChart3, 
  GitBranch, 
  Clock, 
  Database, 
  TrendingUp, 
  Eye, 
  Play,
  RotateCcw,
  Download,
  Share,
  Settings,
  Plus,
  AlertTriangle,
  Layout,
  Type,
  Table,
  BarChart2,
  Code,
  Quote,
  Minus,
  Hash
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ReasoningChain } from './ReasoningChain';
import { BlockEditor } from './BlockEditor';

interface CanvasWorkspaceProps {
  page: Page;
  workspace: Workspace;
  onNavigateBack: () => void;
  onUpdatePage: (updates: Partial<Page>) => void;
  onAddBlock?: (afterBlockId?: string, type?: Block['type']) => string;
  onUpdateBlock?: (blockId: string, updates: Partial<Block>) => void;
  onDeleteBlock?: (blockId: string) => void;
}

// Helper function to determine if a reasoning chain belongs to a specific canvas
const isChainRelevantToCanvas = (
  chain: ReasoningChainData, 
  canvasBlock: Block | undefined, 
  canvasPageId: string
): boolean => {
  if (!canvasBlock) return false;
  
  // Get canvas data for comparison
  const canvasData = canvasBlock.properties?.canvasData;
  
  // Method 1: Direct blockId match to canvas block
  if (chain.blockId === canvasBlock.id) {
    console.log(`🎯 Reasoning chain matched by blockId: ${chain.blockId} === ${canvasBlock.id}`);
    return true;
  }
  
  // Method 2: SessionId/threadId match
  if (chain.sessionId && canvasData?.threadId && chain.sessionId === canvasData.threadId) {
    console.log(`🎯 Reasoning chain matched by sessionId: ${chain.sessionId} === ${canvasData.threadId}`);
    return true;
  }
  
  // Method 3: Original query match (exact match)
  if (chain.originalQuery && canvasData?.originalQuery && chain.originalQuery === canvasData.originalQuery) {
    console.log(`🎯 Reasoning chain matched by originalQuery: "${chain.originalQuery}" === "${canvasData.originalQuery}"`);
    return true;
  }
  
  // Method 4: Check if chain's pageId matches this canvas workspace page
  if ((chain as any).pageId === canvasPageId) {
    console.log(`🎯 Reasoning chain matched by pageId: ${(chain as any).pageId} === ${canvasPageId}`);
    return true;
  }
  
  // Method 5: Check if chain's originalPageId matches canvas workspace page
  if ((chain as any).originalPageId === canvasPageId) {
    console.log(`🎯 Reasoning chain matched by originalPageId: ${(chain as any).originalPageId} === ${canvasPageId}`);
    return true;
  }
  
  console.log(`🎯 Reasoning chain NOT relevant:`, {
    chainBlockId: chain.blockId,
    canvasBlockId: canvasBlock.id,
    chainSessionId: chain.sessionId,
    canvasThreadId: canvasData?.threadId,
    chainQuery: chain.originalQuery?.substring(0, 50),
    canvasQuery: canvasData?.originalQuery?.substring(0, 50),
    chainPageId: (chain as any).pageId,
    chainOriginalPageId: (chain as any).originalPageId,
    canvasPageId
  });
  
  return false;
};

export const CanvasWorkspace = ({ 
  page, 
  workspace, 
  onNavigateBack, 
  onUpdatePage,
  onAddBlock,
  onUpdateBlock,
  onDeleteBlock
}: CanvasWorkspaceProps) => {
  const { storageManager } = useStorageManager({
    edition: 'enterprise',
    apiBaseUrl: import.meta.env.VITE_API_BASE || 'http://localhost:8787'
  });
  
  // Remove sidebar state since sidebar is removed
  const [selectedView, setSelectedView] = useState<'analysis' | 'data' | 'history' | 'reasoning'>('analysis');
  const [isQueryRunning, setIsQueryRunning] = useState(false);
  const [reasoningChains, setReasoningChains] = useState<Map<string, ReasoningChainData>>(new Map());
  const [incompleteChains, setIncompleteChains] = useState<Array<{ blockId: string; data: ReasoningChainData }>>();
  const [reasoningChainsLoaded, setReasoningChainsLoaded] = useState<Set<string>>(new Set());
  const [isLoadingReasoningChains, setIsLoadingReasoningChains] = useState(false);
  const [focusedBlockId, setFocusedBlockId] = useState<string | null>(null);
  const [showAddBlockMenu, setShowAddBlockMenu] = useState(false);

  // Helper function to filter blocks by view type for DISPLAY ONLY (not functionality restriction)
  const getBlocksForView = (view: string) => {
    const sortedBlocks = [...page.blocks].sort((a, b) => (a.order || 0) - (b.order || 0));
    
    switch (view) {
      case 'analysis':
        // Show text content, headings, quotes, and analysis-related blocks
        return sortedBlocks.filter(block => 
          ['heading1', 'heading2', 'heading3', 'text', 'quote', 'divider', 'code'].includes(block.type)
        );
      case 'data':
        // Show tables, stats, charts, and data-related blocks
        return sortedBlocks.filter(block => 
          ['table', 'stats', 'chart', 'graph', 'code', 'divider'].includes(block.type)
        );
      case 'history':
        // Show all blocks in chronological order
        return sortedBlocks;
      case 'reasoning':
        // Show ONLY blocks that actually have reasoning chains or AI-related content
        return sortedBlocks.filter(block => 
          block.properties?.reasoningChain || 
          block.properties?.canvasData?.reasoningChain
        );
      default:
        return sortedBlocks;
    }
  };

  // All block types are always available - no view restrictions
  const getAllAvailableBlockTypes = (): Array<{ type: Block['type']; label: string; icon: any }> => {
    return [
      { type: 'text' as const, label: 'Text', icon: Type },
      { type: 'heading1' as const, label: 'Heading 1', icon: Hash },
      { type: 'heading2' as const, label: 'Heading 2', icon: Hash },
      { type: 'heading3' as const, label: 'Heading 3', icon: Hash },
      { type: 'quote' as const, label: 'Quote', icon: Quote },
      { type: 'code' as const, label: 'Code', icon: Code },
      { type: 'table' as const, label: 'Table', icon: Table },
      { type: 'stats' as const, label: 'Stats', icon: BarChart2 },
      { type: 'divider' as const, label: 'Divider', icon: Minus }
    ];
  };

  // Helper function to handle block focus
  const handleBlockFocus = (blockId: string) => {
    setFocusedBlockId(blockId);
  };

  // Standard block creation - no view restrictions
  const handleAddBlock = (type: Block['type']) => {
    if (onAddBlock) {
      const newBlockId = onAddBlock(undefined, type);
      setFocusedBlockId(newBlockId);
      setShowAddBlockMenu(false);
    }
  };

  // Enhanced initialization to populate with canvas data and load reasoning chains
  useEffect(() => {
    console.log('🎨 CanvasWorkspace: Enhanced initialization starting...');
    console.log('🎨 CanvasWorkspace: Page blocks count:', page.blocks.length);
    
    const initializeCanvasWorkspace = async () => {
      // Prevent repeated loading for the same page
      const initPageKey = `${page.id}_${workspace.pages.length}`;
      if (reasoningChainsLoaded.has(initPageKey)) {
        console.log(`🧠 CanvasWorkspace: Skipping initialization - already loaded for page ${page.id}`);
        return;
      }

      if (isLoadingReasoningChains) {
        console.log(`🧠 CanvasWorkspace: Skipping initialization - already in progress`);
        return;
      }

      setIsLoadingReasoningChains(true);
      
      // Check if page is empty but has canvas data available, and populate it
    const hasOnlyBasicContent = page.blocks.length <= 1 || 
      (page.blocks.length === 1 && page.blocks[0].type === 'heading1');
    
    if (hasOnlyBasicContent) {
      console.log('🎨 CanvasWorkspace: Page appears empty, looking for canvas data...');
      
      // Find the CanvasBlock that references this page
      const canvasBlock = workspace.pages.flatMap(p => p.blocks).find(block => 
        block.type === 'canvas' && 
        block.properties?.canvasPageId === page.id &&
        block.properties?.canvasData
      );
      
      if (canvasBlock?.properties?.canvasData) {
        console.log('🎯 CanvasWorkspace: Found canvas block with data, checking if it still exists...');
        
        // Double-check that the canvas block still exists in its page
        const canvasBlockStillExists = workspace.pages.some(p => 
          p.blocks.some(b => b.id === canvasBlock.id && b.type === 'canvas')
        );
        
        if (canvasBlockStillExists) {
          console.log('✅ CanvasWorkspace: Canvas block still exists, populating page...');
          const canvasData = canvasBlock.properties.canvasData;
          
          // Build blocks from canvas data
          const blocks = [];
          let nextOrder = 0;
          
          // Add main heading (or keep existing if present)
          const existingHeading = page.blocks.find(b => b.type === 'heading1');
          if (existingHeading) {
            blocks.push(existingHeading);
            nextOrder = 1;
          } else {
            blocks.push({
              id: `heading_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'heading1' as const,
              content: page.title || 'Canvas Analysis',
              order: nextOrder++
            });
          }
          
          // Add analysis if available
          if (canvasData.fullAnalysis) {
            blocks.push({
              id: `analysis_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'text' as const,
              content: canvasData.fullAnalysis,
              order: nextOrder++
            });
          }
          
          // Add table if available  
          if (canvasData.fullData && canvasData.fullData.headers && canvasData.fullData.rows) {
            blocks.push({
              id: `table_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'table' as const,
              content: '',
              order: nextOrder++,
              properties: {
                tableData: {
                  headers: canvasData.fullData.headers,
                  data: canvasData.fullData.rows
                }
              }
            });
          }
          
          // Add SQL query if available
          if (canvasData.sqlQuery) {
            blocks.push({
              id: `sql_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'code' as const,
              content: canvasData.sqlQuery,
              order: nextOrder++
            });
          }
          
          // Add divider for future analyses
          blocks.push({
            id: `divider_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type: 'divider' as const,
            content: '---',
            order: nextOrder++
          });
          
          console.log(`✅ CanvasWorkspace: Populating page with ${blocks.length} blocks from canvas data`);
          
          // Update the page with the populated blocks
          onUpdatePage({ blocks });
          }
        }
      }

      // Load reasoning chains from server API 
      const chains = new Map<string, ReasoningChainData>();
      const incomplete: Array<{ blockId: string; data: ReasoningChainData }> = [];
      
      // Find the original CanvasBlock that references this workspace page
      const originalCanvasBlock = workspace.pages.flatMap(p => p.blocks).find(block => 
        block.type === 'canvas' && 
        block.properties?.canvasPageId === page.id
      );
      
      // Get the original page ID (where the CanvasBlock lives)
      const originalPageId = originalCanvasBlock 
        ? workspace.pages.find(p => p.blocks.some(b => b.id === originalCanvasBlock.id))?.id
        : null;
      
      console.log(`🧠 CanvasWorkspace: Found original canvas block:`, {
        blockId: originalCanvasBlock?.id,
        originalPageId,
        currentPageId: page.id,
        threadId: originalCanvasBlock?.properties?.canvasData?.threadId,
        originalQuery: originalCanvasBlock?.properties?.canvasData?.originalQuery
      });
      
      // Load reasoning chains from both current page and original page
      const pageIdsToCheck = [page.id];
      if (originalPageId && originalPageId !== page.id) {
        pageIdsToCheck.push(originalPageId);
      }
      
      for (const pageId of pageIdsToCheck) {
        try {
          console.log(`🧠 CanvasWorkspace: Loading reasoning chains from server for page ${pageId}`);
          const serverReasoningChains = await storageManager.getReasoningChainsForPage(pageId);
          console.log(`🧠 CanvasWorkspace: Found ${serverReasoningChains.length} reasoning chains from server for page ${pageId}`);
          
          serverReasoningChains.forEach(chain => {
            if (chain.sessionId) {
              const chainKey = chain.blockId || chain.sessionId; // Use blockId if available, otherwise sessionId
              
              // Only add if not already loaded (avoid duplicates)
              if (!chains.has(chainKey)) {
                // Filter reasoning chains to only include ones related to this specific canvas
                const isRelevantChain = isChainRelevantToCanvas(chain, originalCanvasBlock, page.id);
                
                if (isRelevantChain) {
                  chains.set(chainKey, chain);
                  console.log(`🧠 CanvasWorkspace: Loaded relevant reasoning chain ${chain.sessionId} from page ${pageId}, events: ${chain.events?.length || 0}, complete: ${chain.isComplete}`);
                  
                  // Check if this is an incomplete chain
                  if (!chain.isComplete && chain.status === 'streaming') {
                    incomplete.push({ blockId: chainKey, data: chain });
                  }
                } else {
                  console.log(`🧠 CanvasWorkspace: Skipping irrelevant reasoning chain ${chain.sessionId} for this canvas`);
                }
              }
            }
          });
        } catch (error) {
          console.error(`❌ CanvasWorkspace: Failed to load reasoning chains from server for page ${pageId}:`, error);
        }
      }
      
      // Fallback: Also check for reasoning chains in block properties (legacy support)
      // Check current page blocks
      page.blocks.forEach(block => {
        // Check for reasoning chains in block properties
        if (block.properties?.reasoningChain) {
          const reasoningData = block.properties.reasoningChain as ReasoningChainData;
          console.log(`🧠 CanvasWorkspace: Found legacy reasoning chain in current page block ${block.id}, events: ${reasoningData.events?.length || 0}, complete: ${reasoningData.isComplete}`);
          
          // Only add if not already loaded from server and is relevant to this canvas
          if (!chains.has(block.id)) {
            const isRelevant = isChainRelevantToCanvas(reasoningData, originalCanvasBlock, page.id);
            if (isRelevant) {
              chains.set(block.id, reasoningData);
              
              // Check if this is an incomplete chain
              if (!reasoningData.isComplete && reasoningData.status === 'streaming') {
                incomplete.push({ blockId: block.id, data: reasoningData });
              }
            }
          }
        }
        
        // Also check legacy canvas data format
        if (block.properties?.canvasData?.reasoningChain) {
          const legacyReasoningData = block.properties.canvasData.reasoningChain;
          console.log(`🧠 CanvasWorkspace: Found legacy canvas reasoning chain for current page block ${block.id}`);
          
          // Only add if not already loaded from server and is relevant to this canvas
          if (!chains.has(block.id)) {
            // Convert legacy format to new format
            const convertedData: ReasoningChainData = {
              events: legacyReasoningData || [],
              originalQuery: block.properties.canvasData.originalQuery || 'Legacy Query',
              sessionId: block.properties.canvasData.threadId,
              isComplete: true, // Assume legacy chains are complete
              lastUpdated: new Date().toISOString(),
              status: 'completed',
              progress: 1.0
            };
            
            const isRelevant = isChainRelevantToCanvas(convertedData, originalCanvasBlock, page.id);
            if (isRelevant) {
              chains.set(block.id, convertedData);
            }
          }
        }
      });
      
      // Also check the original canvas block for reasoning chains
      if (originalCanvasBlock?.properties?.canvasData?.reasoningChain) {
        const originalReasoningData = originalCanvasBlock.properties.canvasData.reasoningChain;
        console.log(`🧠 CanvasWorkspace: Found reasoning chain in original canvas block ${originalCanvasBlock.id}`);
        
        // Only add if not already loaded
        if (!chains.has(originalCanvasBlock.id)) {
          // Handle both new object format and old array format
          let convertedData: ReasoningChainData;
          
          if (typeof originalReasoningData === 'object' && originalReasoningData !== null && !Array.isArray(originalReasoningData) && 'events' in originalReasoningData) {
            // New format - use as is
            convertedData = originalReasoningData as ReasoningChainData;
          } else if (Array.isArray(originalReasoningData)) {
            // Old array format - convert
            convertedData = {
              events: originalReasoningData,
              originalQuery: originalCanvasBlock.properties.canvasData.originalQuery || 'Canvas Query',
              sessionId: originalCanvasBlock.properties.canvasData.threadId,
              isComplete: true, // Assume legacy chains are complete
              lastUpdated: new Date().toISOString(),
              status: 'completed',
              progress: 1.0
            };
          } else {
            return; // Skip invalid format
          }
          
          // This should always be relevant since it's from the original canvas block itself
          // But let's still check for consistency
          const isRelevant = isChainRelevantToCanvas(convertedData, originalCanvasBlock, page.id);
          if (isRelevant) {
            chains.set(originalCanvasBlock.id, convertedData);
            
            // Check if this is an incomplete chain
            if (!convertedData.isComplete && convertedData.status === 'streaming') {
              incomplete.push({ blockId: originalCanvasBlock.id, data: convertedData });
            }
          }
        }
      }
      
      console.log(`🧠 CanvasWorkspace: Total loaded ${chains.size} reasoning chains, ${incomplete.length} incomplete`);
      setReasoningChains(chains);
      setIncompleteChains(incomplete);
      
      // Mark this page as loaded
      const loadedPageKey = `${page.id}_${workspace.pages.length}`;
      setReasoningChainsLoaded(prev => {
        const newSet = new Set(prev);
        newSet.add(loadedPageKey);
        return newSet;
      });
      
      setIsLoadingReasoningChains(false);
    };

    // Debounce the initialization to prevent rapid successive calls
    const debounceTimeout = setTimeout(() => {
      initializeCanvasWorkspace();
    }, 300); // 300ms debounce
    
    return () => clearTimeout(debounceTimeout);
  }, [page.id, workspace.pages.length, onUpdatePage, reasoningChainsLoaded, isLoadingReasoningChains]); // Removed page.blocks.length dependency

  // Enhanced query handler with reasoning chain recovery
  const handleRunNewQuery = async (queryText?: string) => {
    const finalQuery = queryText || prompt('Enter your SQL query or natural language question:');
    if (!finalQuery || finalQuery.trim() === '') return;
    
    console.log('🚀 CanvasWorkspace: Executing new query:', finalQuery);
      setIsQueryRunning(true);
      
    try {
      // Add a timestamp heading for this analysis
      const timestamp = new Date().toLocaleString();
      const headingId = onAddBlock ? onAddBlock(undefined, 'heading2') : null;
      if (headingId && onUpdateBlock) {
        onUpdateBlock(headingId, {
          content: `Analysis - ${timestamp}`
        });
      }
      
      // Add loading indicator
      const loadingId = onAddBlock ? onAddBlock(undefined, 'text') : null;
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: '🔄 Running query and analyzing results...'
        });
      }
      
      // Execute query via agent API (this will trigger reasoning chain persistence in PageEditor)
      const response = await agentClient.query({
        question: finalQuery.trim(),
        analyze: true
      });
      
      console.log('✅ CanvasWorkspace: Query completed successfully');
      console.log('📊 CanvasWorkspace: Response data:', {
        rowsCount: response.rows?.length || 0,
        hasAnalysis: !!response.analysis,
        sql: response.sql?.substring(0, 100) + '...'
      });
      
      // Update loading text with query details
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: `**Query:** ${response.sql || finalQuery}`
        });
      }
      
      // Add analysis summary
      if (response.analysis) {
        const analysisId = onAddBlock ? onAddBlock(undefined, 'text') : null;
        if (analysisId && onUpdateBlock) {
          onUpdateBlock(analysisId, {
            content: response.analysis
          });
        }
      }
      
      // Add query results as table with proper data conversion
      if (response.rows && response.rows.length > 0) {
        console.log('📊 CanvasWorkspace: Converting query results to table...');
        
        // Convert response data, handling MongoDB objects, Decimal and other special types
        const convertValue = (value: any): string => {
          if (value === null || value === undefined) return '';
          
          // Handle Decimal objects
          if (typeof value === 'object' && value.constructor && value.constructor.name === 'Decimal') {
            return value.toString();
          }
          
          // Handle Date objects
          if (value instanceof Date) return value.toISOString();
          
          // Handle MongoDB ObjectId
          if (typeof value === 'object' && value.constructor && value.constructor.name === 'ObjectId') {
            return value.toString();
          }
          
          // Handle arrays - show as JSON or comma-separated for simple arrays
          if (Array.isArray(value)) {
            if (value.length === 0) return '[]';
            if (value.every(item => typeof item === 'string' || typeof item === 'number')) {
              return value.join(', ');
            }
            return JSON.stringify(value);
          }
          
          // Handle complex objects (MongoDB documents, nested objects)
          if (typeof value === 'object' && value !== null) {
            // For simple key-value objects, show as JSON
            try {
              return JSON.stringify(value);
            } catch (e) {
              // Fallback if JSON.stringify fails
              return Object.prototype.toString.call(value);
            }
          }
          
          // Handle primitives (string, number, boolean)
          return String(value);
        };
        
        // Get headers from first row
        const headers = Object.keys(response.rows[0]);
        console.log('📊 CanvasWorkspace: Table headers:', headers);
        
        // Convert rows to string arrays, handling special types
        const tableData = response.rows.map(row => 
          headers.map(header => convertValue(row[header]))
        );
        
        console.log('📊 CanvasWorkspace: Table data sample:', {
          headers,
          firstRow: tableData[0],
          totalRows: tableData.length
        });
        
        const tableId = onAddBlock ? onAddBlock(undefined, 'table') : null;
        if (tableId && onUpdateBlock) {
          onUpdateBlock(tableId, {
            content: 'Query Results',
                properties: {
              tableData: {
                rows: response.rows.length,
                cols: headers.length,
                headers: headers,
                data: tableData
              }
            }
          });
          
          console.log('✅ CanvasWorkspace: Table block created successfully with ID:', tableId);
        }
      }
      
      // Add divider for next analysis
      onAddBlock?.(undefined, 'divider');
      
    } catch (error) {
      console.error('❌ CanvasWorkspace: Query failed:', error);
      
      // Show error
      const errorId = onAddBlock ? onAddBlock(undefined, 'quote') : null;
      if (errorId && onUpdateBlock) {
        onUpdateBlock(errorId, {
          content: `❌ **Error:** ${error.message || 'Query execution failed'}`
        });
      }
    } finally {
      setIsQueryRunning(false);
    }
  };

  // Recovery handlers
  const handleResumeQuery = async (query: string) => {
    console.log('🔄 CanvasWorkspace: Resuming interrupted query:', query);
    await handleRunNewQuery(query);
  };

  const handleRetryQuery = async (query: string) => {
    console.log('🔄 CanvasWorkspace: Retrying failed query:', query);
    await handleRunNewQuery(query);
  };

  return (
    <div className="flex h-screen w-full bg-white dark:bg-gray-900">
      {/* Main Content Area - Full Width */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onNavigateBack}
                className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
              >
                ← Back to Page
              </Button>
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{page.title}</h1>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => handleRunNewQuery()}
                disabled={isQueryRunning}
              >
                <Play className="h-4 w-4 mr-2" />
                {isQueryRunning ? 'Running...' : 'New Query'}
              </Button>
              <Button size="sm" variant="outline">
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
              <Button size="sm" variant="outline">
                <Share className="h-4 w-4 mr-2" />
                Share
              </Button>
              <Button size="sm" variant="ghost">
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* View Tabs */}
          <div className="flex border-t border-gray-200 dark:border-gray-700">
            {[
              { id: 'analysis', label: 'Analysis', icon: Eye },
              { id: 'data', label: 'Data', icon: Database },
              { id: 'history', label: 'History', icon: Clock },
              { id: 'reasoning', label: 'AI Reasoning', icon: GitBranch }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  selectedView === id
                    ? "border-blue-500 dark:border-blue-400 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                )}
                onClick={() => setSelectedView(id as any)}
              >
                <Icon className="h-4 w-4" />
                {label}
                              {/* Show count of relevant blocks for each tab */}
              <span className="ml-1 px-1.5 py-0.5 text-xs bg-gray-500 text-white rounded-full">
                {getBlocksForView(id).length}
              </span>
              {id === 'reasoning' && incompleteChains && incompleteChains.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-yellow-500 text-white rounded-full">
                  {incompleteChains.length}
                </span>
              )}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-6xl mx-auto">
            {/* View-specific header and add block controls */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {selectedView === 'analysis' && 'Analysis Workspace'}
                  {selectedView === 'data' && 'Data Workspace'}
                  {selectedView === 'history' && 'Complete History'}
                  {selectedView === 'reasoning' && 'AI Reasoning Workspace'}
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {selectedView === 'analysis' && 'View and organize your analysis content'}
                  {selectedView === 'data' && 'View tables, stats, and data visualizations'}
                  {selectedView === 'history' && 'View all content chronologically'}
                  {selectedView === 'reasoning' && 'View AI reasoning chains and thought processes'}
                </p>
              </div>
              
              {/* Add Block Button */}
              <div className="relative">
                <Button 
                  onClick={() => setShowAddBlockMenu(!showAddBlockMenu)}
                  size="sm"
                  className="gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Add Block
                </Button>
                
                {/* Add Block Dropdown */}
                {showAddBlockMenu && (
                  <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
                    <div className="p-2">
                      <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2 px-2">
                        Add Block
                      </div>
                      {getAllAvailableBlockTypes().map(({ type, label, icon: Icon }) => (
                        <button
                          key={type}
                          onClick={() => handleAddBlock(type)}
                          className="w-full flex items-center gap-2 px-2 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                        >
                          <Icon className="h-4 w-4" />
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>



            {/* Blocks Content */}
            <div className="space-y-4">
              {(() => {
                const blocksForView = getBlocksForView(selectedView);
                
                console.log(`🎯 Rendering ${selectedView} view:`, {
                  selectedView,
                  totalBlocks: page.blocks.length,
                  filteredBlocks: blocksForView.length,
                  blockTypes: blocksForView.map(b => b.type)
                });
                
                // Special content for reasoning view
                const reasoningContent = selectedView === 'reasoning' && (
                  <>
                    {/* Incomplete chains notification */}
                    {incompleteChains && incompleteChains.length > 0 && (
                      <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4 mb-6">
                        <div className="flex items-center gap-2 mb-2">
                          <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                          <h3 className="font-medium text-yellow-900 dark:text-yellow-100">Incomplete Queries Found</h3>
                        </div>
                        <p className="text-sm text-yellow-800 dark:text-yellow-200 mb-3">
                          {incompleteChains.length} query{incompleteChains.length !== 1 ? 'ies were' : ' was'} interrupted. You can resume or retry them.
                        </p>
                      </div>
                    )}

                    {/* Reasoning chains display */}
                    {Array.from(reasoningChains.entries()).length > 0 && (
                      <div className="space-y-4 mb-8">
                        <h3 className="text-md font-medium text-gray-900 dark:text-gray-100">
                          AI Reasoning Chains ({reasoningChains.size})
                        </h3>
                        {Array.from(reasoningChains.entries()).map(([blockId, reasoningData]) => (
                          <ReasoningChain
                            key={blockId}
                            reasoningData={reasoningData}
                            title={`Block ${blockId.substring(0, 8)} - AI Reasoning`}
                            collapsed={false}
                            showRecoveryOptions={!reasoningData.isComplete}
                            onResumeQuery={handleResumeQuery}
                            onRetryQuery={handleRetryQuery}
                          />
                        ))}
                      </div>
                    )}
                  </>
                );

                // Show reasoning content first if in reasoning view
                const contentToRender = [
                  ...(reasoningContent ? [reasoningContent] : []),
                  ...blocksForView.map((block) => (
                    <div key={block.id} className="group">
                      <BlockEditor
                        block={block}
                        onUpdate={(updates) => onUpdateBlock?.(block.id, updates)}
                        onAddBlock={(type) => onAddBlock?.(block.id, type)}
                        onDeleteBlock={() => onDeleteBlock?.(block.id)}
                        onFocus={() => handleBlockFocus(block.id)}
                        isFocused={focusedBlockId === block.id}
                        onMoveUp={() => {
                          // TODO: Implement move up functionality
                          console.log('Move up block', block.id);
                        }}
                        onMoveDown={() => {
                          // TODO: Implement move down functionality
                          console.log('Move down block', block.id);
                        }}
                        workspace={workspace}
                        page={page}
                        onNavigateToPage={(pageId) => {
                          // TODO: Implement navigation to specific page
                          console.log('Navigate to page:', pageId);
                        }}
                      />
                    </div>
                  ))
                ];

                // Show empty state only if no content at all
                if (contentToRender.length === 0 || (blocksForView.length === 0 && !reasoningContent)) {
                  return (
                    <div className="text-center py-12">
                      <Layout className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
                        No {selectedView} content yet
                      </h3>
                      <p className="text-gray-500 dark:text-gray-400 mb-6">
                        {selectedView === 'analysis' && 'This view shows text, headings, quotes, and analysis content'}
                        {selectedView === 'data' && 'This view shows tables, stats, and data visualizations'}
                        {selectedView === 'history' && 'This view shows all content chronologically'}
                        {selectedView === 'reasoning' && 'This view shows AI reasoning and thought processes'}
                      </p>
                      <Button onClick={() => setShowAddBlockMenu(true)}>
                        <Plus className="h-4 w-4 mr-2" />
                        Add Content
                      </Button>
                    </div>
                  );
                }

                return contentToRender;
              })()}
            </div>

            {/* Quick Actions for New Query */}
            {selectedView === 'analysis' && (
              <div className="mt-8 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Quick Actions</h3>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => handleRunNewQuery()}>
                    <Play className="h-4 w-4 mr-2" />
                    Run New Query
                  </Button>
                  <Button size="sm" variant="outline">
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Refresh Data
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Click outside to close add block menu */}
          {showAddBlockMenu && (
            <div
              className="fixed inset-0 z-40"
              onClick={() => setShowAddBlockMenu(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}; 