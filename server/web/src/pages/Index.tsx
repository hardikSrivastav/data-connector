import { useState, useEffect } from 'react';
import { useWorkspace } from '@/hooks/useWorkspace';
import { useAuth } from '@/contexts/AuthContext';
import { useStorageManager } from '@/hooks/useStorageManager';
import { Sidebar } from '@/components/Sidebar';
import { PageEditor } from '@/components/PageEditor';
import { CanvasWorkspace } from '@/components/CanvasWorkspace';
import { AgentTestPanel } from '@/components/AgentTestPanel';
import { X } from 'lucide-react';

const Index = () => {
  const [showAgentPanel, setShowAgentPanel] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { user, authHealth } = useAuth();
  
  const {
    workspace,
    currentPage,
    currentPageId,
    setCurrentPageId,
    createPage,
    updatePage,
    deletePage,
    updateBlock,
    addBlock,
    deleteBlock,
    moveBlock,
    isLoaded,
    setWorkspace
  } = useWorkspace();

  const { storageManager } = useStorageManager({
    edition: 'enterprise',
    apiBaseUrl: import.meta.env.VITE_API_BASE || 'http://localhost:8787'
  });

  // Add keyboard shortcut for sidebar toggle (Cmd+\ or Ctrl+\)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check for Cmd+\ on Mac or Ctrl+\ on Windows/Linux
      if (e.key === '\\' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setSidebarCollapsed(prev => !prev);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Create a dedicated canvas page
  const createCanvasPage = async (canvasData: any): Promise<string> => {
    console.log('🎨 createCanvasPage: Starting with canvasData:', canvasData);
    
    const newPage = await createPage(canvasData.threadName || 'Canvas Analysis');
    console.log('🎨 createCanvasPage: Created canvas page:', newPage);
    
    // If we have reasoning chain data, update it to point to the new Canvas page
    if (canvasData.reasoningChain?.sessionId) {
      console.log('🧠 createCanvasPage: Updating reasoning chain to point to Canvas page:', {
        sessionId: canvasData.reasoningChain.sessionId,
        originalPageId: canvasData.originalPageId || canvasData.pageId,
        newCanvasPageId: newPage.id
      });
      
      try {
        // Update the reasoning chain to point to the Canvas page
        const updatedReasoningChain = {
          ...canvasData.reasoningChain,
          pageId: newPage.id,  // Canvas page where results will be displayed
          originalPageId: canvasData.originalPageId || canvasData.pageId  // Original page where query was made
        };
        
        // Save the updated reasoning chain
        await storageManager.saveReasoningChain(updatedReasoningChain);
        console.log('✅ createCanvasPage: Reasoning chain updated successfully');
      } catch (error) {
        console.warn('⚠️ createCanvasPage: Failed to update reasoning chain:', error);
      }
    }
    
    // Start with a heading block
    const blocks = [];
    let nextOrder = 0;
    
    // Add main heading
    blocks.push({
      id: `heading_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type: 'heading1' as const,
      content: canvasData.threadName || 'Canvas Analysis',
      order: nextOrder++
    });
    
    // If we have AI query results from canvasData, populate the page with them
    if (canvasData.fullAnalysis || canvasData.fullData || canvasData.sqlQuery) {
      console.log('🎯 createCanvasPage: Found AI query results, populating canvas page...');
      
      // Add timestamp section
      const timestamp = new Date().toLocaleString();
      blocks.push({
        id: `heading_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'heading2' as const,
        content: `Analysis - ${timestamp}`,
        order: nextOrder++
      });
      
      // Add SQL query if available
      if (canvasData.sqlQuery) {
        blocks.push({
          id: `query_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'text' as const,
          content: `**Query:** ${canvasData.sqlQuery}`,
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
      
      // Add data table if available
      if (canvasData.fullData && canvasData.fullData.headers && canvasData.fullData.rows) {
        blocks.push({
          id: `table_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'table' as const,
          content: 'Query Results',
          order: nextOrder++,
          properties: {
            tableData: {
              rows: canvasData.fullData.rows.length,
              cols: canvasData.fullData.headers.length,
              headers: canvasData.fullData.headers,
              data: canvasData.fullData.rows
            }
          }
        });
      }
      
      // Add key insights from analysis if we can extract them
      if (canvasData.fullAnalysis) {
        const insights = canvasData.fullAnalysis.split('\n').filter(line => 
          line.toLowerCase().includes('insight') || 
          line.toLowerCase().includes('finding') ||
          line.toLowerCase().includes('trend') ||
          line.toLowerCase().includes('pattern')
        );
        
        insights.forEach(insight => {
          if (insight.trim()) {
            blocks.push({
              id: `insight_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'quote' as const,
              content: insight.trim(),
              order: nextOrder++
            });
          }
        });
      }
      
      // Add divider for future analyses
      blocks.push({
        id: `divider_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'divider' as const,
        content: '---',
        order: nextOrder++
      });
      
      console.log(`✅ createCanvasPage: Populated canvas page with ${blocks.length} blocks from AI results`);
    } else {
      console.log('📝 createCanvasPage: No AI query results found, creating empty canvas page');
    }
    
    // Use setWorkspace directly to ensure immediate state update and persistence
    console.log('🔄 createCanvasPage: Updating workspace with populated canvas page...');
    setWorkspace(prev => ({
      ...prev,
      pages: prev.pages.map(page => 
        page.id === newPage.id 
          ? { 
              ...page, 
              title: canvasData.threadName || 'Canvas Analysis',
              icon: '🎨',
              blocks: blocks,
              updatedAt: new Date() 
            }
          : page
      )
    }));

    // Add a small delay to ensure the workspace update is processed
    await new Promise(resolve => setTimeout(resolve, 100));

    console.log('🎨 createCanvasPage: Canvas page ready, returning ID:', newPage.id);
    console.log('🔍 createCanvasPage: Final blocks in canvas page:', blocks.map(b => ({
      id: b.id,
      type: b.type,
      content: b.content?.substring(0, 50) || 'No content',
      hasTableData: !!(b.properties?.tableData)
    })));
    
    return newPage.id;
  };

  // Check if current page is a canvas page - check if any CanvasBlock references this page
  const isCanvasPage = workspace.pages.some(page => 
    page.blocks.some(block => 
      block.type === 'canvas' && 
      block.properties?.canvasPageId === currentPageId
    )
  );
  
  console.log('🎯 Index: Canvas page detection:', {
    currentPageId,
    currentPageTitle: currentPage.title,
    currentPageBlocks: currentPage.blocks.length,
    isCanvasPage,
    canvasBlocksPointingHere: workspace.pages.flatMap(page => 
      page.blocks.filter(block => 
        block.type === 'canvas' && 
        block.properties?.canvasPageId === currentPageId
      )
    )
  });

  return (
    <div className="flex h-full font-baskerville bg-background text-foreground">
      <Sidebar
        pages={workspace.pages}
        currentPageId={currentPageId}
        onPageSelect={setCurrentPageId}
        onPageCreate={() => createPage()}
        onPageDelete={deletePage}
        onPageTitleUpdate={(pageId, title) => updatePage(pageId, { title })}
        isCollapsed={sidebarCollapsed}
        onToggleCollapsed={setSidebarCollapsed}
      />
      
      {isCanvasPage ? (
        <CanvasWorkspace
          page={currentPage}
          workspace={workspace}
          onNavigateBack={() => {
            // Navigate back to the parent page that contains the CanvasBlock referencing this page
            const parentPage = workspace.pages.find(page => 
              page.blocks.some(block => 
                block.type === 'canvas' && 
                block.properties?.canvasPageId === currentPageId
              )
            );
            
            if (parentPage) {
              setCurrentPageId(parentPage.id);
            } else {
              // If no parent found, go to first non-canvas page or create new one
              if (workspace.pages.length > 1) {
                const nonCanvasPage = workspace.pages.find(p => 
                  p.id !== currentPageId && 
                  !workspace.pages.some(page => 
                    page.blocks.some(block => 
                      block.type === 'canvas' && 
                      block.properties?.canvasPageId === p.id
                    )
                  )
                );
                if (nonCanvasPage) {
                  setCurrentPageId(nonCanvasPage.id);
                } else {
                  createPage('New Page').then(newPage => {
                    setCurrentPageId(newPage.id);
                  });
                }
              } else {
                createPage('New Page').then(newPage => {
                  setCurrentPageId(newPage.id);
                });
              }
            }
          }}
          onUpdatePage={(updates) => updatePage(currentPageId, updates)}
          onAddBlock={addBlock}
          onUpdateBlock={updateBlock}
          onDeleteBlock={deleteBlock}
        />
      ) : (
        <div className="flex flex-1">
          <PageEditor
            page={currentPage}
            onUpdateBlock={updateBlock}
            onAddBlock={addBlock}
            onDeleteBlock={deleteBlock}
            onUpdatePage={(updates) => updatePage(currentPageId, updates)}
            onMoveBlock={moveBlock}
            showAgentPanel={showAgentPanel}
            onToggleAgentPanel={setShowAgentPanel}
            workspace={workspace}
            onNavigateToPage={setCurrentPageId}
            onCreateCanvasPage={createCanvasPage}
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
          
          {/* Agent Test Panel - only show for regular pages */}
          {showAgentPanel && (
            <div className="w-96 border-l border-border bg-muted p-4 overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Agent Testing</h2>
                <button
                  onClick={() => setShowAgentPanel(false)}
                  className="p-1 hover:bg-accent rounded text-muted-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <AgentTestPanel />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Index;
