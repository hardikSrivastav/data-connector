import { useState, useEffect } from 'react';
import { Block, Page, Workspace } from '@/types';
import { BarChart3, ChevronRight, Maximize2, Eye, Database, TrendingUp, Activity, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import { TableDisplay } from './TableDisplay';
import { ReasoningChain } from './ReasoningChain';

interface CanvasBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
  workspace: Workspace;
  page: Page;
  onNavigateToPage?: (pageId: string) => void;
  onCreateCanvasPage?: (canvasData: any) => Promise<string>;
}

export const CanvasBlock = ({ 
  block, 
  onUpdate, 
  isFocused, 
  workspace, 
  page,
  onNavigateToPage,
  onCreateCanvasPage
}: CanvasBlockProps) => {
  // Simplified canvas data - just page reference and name
  const canvasPageId = block.properties?.canvasPageId;
  const threadName = block.content || block.properties?.threadName || '';
  const [showNameEditor, setShowNameEditor] = useState(!threadName);
  const [tempName, setTempName] = useState(threadName);

  useEffect(() => {
    if (block.content) {
      setTempName(block.content);
      setShowNameEditor(false);
    }
  }, [block.content]);

  // Find the canvas page in workspace
  const canvasPage = canvasPageId ? workspace.pages.find(p => p.id === canvasPageId) : null;

  // Generate preview data dynamically from canvas page blocks OR canvas data
  const generatePreview = () => {
    // First try to get preview from canvasData if available (for immediate display on reload)
    const canvasData = block.properties?.canvasData;
    if (canvasData && (canvasData.fullAnalysis || canvasData.fullData || canvasData.sqlQuery)) {
      console.log('🎯 CanvasBlock: Generating preview from canvasData properties');
      console.log('🎯 CanvasBlock: canvasData structure:', {
        hasFullAnalysis: !!canvasData.fullAnalysis,
        hasFullData: !!canvasData.fullData,
        fullDataStructure: canvasData.fullData ? {
          headers: canvasData.fullData.headers?.length,
          rows: canvasData.fullData.rows?.length
        } : null,
        hasSqlQuery: !!canvasData.sqlQuery,
        hasPreview: !!canvasData.preview
      });
      
      // Use the existing preview data if available
      if (canvasData.preview) {
        console.log('🎯 CanvasBlock: Using existing preview data');
        return {
          summary: canvasData.preview.summary,
          stats: canvasData.preview.stats || [],
          tablePreview: canvasData.preview.tablePreview,
          hasCharts: !!(canvasData.preview.charts && canvasData.preview.charts.length > 0)
        };
      }
      
      // Otherwise generate preview from the canvas data
      const summary = canvasData.fullAnalysis 
        ? canvasData.fullAnalysis.substring(0, 200) + (canvasData.fullAnalysis.length > 200 ? '...' : '')
        : 'Analysis completed successfully.';

      const stats = [
        { label: 'ANALYSIS', value: canvasData.fullAnalysis ? '1' : '0' },
        { label: 'TABLES', value: canvasData.fullData ? '1' : '0' },
        { label: 'QUERIES', value: canvasData.sqlQuery ? '1' : '0' },
        { label: 'STATUS', value: 'Ready' }
      ];

      let tablePreview = null;
      if (canvasData.fullData && canvasData.fullData.headers && canvasData.fullData.rows) {
        console.log('🎯 CanvasBlock: Creating table preview from fullData:', {
          headers: canvasData.fullData.headers,
          rowCount: canvasData.fullData.rows.length,
          firstRowSample: canvasData.fullData.rows[0]
        });
        
        tablePreview = {
          headers: canvasData.fullData.headers,
          rows: canvasData.fullData.rows.slice(0, 3).map(row => 
            canvasData.fullData.headers.map(header => {
              const value = row[header];
              // Handle Decimal and other special types
              if (value === null || value === undefined) return '';
              if (typeof value === 'object' && value.constructor && value.constructor.name === 'Decimal') {
                return value.toString();
              }
              if (value instanceof Date) return value.toISOString();
              return String(value);
            })
          ),
          totalRows: canvasData.fullData.rows.length
        };
        
        console.log('🎯 CanvasBlock: Table preview created:', {
          headers: tablePreview.headers,
          rowCount: tablePreview.rows.length,
          totalRows: tablePreview.totalRows
        });
      }

      return {
        summary,
        stats,
        tablePreview,
        hasCharts: false
      };
    }
    
    // Fallback: try to read from canvas page blocks (for when page is already populated)
    if (!canvasPage || canvasPage.blocks.length === 0) {
      return null;
    }

    console.log('🎯 CanvasBlock: Generating preview from canvas page blocks');
    const blocks = canvasPage.blocks;
    
    // Find different types of blocks for preview
    const tableBlocks = blocks.filter(b => b.type === 'table');
    const textBlocks = blocks.filter(b => b.type === 'text');
    const quoteBlocks = blocks.filter(b => b.type === 'quote');
    const headingBlocks = blocks.filter(b => b.type.startsWith('heading'));

    // Generate summary from text/quote blocks
    const summaryBlocks = [...textBlocks, ...quoteBlocks];
    const summary = summaryBlocks.length > 0 
      ? summaryBlocks[0].content.substring(0, 200) + (summaryBlocks[0].content.length > 200 ? '...' : '')
      : 'Analysis completed successfully.';

    // Generate stats
    const stats = [
      { label: 'BLOCKS', value: blocks.length.toString() },
      { label: 'TABLES', value: tableBlocks.length.toString() },
      { label: 'INSIGHTS', value: quoteBlocks.length.toString() },
      { label: 'SECTIONS', value: headingBlocks.length.toString() }
    ];

    // Get table preview from first table block
    let tablePreview = null;
    if (tableBlocks.length > 0) {
      const tableData = tableBlocks[0].properties?.tableData;
      if (tableData) {
        tablePreview = {
          headers: tableData.headers || [],
          rows: tableData.data?.slice(0, 3) || [],
          totalRows: tableData.data?.length || 0
        };
      }
    }

    return {
      summary,
      stats,
      tablePreview,
      hasCharts: false // Could be enhanced later
    };
  };

  const preview = generatePreview();

  // Initialize canvas if needed
  useEffect(() => {
    if (!canvasPageId && !threadName) {
      setShowNameEditor(true);
    }
  }, [canvasPageId, threadName]);

  const openCanvasPage = async () => {
    // If canvas has an associated pageId, navigate to it
    if (canvasPageId) {
      // Check if the page still exists
      const targetPage = workspace.pages.find(p => p.id === canvasPageId);
      
      if (targetPage) {
        // Page exists, navigate normally
        onNavigateToPage?.(canvasPageId);
        return;
      } else {
        // Page was deleted - clear the broken reference and recreate
        console.warn('Canvas page was deleted, recreating...', canvasPageId);
        
        // Clear the broken reference
    onUpdate({
      properties: {
        ...block.properties,
              canvasPageId: undefined
      }
    });
      }
    }
    
    // Create a new dedicated page for this canvas
    if (onCreateCanvasPage) {
      try {
        const canvasPageId = await onCreateCanvasPage({
          threadName: threadName || 'Canvas Analysis',
          parentPageId: page.id,
          parentBlockId: block.id,
          // Pass through any existing canvas data with AI query results
          ...block.properties?.canvasData
        });
        
        // Store the canvas page reference in the block
        onUpdate({
          properties: {
            ...block.properties,
              canvasPageId: canvasPageId
          }
        });
        
        // Navigate to the new canvas page
        onNavigateToPage?.(canvasPageId);
      } catch (error) {
        console.error('Failed to create canvas page:', error);
      }
    }
  };

  const updateThreadName = (newName: string) => {
    setTempName(newName);
    onUpdate({
      content: newName,
      properties: {
        ...block.properties,
          threadName: newName
      }
    });
    setShowNameEditor(false);
  };

  const handleNameSubmit = () => {
    if (tempName.trim()) {
      updateThreadName(tempName.trim());
    } else {
      setTempName(threadName);
      setShowNameEditor(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleNameSubmit();
    } else if (e.key === 'Escape') {
      setTempName(threadName);
      setShowNameEditor(false);
    }
  };

  // Check if canvas page reference is broken
  const isCanvasPageMissing = canvasPageId && !canvasPage;

    return (
      <div className="w-full canvas-block">
        <div 
        className={cn(
          "group border rounded-lg hover:border-gray-300 dark:hover:border-gray-600 transition-colors cursor-pointer overflow-hidden canvas-preview",
          isCanvasPageMissing 
            ? "border-orange-300 dark:border-orange-600 bg-orange-50 dark:bg-orange-900/20" 
            : "border-gray-200 dark:border-gray-700"
        )}
        onClick={(e) => {
          // Don't navigate if clicking on interactive elements
          const target = e.target as HTMLElement;
          if (
            target.tagName === 'BUTTON' ||
            target.tagName === 'INPUT' ||
            target.closest('button') ||
            target.closest('input')
          ) {
            return;
          }
          openCanvasPage();
        }}
        >
          {/* Header */}
        <div className={cn(
          "flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700",
          isCanvasPageMissing ? "bg-orange-100 dark:bg-orange-900/30" : "bg-gray-50 dark:bg-gray-800"
        )}>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
              <BarChart3 className={cn(
                "h-5 w-5",
                isCanvasPageMissing ? "text-orange-600 dark:text-orange-400" : "text-blue-600 dark:text-blue-400"
              )} />
                <ChevronRight className="h-4 w-4 text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
              </div>
              
              {showNameEditor ? (
                <input
                  type="text"
                  value={tempName}
                  onChange={(e) => setTempName(e.target.value)}
                  onBlur={handleNameSubmit}
                  onKeyDown={handleKeyDown}
                placeholder="Name your canvas analysis..."
                  className="font-medium text-gray-900 dark:text-gray-100 bg-transparent border-none outline-none focus:ring-0 flex-1 min-w-0"
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span 
                  className="font-medium text-gray-900 dark:text-gray-100"
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    setShowNameEditor(true);
                  }}
                >
                {threadName || 'Untitled Canvas'}
                </span>
              )}
            
            {isCanvasPageMissing && (
              <span className="text-xs text-orange-600 dark:text-orange-400 bg-orange-200 dark:bg-orange-800 px-2 py-1 rounded">
                Page Missing
              </span>
            )}
          </div>
            
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded">
              Canvas
              </span>
            <Maximize2 className={cn(
              "h-4 w-4 transition-colors",
              isCanvasPageMissing 
                ? "text-orange-400 dark:text-orange-500 group-hover:text-orange-600 dark:group-hover:text-orange-400" 
                : "text-gray-400 dark:text-gray-500 group-hover:text-blue-600 dark:group-hover:text-blue-400"
            )} />
          </div>
        </div>

        {/* Preview Content */}
        {isCanvasPageMissing ? (
          <div className="p-4 space-y-4">
            <div className="text-sm text-orange-700 dark:text-orange-300 bg-orange-100 dark:bg-orange-900/30 p-3 rounded-lg border-l-4 border-orange-300 dark:border-orange-600">
              <div className="flex items-center gap-2 font-medium text-orange-900 dark:text-orange-100 mb-1">
                <Eye className="h-4 w-4" />
                Canvas Page Missing
              </div>
              <p>The dedicated page for this canvas was deleted. Click to recreate it and continue your analysis.</p>
            </div>
          </div>
        ) : preview ? (
            <div className="p-4 space-y-4">
              {/* Summary */}
            {preview.summary && (
                <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/30 p-3 rounded-lg border-l-4 border-blue-200 dark:border-blue-600">
                  <div className="flex items-center gap-2 font-medium text-blue-900 dark:text-blue-100 mb-1">
                    <Eye className="h-4 w-4" />
                  Analysis Summary
                  </div>
                  <div className="prose prose-sm max-w-none text-sm text-gray-700 dark:text-gray-300">
                  <ReactMarkdown children={preview.summary} />
                  </div>
                </div>
              )}

              {/* Stats */}
            {preview.stats && preview.stats.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {preview.stats.map((stat, index) => (
                    <div key={index} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
                      <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{stat.label}</div>
                      <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">{stat.value}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Table Preview */}
            {preview.tablePreview && (
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                    Table Preview: {preview.tablePreview.headers?.length || 0} columns, {preview.tablePreview.rows?.length || 0} rows
                  </div>
                <TableDisplay
                  headers={preview.tablePreview.headers}
                  rows={preview.tablePreview.rows}
                  totalRows={preview.tablePreview.totalRows}
                  title="Data Preview"
                  isPreview={true}
                  maxRows={3}
                />
                </div>
              )}

              {/* AI Reasoning Chain - Show if available */}
              {block.properties?.canvasData?.reasoningChain && (() => {
                const reasoningChain = block.properties.canvasData.reasoningChain as any;
                
                // Handle new object format with events array
                if (reasoningChain && typeof reasoningChain === 'object' && !Array.isArray(reasoningChain) && reasoningChain.events) {
                  const isIncomplete = !reasoningChain.isComplete;
                  const isFailed = reasoningChain.status === 'failed';
                  
                  return (
                    <div>
                      {/* Show status indicator for incomplete/failed chains */}
                      {(isIncomplete || isFailed) && (
                        <div className="mb-3 p-3 bg-orange-50 dark:bg-orange-900/30 border border-orange-200 dark:border-orange-600 rounded-lg">
                          <div className="flex items-center gap-2 text-orange-700 dark:text-orange-300">
                            <AlertTriangle className="h-4 w-4" />
                            <span className="font-medium">
                              {isFailed ? 'Query Failed' : 'Query Incomplete'}
                            </span>
                          </div>
                          <p className="text-sm text-orange-600 dark:text-orange-400 mt-1">
                            {isFailed 
                              ? 'This analysis encountered an error. Check the reasoning chain below for details.'
                              : 'This analysis was interrupted. You can retry or resume from the Canvas workspace.'
                            }
                          </p>
                        </div>
                      )}
                      
                      <ReasoningChain
                        reasoningData={{
                          events: Array.isArray(reasoningChain.events) 
                            ? reasoningChain.events.map((event: any) => ({
                                type: event.type as any,
                                message: event.message,
                                timestamp: event.timestamp,
                                metadata: event.metadata
                              }))
                            : [],
                          originalQuery: block.properties.canvasData.originalQuery || 'Analysis Query',
                          isComplete: reasoningChain.isComplete ?? true,
                          lastUpdated: reasoningChain.lastUpdated || new Date().toISOString(),
                          status: reasoningChain.status || 'completed',
                          progress: reasoningChain.progress ?? 1.0
                        }}
                        title={isIncomplete || isFailed ? "AI Processing Log" : "How AI Solved This"}
                        collapsed={!isIncomplete && !isFailed} // Show expanded for failed/incomplete
                      />
                    </div>
                  );
                }
                
                // Handle old array format (legacy)
                if (Array.isArray(reasoningChain)) {
                  return (
                    <ReasoningChain
                      reasoningData={{
                        events: reasoningChain.map((event: any) => ({
                          type: event.type as any,
                          message: event.message,
                          timestamp: event.timestamp,
                          metadata: event.metadata
                        })),
                        originalQuery: block.properties.canvasData.originalQuery || 'Analysis Query',
                        isComplete: true,
                        lastUpdated: new Date().toISOString(),
                        status: 'completed' as const,
                        progress: 1.0
                      }}
                      title="How AI Solved This"
                      collapsed={true}
                    />
                  );
                }
                
                return null;
              })()}
                      </div>
        ) : threadName ? (
          // Show basic preview for named canvases without content yet
            <div className="p-4 space-y-4">
              <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/30 p-3 rounded-lg border-l-4 border-blue-200 dark:border-blue-600">
                <div className="flex items-center gap-2 font-medium text-blue-900 dark:text-blue-100 mb-1">
                  <Eye className="h-4 w-4" />
                Analysis Workspace
                </div>
              <p>This canvas is ready for analysis. Click to open the workspace and start building your analysis.</p>
              </div>

            {/* Empty state stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Blocks</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">0</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Tables</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">0</div>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Insights</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">0</div>
              </div>
              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Status</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">Ready</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center">
              <div className="flex flex-col items-center gap-3 text-gray-500 dark:text-gray-400">
                <Activity className="h-8 w-8" />
                <div>
                  <div className="font-medium">Ready for Analysis</div>
                <div className="text-sm">Click to open canvas workspace</div>
              </div>
              </div>
            </div>
          )}
        </div>

        {/* Edit Controls */}
        {isFocused && (
          <div className="flex gap-2 mt-2">
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
              e.preventDefault();
                setShowNameEditor(true);
              }}
            >
            Rename
            </Button>
          {isCanvasPageMissing ? (
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                openCanvasPage();
              }}
              className="text-orange-600 dark:text-orange-400 border-orange-300 dark:border-orange-600 hover:bg-orange-50 dark:hover:bg-orange-900/30"
            >
              Recreate Page
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                openCanvasPage();
              }}
            >
              Open Canvas
            </Button>
          )}
        </div>
      )}
    </div>
  );
}; 