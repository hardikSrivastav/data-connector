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
  ChevronRight,
  ChevronDown,
  Play,
  RotateCcw,
  Filter,
  Search,
  Download,
  Share,
  Settings,
  Plus,
  AlertTriangle
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import { TableDisplay } from './TableDisplay';
import { ReasoningChain } from './ReasoningChain';

interface CanvasWorkspaceProps {
  page: Page;
  workspace: Workspace;
  onNavigateBack: () => void;
  onUpdatePage: (updates: Partial<Page>) => void;
  onAddBlock?: (afterBlockId?: string, type?: Block['type']) => string;
  onUpdateBlock?: (blockId: string, updates: Partial<Block>) => void;
  onDeleteBlock?: (blockId: string) => void;
}

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
  
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedView, setSelectedView] = useState<'analysis' | 'data' | 'history' | 'reasoning'>('analysis');
  const [isQueryRunning, setIsQueryRunning] = useState(false);
  const [reasoningChains, setReasoningChains] = useState<Map<string, ReasoningChainData>>(new Map());
  const [incompleteChains, setIncompleteChains] = useState<Array<{ blockId: string; data: ReasoningChainData }>>();

  // Enhanced initialization to populate with canvas data and load reasoning chains
  useEffect(() => {
    console.log('🎨 CanvasWorkspace: Enhanced initialization starting...');
    console.log('🎨 CanvasWorkspace: Page blocks count:', page.blocks.length);
    
    const initializeCanvasWorkspace = async () => {
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

      // Load reasoning chains from blocks
      const chains = new Map<string, ReasoningChainData>();
      const incomplete: Array<{ blockId: string; data: ReasoningChainData }> = [];
      
      page.blocks.forEach(block => {
        // Check for reasoning chains in block properties
        if (block.properties?.reasoningChain) {
          const reasoningData = block.properties.reasoningChain as ReasoningChainData;
          console.log(`🧠 CanvasWorkspace: Found reasoning chain for block ${block.id}, events: ${reasoningData.events?.length || 0}, complete: ${reasoningData.isComplete}`);
          
          chains.set(block.id, reasoningData);
          
          // Check if this is an incomplete chain
          if (!reasoningData.isComplete && reasoningData.status === 'streaming') {
            incomplete.push({ blockId: block.id, data: reasoningData });
          }
        }
        
        // Also check legacy canvas data format
        if (block.properties?.canvasData?.reasoningChain) {
          const legacyReasoningData = block.properties.canvasData.reasoningChain;
          console.log(`🧠 CanvasWorkspace: Found legacy reasoning chain for block ${block.id}`);
          
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
          
          chains.set(block.id, convertedData);
      }
      });
      
      console.log(`🧠 CanvasWorkspace: Loaded ${chains.size} reasoning chains, ${incomplete.length} incomplete`);
      setReasoningChains(chains);
      setIncompleteChains(incomplete);
    };

    initializeCanvasWorkspace();
  }, [page.id, page.blocks.length, workspace.pages, onUpdatePage]);

  // Get analysis data from page blocks
  const getAnalysisData = () => {
    const headingBlocks = page.blocks.filter(b => b.type.startsWith('heading'));
    const textBlocks = page.blocks.filter(b => b.type === 'text');
    const tableBlocks = page.blocks.filter(b => b.type === 'table');
    const quoteBlocks = page.blocks.filter(b => b.type === 'quote');

    // Get current analysis summary from text blocks
    const currentAnalysis = textBlocks.length > 0 
      ? textBlocks[textBlocks.length - 1].content
      : 'No analysis available yet. Run a query to get started.';

    // Get current data from table blocks
    const currentTable = tableBlocks.length > 0 
      ? tableBlocks[tableBlocks.length - 1]
      : null;

    // Generate stats from blocks
    const stats = [
      { label: 'TOTAL BLOCKS', value: page.blocks.length.toString() },
      { label: 'ANALYSIS SECTIONS', value: headingBlocks.length.toString() },
      { label: 'DATA TABLES', value: tableBlocks.length.toString() },
      { label: 'KEY INSIGHTS', value: quoteBlocks.length.toString() },
      { label: 'REASONING CHAINS', value: reasoningChains.size.toString() }
    ];

    return {
      currentAnalysis,
      currentTable,
      stats,
      hasData: tableBlocks.length > 0,
      analysisHistory: textBlocks
    };
  };

  const analysisData = getAnalysisData();

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
        
        // Convert response data, handling Decimal and other special types
        const convertValue = (value: any): string => {
          if (value === null || value === undefined) return '';
          if (typeof value === 'object' && value.constructor && value.constructor.name === 'Decimal') {
            return value.toString();
          }
          if (value instanceof Date) return value.toISOString();
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
    <div className="flex h-screen bg-white dark:bg-gray-900">
      {/* Sidebar - Analysis History */}
      <div className={cn(
        "border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 transition-all duration-200",
        sidebarCollapsed ? "w-12" : "w-80"
      )}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="h-8 w-8 p-0"
            >
              {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
            {!sidebarCollapsed && (
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                <span className="font-medium text-sm text-gray-900 dark:text-gray-100">Analysis History</span>
              </div>
            )}
          </div>
        </div>

        {!sidebarCollapsed && (
          <>
            {/* Canvas Info */}
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                <h2 className="font-semibold text-gray-900 dark:text-gray-100">{page.title}</h2>
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                <div>Status: <span className="font-medium text-green-600 dark:text-green-400">Ready</span></div>
                <div>Blocks: {page.blocks.length}</div>
                <div>Reasoning Chains: {reasoningChains.size}</div>
                <div>Created: {new Date(page.createdAt).toLocaleDateString()}</div>
              </div>
              
              {/* Incomplete queries alert */}
              {incompleteChains && incompleteChains.length > 0 && (
                <div className="mt-3 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded text-xs">
                  <div className="flex items-center gap-1 text-yellow-800 dark:text-yellow-200">
                    <AlertTriangle className="h-3 w-3" />
                    {incompleteChains.length} incomplete queries found
                  </div>
                </div>
              )}
            </div>

            {/* Search */}
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
                <Input
                  placeholder="Search analysis..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-8 text-sm"
                />
              </div>
            </div>

            {/* Analysis Sections */}
            <div className="flex-1 overflow-y-auto">
              <div className="p-4">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-3">Analysis Sections</h3>
                <div className="space-y-2">
                  {page.blocks
                    .filter(block => block.type.startsWith('heading'))
                    .map((block, index) => (
                      <div
                        key={block.id}
                        className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                          <div className="w-2 h-2 rounded-full bg-blue-500 dark:bg-blue-400" />
                          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{block.content || `Section ${index + 1}`}</span>
                      </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {new Date().toLocaleString()}
                      </div>
                      </div>
                    ))}
                  
                  {page.blocks.filter(block => block.type.startsWith('heading')).length === 0 && (
                    <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                      No analysis sections yet. Run a query to get started.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Main Content Area */}
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
          {selectedView === 'analysis' && (
            <div className="max-w-4xl mx-auto space-y-6">
              {/* Current Analysis Summary */}
              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Eye className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  <h2 className="text-lg font-semibold text-blue-900 dark:text-blue-100">Current Analysis</h2>
                </div>
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown>{analysisData.currentAnalysis}</ReactMarkdown>
                </div>
              </div>

              {/* Key Statistics */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {analysisData.stats.map((stat, index) => (
                  <div key={index} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{stat.label}</div>
                    <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{stat.value}</div>
                  </div>
                ))}
              </div>

              {/* Quick Actions */}
                <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Quick Actions</h3>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => handleRunNewQuery()}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Analysis
                  </Button>
                  <Button size="sm" variant="outline">
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Refresh Data
                  </Button>
                </div>
                </div>
            </div>
          )}

          {selectedView === 'data' && (
            <div className="max-w-6xl mx-auto">
              {analysisData.currentTable ? (
              <TableDisplay
                headers={analysisData.currentTable.properties?.tableData?.headers || []}
                rows={analysisData.currentTable.properties?.tableData?.data || []}
                totalRows={analysisData.currentTable.properties?.tableData?.data?.length || 0}
                title="Latest Query Results"
                showControls={true}
                maxRows={50}
                onDownload={() => {
                  console.log('Download CSV');
                }}
                onFilter={() => {
                  console.log('Filter data');
                }}
              />
              ) : (
                <div className="text-center py-12">
                  <Database className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Data Available</h3>
                  <p className="text-gray-500 dark:text-gray-400 mb-6">Run a query to see data results here.</p>
                  <Button onClick={() => handleRunNewQuery()}>
                    <Play className="h-4 w-4 mr-2" />
                    Run Query
                  </Button>
              </div>
              )}
            </div>
          )}

          {selectedView === 'history' && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Analysis History</h2>
              <div className="space-y-4">
                {analysisData.analysisHistory.length > 0 ? (
                  analysisData.analysisHistory.map((block, index) => (
                    <div key={block.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-6 bg-white dark:bg-gray-800">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                          <div className="w-3 h-3 rounded-full bg-blue-500 dark:bg-blue-400" />
                          <h3 className="font-medium text-gray-900 dark:text-gray-100">Analysis Step {index + 1}</h3>
                      </div>
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                          {new Date().toLocaleString()}
                      </span>
                    </div>
                    
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <ReactMarkdown>{block.content}</ReactMarkdown>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-12">
                    <Clock className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Analysis History</h3>
                    <p className="text-gray-500 dark:text-gray-400 mb-6">Your analysis steps will appear here as you work.</p>
                    <Button onClick={() => handleRunNewQuery()}>
                      <Play className="h-4 w-4 mr-2" />
                      Start Analysis
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}

          {selectedView === 'reasoning' && (
            <div className="max-w-4xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Reasoning Chains</h2>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {reasoningChains.size} total chain{reasoningChains.size !== 1 ? 's' : ''}
                </div>
              </div>
              
              {/* Incomplete chains notification */}
              {incompleteChains && incompleteChains.length > 0 && (
                <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
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
              {Array.from(reasoningChains.entries()).length > 0 ? (
                <div className="space-y-4">
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
              ) : (
                    <div className="text-center py-12">
                      <GitBranch className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No AI Reasoning Available</h3>
                      <p className="text-gray-500 dark:text-gray-400 mb-6">
                        The AI reasoning chain will appear here after running queries. 
                        This shows how the AI thinks through problems step by step.
                      </p>
                  <Button onClick={() => handleRunNewQuery()}>
                        <Play className="h-4 w-4 mr-2" />
                        Run Query to See Reasoning
                      </Button>
                    </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}; 