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
    moveBlock
  } = useWorkspace();

  // Create a dedicated canvas page
  const createCanvasPage = async (canvasData: any): Promise<string> => {
    const newPage = await createPage(canvasData.threadName || 'Canvas Analysis');
    
    // Update the new page with canvas-specific content and mark it as a canvas page
    updatePage(newPage.id, {
      title: canvasData.threadName || 'Canvas Analysis',
      icon: '🎨',
      blocks: [{
        id: `canvas_content_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'text' as const,
        content: `# ${canvasData.threadName || 'Canvas Analysis'}\n\nThis is a dedicated workspace for your canvas analysis.`,
        order: 0,
        properties: {
          isCanvasPage: true, // Mark this as a canvas page
          canvasData: canvasData
        }
      }]
    });

    return newPage.id;
  };

  // Check if current page is a canvas page - only for dedicated canvas workspaces
  const isCanvasPage = currentPage.blocks.some(block => 
    block.properties?.isCanvasPage === true
  );

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
              // Navigate back to the parent page or create a new regular page
              const parentBlock = currentPage.blocks.find(block => block.properties?.canvasData?.parentPageId);
              if (parentBlock?.properties?.canvasData?.parentPageId) {
                setCurrentPageId(parentBlock.properties.canvasData.parentPageId);
              } else {
                // If no parent, just create a new page or go to first available page
                if (workspace.pages.length > 1) {
                  const nonCanvasPage = workspace.pages.find(p => 
                    p.id !== currentPageId && 
                    !p.blocks.some(b => b.properties?.isCanvasPage)
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
