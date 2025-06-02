import { useState, useEffect } from 'react';
import { Block, Page, Workspace } from '@/types';
import { BarChart3, ChevronRight, Maximize2, Eye, Database, TrendingUp, Activity } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';

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

  // Generate preview data dynamically from canvas page blocks
  const generatePreview = () => {
    if (!canvasPage || canvasPage.blocks.length === 0) {
      return null;
    }

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
          parentBlockId: block.id
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
          "group border rounded-lg hover:border-gray-300 transition-colors cursor-pointer overflow-hidden canvas-preview",
          isCanvasPageMissing ? "border-orange-300 bg-orange-50" : "border-gray-200"
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
          "flex items-center justify-between p-4 border-b border-gray-200",
          isCanvasPageMissing ? "bg-orange-100" : "bg-gray-50"
        )}>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
              <BarChart3 className={cn(
                "h-5 w-5",
                isCanvasPageMissing ? "text-orange-600" : "text-blue-600"
              )} />
                <ChevronRight className="h-4 w-4 text-gray-400 group-hover:text-gray-600 transition-colors" />
              </div>
              
              {showNameEditor ? (
                <input
                  type="text"
                  value={tempName}
                  onChange={(e) => setTempName(e.target.value)}
                  onBlur={handleNameSubmit}
                  onKeyDown={handleKeyDown}
                placeholder="Name your canvas analysis..."
                  className="font-medium text-gray-900 bg-transparent border-none outline-none focus:ring-0 flex-1 min-w-0"
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span 
                  className="font-medium text-gray-900"
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    setShowNameEditor(true);
                  }}
                >
                {threadName || 'Untitled Canvas'}
                </span>
              )}
            
            {isCanvasPageMissing && (
              <span className="text-xs text-orange-600 bg-orange-200 px-2 py-1 rounded">
                Page Missing
              </span>
            )}
          </div>
            
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 bg-white px-2 py-1 rounded">
              Canvas
              </span>
            <Maximize2 className={cn(
              "h-4 w-4 transition-colors",
              isCanvasPageMissing 
                ? "text-orange-400 group-hover:text-orange-600" 
                : "text-gray-400 group-hover:text-blue-600"
            )} />
          </div>
        </div>

        {/* Preview Content */}
        {isCanvasPageMissing ? (
          <div className="p-4 space-y-4">
            <div className="text-sm text-orange-700 bg-orange-100 p-3 rounded-lg border-l-4 border-orange-300">
              <div className="flex items-center gap-2 font-medium text-orange-900 mb-1">
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
                <div className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg border-l-4 border-blue-200">
                  <div className="flex items-center gap-2 font-medium text-blue-900 mb-1">
                    <Eye className="h-4 w-4" />
                  Analysis Summary
                  </div>
                  <div className="prose prose-sm max-w-none text-sm text-gray-700">
                  <ReactMarkdown children={preview.summary} />
                </div>
                </div>
              )}

              {/* Stats */}
            {preview.stats && preview.stats.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {preview.stats.map((stat, index) => (
                    <div key={index} className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">{stat.label}</div>
                      <div className="text-lg font-semibold text-gray-900 mt-1">{stat.value}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Table Preview */}
            {preview.tablePreview && (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <div className="bg-gray-50 px-3 py-2 border-b border-gray-200 flex items-center gap-2">
                    <Database className="h-4 w-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-700">
                    Data Preview ({preview.tablePreview.totalRows} rows)
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                        {preview.tablePreview.headers.map((header, index) => (
                            <th key={index} className="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                      {preview.tablePreview.rows.map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-b border-gray-100">
                            {row.map((cell, cellIndex) => (
                              <td key={cellIndex} className="px-3 py-2 text-gray-900">
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                {preview.tablePreview.totalRows > 3 && (
                    <div className="bg-gray-50 px-3 py-2 text-xs text-gray-500 text-center">
                    +{preview.tablePreview.totalRows - 3} more rows
                    </div>
                  )}
                </div>
              )}
                      </div>
        ) : threadName ? (
          // Show basic preview for named canvases without content yet
            <div className="p-4 space-y-4">
              <div className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg border-l-4 border-blue-200">
                <div className="flex items-center gap-2 font-medium text-blue-900 mb-1">
                  <Eye className="h-4 w-4" />
                Analysis Workspace
              </div>
              <p>This canvas is ready for analysis. Click to open the workspace and start building your analysis.</p>
              </div>

            {/* Empty state stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 uppercase tracking-wide">Blocks</div>
                <div className="text-lg font-semibold text-gray-900 mt-1">0</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 uppercase tracking-wide">Tables</div>
                <div className="text-lg font-semibold text-gray-900 mt-1">0</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500 uppercase tracking-wide">Insights</div>
                <div className="text-lg font-semibold text-gray-900 mt-1">0</div>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-500 uppercase tracking-wide">Status</div>
                <div className="text-lg font-semibold text-gray-900 mt-1">Ready</div>
              </div>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center">
              <div className="flex flex-col items-center gap-3 text-gray-500">
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
              className="text-orange-600 border-orange-300 hover:bg-orange-50"
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