import { useState } from 'react';
import { Page, Workspace, Block } from '@/types';
import { agentClient, AgentQueryResponse } from '@/lib/agent-client';
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
  Plus
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedView, setSelectedView] = useState<'analysis' | 'data' | 'history'>('analysis');
  const [isQueryRunning, setIsQueryRunning] = useState(false);

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
      { label: 'KEY INSIGHTS', value: quoteBlocks.length.toString() }
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

  const handleRunNewQuery = async () => {
    const queryText = prompt('Enter your SQL query or natural language question:');
    if (!queryText || queryText.trim() === '') return;
    
    let loadingId: string | null = null; // Declare outside try block
    
    try {
      console.log('🚀 CanvasWorkspace: Executing new query:', queryText);
      setIsQueryRunning(true);
      
      // Add a timestamp heading for this analysis
      const timestamp = new Date().toLocaleString();
      const headingId = onAddBlock ? onAddBlock(undefined, 'heading2') : null;
      if (headingId && onUpdateBlock) {
        onUpdateBlock(headingId, {
          content: `Analysis - ${timestamp}`
        });
      }
      
      // Add loading indicator
      loadingId = onAddBlock ? onAddBlock(undefined, 'text') : null;
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: '🔄 Running query and analyzing results...'
        });
      }
      
      // Execute the query via agent client
      const response: AgentQueryResponse = await agentClient.query({
        question: queryText.trim(),
        analyze: true
      });
      
      console.log('✅ CanvasWorkspace: Query completed successfully');
      
      // Update loading text with query details
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: `**Query:** ${response.sql || queryText}`
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
      
      // Add query results as table
      if (response.rows && response.rows.length > 0) {
        const tableId = onAddBlock ? onAddBlock(undefined, 'table') : null;
        if (tableId && onUpdateBlock) {
          const headers = Object.keys(response.rows[0]);
          const tableData = response.rows.map(row => 
            headers.map(header => String(row[header] || ''))
          );
          
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
        }
      }
      
      // Add key insights as quotes if available
      if (response.analysis) {
        // Extract insights from analysis (simple approach)
        const insights = response.analysis.split('\n').filter(line => 
          line.toLowerCase().includes('insight') || 
          line.toLowerCase().includes('finding') ||
          line.toLowerCase().includes('trend')
        );
        
        insights.forEach(insight => {
          if (insight.trim()) {
            const quoteId = onAddBlock ? onAddBlock(undefined, 'quote') : null;
            if (quoteId && onUpdateBlock) {
              onUpdateBlock(quoteId, {
                content: insight.trim()
              });
            }
          }
        });
      }
      
      // Add divider for next analysis
      onAddBlock?.(undefined, 'divider');
      
    } catch (error) {
      console.error('❌ CanvasWorkspace: Query failed:', error);
      
      // Update loading text with error
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: `❌ **Error:** ${error.message || 'Query execution failed'}`
        });
      }
      
      // Add error details as quote
      const errorId = onAddBlock ? onAddBlock(undefined, 'quote') : null;
      if (errorId && onUpdateBlock) {
        onUpdateBlock(errorId, {
          content: `Error details: ${error.message || 'Unknown error occurred'}`
        });
      }
    } finally {
      setIsQueryRunning(false);
    }
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar - Analysis History */}
      <div className={cn(
        "border-r border-gray-200 bg-gray-50 transition-all duration-200",
        sidebarCollapsed ? "w-12" : "w-80"
      )}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-200">
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
                <GitBranch className="h-4 w-4 text-gray-600" />
                <span className="font-medium text-sm">Analysis History</span>
              </div>
            )}
          </div>
        </div>

        {!sidebarCollapsed && (
          <>
            {/* Canvas Info */}
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="h-5 w-5 text-blue-600" />
                <h2 className="font-semibold">{page.title}</h2>
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <div>Status: <span className="font-medium text-green-600">Ready</span></div>
                <div>Blocks: {page.blocks.length}</div>
                <div>Created: {new Date(page.createdAt).toLocaleDateString()}</div>
              </div>
            </div>

            {/* Search */}
            <div className="p-4 border-b border-gray-200">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
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
                <h3 className="text-sm font-medium text-gray-700 mb-3">Analysis Sections</h3>
                <div className="space-y-2">
                  {page.blocks
                    .filter(block => block.type.startsWith('heading'))
                    .map((block, index) => (
                      <div
                        key={block.id}
                        className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                          <div className="w-2 h-2 rounded-full bg-blue-500" />
                          <span className="text-sm font-medium">{block.content || `Section ${index + 1}`}</span>
                      </div>
                        <div className="text-xs text-gray-500">
                          {new Date().toLocaleString()}
                        </div>
                      </div>
                    ))}
                  
                  {page.blocks.filter(block => block.type.startsWith('heading')).length === 0 && (
                    <div className="text-sm text-gray-500 text-center py-4">
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
        <div className="border-b border-gray-200 bg-white">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onNavigateBack}
                className="text-gray-600 hover:text-gray-900"
              >
                ← Back to Page
              </Button>
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-blue-600" />
                <h1 className="text-lg font-semibold">{page.title}</h1>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button 
                size="sm" 
                variant="outline" 
                onClick={handleRunNewQuery}
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
          <div className="flex border-t border-gray-200">
            {[
              { id: 'analysis', label: 'Analysis', icon: Eye },
              { id: 'data', label: 'Data', icon: Database },
              { id: 'history', label: 'History', icon: Clock }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  selectedView === id
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                )}
                onClick={() => setSelectedView(id as any)}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {selectedView === 'analysis' && (
            <div className="max-w-4xl mx-auto space-y-6">
              {/* Current Analysis Summary */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Eye className="h-5 w-5 text-blue-600" />
                  <h2 className="text-lg font-semibold text-blue-900">Current Analysis</h2>
                </div>
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown>{analysisData.currentAnalysis}</ReactMarkdown>
                </div>
              </div>

              {/* Key Statistics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {analysisData.stats.map((stat, index) => (
                  <div key={index} className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 uppercase tracking-wide">{stat.label}</div>
                    <div className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</div>
                  </div>
                ))}
              </div>

              {/* Quick Actions */}
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 mb-3">Quick Actions</h3>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={handleRunNewQuery}>
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
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Database className="h-5 w-5 text-gray-600" />
                        <h3 className="font-medium">Latest Query Results</h3>
                      <span className="text-sm text-gray-500">
                          ({analysisData.currentTable.properties?.tableData?.data?.length || 0} rows)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline">
                        <Filter className="h-4 w-4 mr-2" />
                        Filter
                      </Button>
                      <Button size="sm" variant="outline">
                        <Download className="h-4 w-4 mr-2" />
                        Download CSV
                      </Button>
                    </div>
                  </div>
                </div>
                
                <div className="overflow-x-auto">
                    {analysisData.currentTable.properties?.tableData && (
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                            {analysisData.currentTable.properties.tableData.headers?.map((header, index) => (
                          <th key={index} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {header}
                          </th>
                            ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                          {analysisData.currentTable.properties.tableData.data?.slice(0, 50).map((row, rowIndex) => (
                        <tr key={rowIndex} className="hover:bg-gray-50">
                              {row.map((cell, cellIndex) => (
                            <td key={cellIndex} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                    {typeof cell === 'string' && cell.length > 100 ? (
                                <div className="max-w-md truncate" title={cell}>
                                  {cell}
                                </div>
                              ) : (
                                      String(cell || '')
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Data Available</h3>
                  <p className="text-gray-500 mb-6">Run a query to see data results here.</p>
                  <Button onClick={handleRunNewQuery}>
                    <Play className="h-4 w-4 mr-2" />
                    Run Query
                  </Button>
              </div>
              )}
            </div>
          )}

          {selectedView === 'history' && (
            <div className="max-w-4xl mx-auto">
              <h2 className="text-lg font-semibold mb-6">Analysis History</h2>
              <div className="space-y-4">
                {analysisData.analysisHistory.length > 0 ? (
                  analysisData.analysisHistory.map((block, index) => (
                    <div key={block.id} className="border border-gray-200 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                          <div className="w-3 h-3 rounded-full bg-blue-500" />
                          <h3 className="font-medium">Analysis Step {index + 1}</h3>
                      </div>
                      <span className="text-sm text-gray-500">
                          {new Date().toLocaleString()}
                      </span>
                    </div>
                    
                      <div className="prose prose-sm max-w-none">
                        <ReactMarkdown>{block.content}</ReactMarkdown>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-12">
                    <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No Analysis History</h3>
                    <p className="text-gray-500 mb-6">Your analysis steps will appear here as you work.</p>
                    <Button onClick={handleRunNewQuery}>
                      <Play className="h-4 w-4 mr-2" />
                      Start Analysis
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}; 