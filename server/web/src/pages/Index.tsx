import { useState } from 'react';
import { useWorkspace } from '@/hooks/useWorkspace';
import { Sidebar } from '@/components/Sidebar';
import { PageEditor } from '@/components/PageEditor';
import { AgentTestPanel } from '@/components/AgentTestPanel';
import { Button } from '@/components/ui/button';
import { Settings, X } from 'lucide-react';

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
        <PageEditor
          page={currentPage}
          onUpdateBlock={updateBlock}
          onAddBlock={addBlock}
          onDeleteBlock={deleteBlock}
          onUpdatePage={(updates) => updatePage(currentPageId, updates)}
          onMoveBlock={moveBlock}
        />
        
        {/* Agent Test Panel Toggle */}
        {!showAgentPanel && (
          <div className="fixed bottom-4 right-4 z-50">
            <Button
              onClick={() => setShowAgentPanel(true)}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white shadow-lg"
            >
              <Settings className="h-4 w-4 mr-2" />
              Test AI Agent
            </Button>
          </div>
        )}
        
        {/* Agent Test Panel */}
        {showAgentPanel && (
          <div className="w-96 border-l border-gray-200 bg-gray-50 p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">AI Agent Testing</h2>
              <Button
                onClick={() => setShowAgentPanel(false)}
                size="sm"
                variant="ghost"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <AgentTestPanel />
          </div>
        )}
      </div>
    </div>
  );
};

export default Index;
