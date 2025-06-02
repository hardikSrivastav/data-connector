import { useState, useEffect } from 'react';
import { Block, Page, Workspace } from '@/types';
import { BarChart3, ChevronDown, ChevronRight, Maximize2, Minimize2, TrendingUp, Database, Eye, Activity, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { BlockEditor } from './BlockEditor';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';

interface CanvasBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
  workspace: Workspace;
  page: Page;
  onCanvasQuery?: (query: string, threadId: string) => void;
  onNavigateToPage?: (pageId: string) => void;
  onCreateCanvasPage?: (canvasData: any) => Promise<string>;
}

export const CanvasBlock = ({ 
  block, 
  onUpdate, 
  isFocused, 
  workspace, 
  page,
  onCanvasQuery,
  onNavigateToPage,
  onCreateCanvasPage
}: CanvasBlockProps) => {
  const canvasData = block.properties?.canvasData;
  const [showNameEditor, setShowNameEditor] = useState(!canvasData?.threadName);
  const [tempName, setTempName] = useState(canvasData?.threadName || '');
  
  // Canvas-specific blocks state
  const [canvasBlocks, setCanvasBlocks] = useState<Block[]>([]);
  const [focusedCanvasBlockId, setFocusedCanvasBlockId] = useState<string | null>(null);

  useEffect(() => {
    if (block.properties?.canvasData?.threadName) {
      setTempName(block.properties.canvasData.threadName);
      setShowNameEditor(false);
    }
  }, [block.properties?.canvasData?.threadName]);

  // Initialize canvas blocks from stored data or create initial block
  useEffect(() => {
    if (canvasData && canvasData.isExpanded) {
      const storedBlocks = canvasData.blocks || [];
      setCanvasBlocks(storedBlocks);
      // Don't automatically create a block - let users see analysis results first
      // and choose to add blocks when they want to
    }
  }, [canvasData?.isExpanded]);

  // Initialize canvas if needed
  useEffect(() => {
    if (!canvasData) {
      // Create new canvas thread
      const newCanvasData = {
        threadId: `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        threadName: '',
        isExpanded: false,
        workspaceId: workspace.id,
        pageId: page.id,
        blockId: block.id,
        blocks: [] // Initialize empty blocks array
      };

      onUpdate({
        properties: {
          ...block.properties,
          canvasData: newCanvasData
        }
      });
      setShowNameEditor(true);
    }
  }, [canvasData, workspace.id, page.id, block.id, onUpdate, block.properties]);

  const updateCanvasBlocks = (newBlocks: Block[]) => {
    if (!canvasData) return;
    
    onUpdate({
      properties: {
        ...block.properties,
        canvasData: {
          ...canvasData,
          blocks: newBlocks
        }
      }
    });
  };

  const handleCanvasBlockUpdate = (blockId: string, updates: Partial<Block>) => {
    const newBlocks = canvasBlocks.map(b => 
      b.id === blockId ? { ...b, ...updates } : b
    );
    setCanvasBlocks(newBlocks);
    updateCanvasBlocks(newBlocks);
  };

  const handleAddCanvasBlock = (afterBlockId?: string) => {
    const newBlock: Block = {
      id: `canvas_block_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type: 'text',
      content: '',
      order: canvasBlocks.length
    };

    let newBlocks;
    if (afterBlockId) {
      const afterIndex = canvasBlocks.findIndex(b => b.id === afterBlockId);
      newBlocks = [
        ...canvasBlocks.slice(0, afterIndex + 1),
        newBlock,
        ...canvasBlocks.slice(afterIndex + 1)
      ];
    } else {
      newBlocks = [...canvasBlocks, newBlock];
    }

    // Update order numbers
    newBlocks.forEach((block, index) => {
      block.order = index;
    });

    setCanvasBlocks(newBlocks);
    updateCanvasBlocks(newBlocks);
    setFocusedCanvasBlockId(newBlock.id);
    return newBlock.id;
  };

  const handleDeleteCanvasBlock = (blockId: string) => {
    const blockIndex = canvasBlocks.findIndex(b => b.id === blockId);
    const newBlocks = canvasBlocks.filter(b => b.id !== blockId);
    
    // Update order numbers
    newBlocks.forEach((block, index) => {
      block.order = index;
    });

    setCanvasBlocks(newBlocks);
    updateCanvasBlocks(newBlocks);
    
    // Focus previous block if available
    if (blockIndex > 0 && newBlocks.length > 0) {
      setFocusedCanvasBlockId(newBlocks[blockIndex - 1].id);
    } else if (newBlocks.length > 0) {
      setFocusedCanvasBlockId(newBlocks[0].id);
    } else {
      setFocusedCanvasBlockId(null);
    }
  };

  const handleMoveCanvasBlock = (blockId: string, newIndex: number) => {
    const currentIndex = canvasBlocks.findIndex(b => b.id === blockId);
    if (currentIndex === -1) return;

    const newBlocks = [...canvasBlocks];
    const [movedBlock] = newBlocks.splice(currentIndex, 1);
    newBlocks.splice(newIndex, 0, movedBlock);

    // Update order numbers
    newBlocks.forEach((block, index) => {
      block.order = index;
    });

    setCanvasBlocks(newBlocks);
    updateCanvasBlocks(newBlocks);
  };

  const openCanvasPage = async () => {
    if (!canvasData) return;
    
    // If canvas has an associated pageId, navigate to it
    if (canvasData.canvasPageId) {
      // First check if the page still exists
      const targetPage = workspace.pages.find(p => p.id === canvasData.canvasPageId);
      
      if (targetPage) {
        // Page exists, navigate normally
        onNavigateToPage?.(canvasData.canvasPageId);
        return;
      } else {
        // Page was deleted - clear the broken reference and recreate
        console.warn('Canvas page was deleted, recreating...', canvasData.canvasPageId);
        
        // Clear the broken reference
    onUpdate({
      properties: {
        ...block.properties,
        canvasData: {
          ...canvasData,
              canvasPageId: undefined
        }
      }
    });
        
        // Fall through to creation logic below
      }
    }
    
    // Create a new dedicated page for this canvas
    if (onCreateCanvasPage) {
      try {
        const canvasPageId = await onCreateCanvasPage({
          ...canvasData,
          parentPageId: page.id,
          parentBlockId: block.id
        });
        
        // Store the canvas page reference in the block
        onUpdate({
          properties: {
            ...block.properties,
            canvasData: {
              ...canvasData,
              canvasPageId: canvasPageId
            }
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
    if (!canvasData) return;
    
    setTempName(newName);
    onUpdate({
      content: newName,
      properties: {
        ...block.properties,
        canvasData: {
          ...canvasData,
          threadName: newName
        }
      }
    });
    setShowNameEditor(false);
  };

  const handleNameSubmit = () => {
    if (tempName.trim()) {
      updateThreadName(tempName.trim());
    } else {
      setTempName(canvasData?.threadName || '');
      setShowNameEditor(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleNameSubmit();
    } else if (e.key === 'Escape') {
      setTempName(canvasData?.threadName || '');
      setShowNameEditor(false);
    }
  };

  // Check if canvas page reference is broken
  const isCanvasPageMissing = canvasData?.canvasPageId && 
    !workspace.pages.find(p => p.id === canvasData.canvasPageId);

  if (!canvasData) {
    return (
      <div className="w-full p-4 border border-gray-200 rounded-lg bg-gray-50">
        <div className="flex items-center gap-2 text-gray-500">
          <BarChart3 className="h-4 w-4" />
          <span className="text-sm">Initializing canvas...</span>
        </div>
      </div>
    );
  }

  // Always show as collapsed preview - clicking opens dedicated page
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
                  placeholder="Name your canvas thread..."
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
                  {canvasData.threadName || 'Untitled Canvas'}
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
                Thread #{canvasData.threadId.split('_')[1]?.substr(0, 6) || 'new'}
              </span>
            <Maximize2 className={cn(
              "h-4 w-4 transition-colors",
              isCanvasPageMissing 
                ? "text-orange-400 group-hover:text-orange-600" 
                : "text-gray-400 group-hover:text-blue-600"
            )} />
          </div>
        </div>

        {/* Preview Content - Show different content if page is missing */}
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
        ) : canvasData.preview ? (
            <div className="p-4 space-y-4">
              {/* Summary */}
              {canvasData.preview.summary && (
                <div className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg border-l-4 border-blue-200">
                  <div className="flex items-center gap-2 font-medium text-blue-900 mb-1">
                    <Eye className="h-4 w-4" />
                    Summary
                  </div>
                  <div className="prose prose-sm max-w-none text-sm text-gray-700">
                    <ReactMarkdown children={canvasData.preview.summary} />
                  </div>
                </div>
              )}

              {/* Stats */}
              {canvasData.preview.stats && canvasData.preview.stats.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {canvasData.preview.stats.map((stat, index) => (
                    <div key={index} className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">{stat.label}</div>
                      <div className="text-lg font-semibold text-gray-900 mt-1">{stat.value}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Table Preview */}
              {canvasData.preview.tablePreview && (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <div className="bg-gray-50 px-3 py-2 border-b border-gray-200 flex items-center gap-2">
                    <Database className="h-4 w-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-700">
                      Data Preview ({canvasData.preview.tablePreview.totalRows} rows)
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          {canvasData.preview.tablePreview.headers.map((header, index) => (
                            <th key={index} className="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {canvasData.preview.tablePreview.rows.slice(0, 3).map((row, rowIndex) => (
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
                  {canvasData.preview.tablePreview.rows.length > 3 && (
                    <div className="bg-gray-50 px-3 py-2 text-xs text-gray-500 text-center">
                      +{canvasData.preview.tablePreview.rows.length - 3} more rows
                    </div>
                  )}
                </div>
              )}

              {/* Charts Preview */}
              {canvasData.preview.charts && canvasData.preview.charts.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {canvasData.preview.charts.map((chart, index) => (
                    <div key={index} className="bg-white border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="h-4 w-4 text-green-600" />
                        <span className="text-sm font-medium text-gray-700">
                          {chart.type.charAt(0).toUpperCase() + chart.type.slice(1)} Chart
                        </span>
                      </div>
                      <div className="h-24 bg-gray-50 rounded flex items-center justify-center text-xs text-gray-500">
                        Chart preview ({chart.type})
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : canvasData.threadName ? (
            // Show demo preview data for named canvases
            <div className="p-4 space-y-4">
              {/* Demo Summary */}
              <div className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg border-l-4 border-blue-200">
                <div className="flex items-center gap-2 font-medium text-blue-900 mb-1">
                  <Eye className="h-4 w-4" />
                  Analysis Summary
                </div>
                <p>This canvas contains data analysis results. Click to expand and see your queries, visualizations, and insights.</p>
              </div>

              {/* Demo Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500 uppercase tracking-wide">Queries</div>
                  <div className="text-lg font-semibold text-gray-900 mt-1">3</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500 uppercase tracking-wide">Results</div>
                  <div className="text-lg font-semibold text-gray-900 mt-1">1.2k</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500 uppercase tracking-wide">Charts</div>
                  <div className="text-lg font-semibold text-gray-900 mt-1">2</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500 uppercase tracking-wide">Insights</div>
                  <div className="text-lg font-semibold text-gray-900 mt-1">5</div>
                </div>
              </div>

              {/* Demo Table Preview */}
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-3 py-2 border-b border-gray-200 flex items-center gap-2">
                  <Database className="h-4 w-4 text-gray-600" />
                  <span className="text-sm font-medium text-gray-700">
                    Latest Results (1,247 rows)
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">Date</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">Revenue</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">Orders</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700 border-b border-gray-200">Region</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-gray-100">
                        <td className="px-3 py-2 text-gray-900">2024-01-15</td>
                        <td className="px-3 py-2 text-gray-900">$12,450</td>
                        <td className="px-3 py-2 text-gray-900">87</td>
                        <td className="px-3 py-2 text-gray-900">North America</td>
                      </tr>
                      <tr className="border-b border-gray-100">
                        <td className="px-3 py-2 text-gray-900">2024-01-14</td>
                        <td className="px-3 py-2 text-gray-900">$9,280</td>
                        <td className="px-3 py-2 text-gray-900">64</td>
                        <td className="px-3 py-2 text-gray-900">Europe</td>
                      </tr>
                      <tr className="border-b border-gray-100">
                        <td className="px-3 py-2 text-gray-900">2024-01-13</td>
                        <td className="px-3 py-2 text-gray-900">$15,670</td>
                        <td className="px-3 py-2 text-gray-900">103</td>
                        <td className="px-3 py-2 text-gray-900">Asia Pacific</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className="bg-gray-50 px-3 py-2 text-xs text-gray-500 text-center">
                  +1,244 more rows
                </div>
              </div>

              {/* Demo Charts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-white border border-gray-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium text-gray-700">Revenue Trend</span>
                  </div>
                  <div className="h-24 bg-gray-50 rounded flex items-center justify-center text-xs text-gray-500">
                    📈 Line chart preview
                  </div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium text-gray-700">Regional Distribution</span>
                  </div>
                  <div className="h-24 bg-gray-50 rounded flex items-center justify-center text-xs text-gray-500">
                    🥧 Pie chart preview
                  </div>
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
              Rename Thread
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