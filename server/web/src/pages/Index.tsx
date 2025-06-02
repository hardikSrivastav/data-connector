import { useState } from 'react';
import { useWorkspace } from '@/hooks/useWorkspace';
import { Sidebar } from '@/components/Sidebar';
import { PageEditor } from '@/components/PageEditor';
import { CanvasWorkspace } from '@/components/CanvasWorkspace';
import { AgentTestPanel } from '@/components/AgentTestPanel';
import { X } from 'lucide-react';

const Index = () => {
  const [showAgentPanel, setShowAgentPanel] = useState(false);
  
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

  // Create a dedicated canvas page
  const createCanvasPage = async (canvasData: any): Promise<string> => {
    console.log('🎨 createCanvasPage: Starting with canvasData:', canvasData);
    
    const newPage = await createPage(canvasData.threadName || 'Canvas Analysis');
    console.log('🎨 createCanvasPage: Created canvas page:', newPage);
    
    // Add an initial heading block to the canvas page
    const headingBlock = {
      id: `heading_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type: 'heading1' as const,
      content: canvasData.threadName || 'Canvas Analysis',
      order: 0
    };
    
    // Update the page with the heading block and canvas icon
    updatePage(newPage.id, { 
      title: canvasData.threadName || 'Canvas Analysis',
      icon: '🎨',
      blocks: [headingBlock]
    });

    console.log('🎨 createCanvasPage: Canvas page ready, returning ID:', newPage.id);
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
    <div className="flex h-screen bg-white font-baskerville">
      <Sidebar
        pages={workspace.pages}
        currentPageId={currentPageId}
        onPageSelect={setCurrentPageId}
        onPageCreate={() => createPage()}
        onPageDelete={deletePage}
        onPageTitleUpdate={(pageId, title) => updatePage(pageId, { title })}
      />
      
      <div className="flex-1 flex">
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
          />
        )}
        
        {/* Agent Test Panel - only show for regular pages */}
        {!isCanvasPage && showAgentPanel && (
          <div className="w-96 border-l border-gray-200 bg-gray-50 p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">AI Agent Testing</h2>
              <button
                onClick={() => setShowAgentPanel(false)}
                className="p-1 hover:bg-gray-200 rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <AgentTestPanel />
          </div>
        )}
      </div>
    </div>
  );
};

export default Index;
