
import { useWorkspace } from '@/hooks/useWorkspace';
import { Sidebar } from '@/components/Sidebar';
import { PageEditor } from '@/components/PageEditor';

const Index = () => {
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
      
      <PageEditor
        page={currentPage}
        onUpdateBlock={updateBlock}
        onAddBlock={addBlock}
        onDeleteBlock={deleteBlock}
        onUpdatePage={(updates) => updatePage(currentPageId, updates)}
        onMoveBlock={moveBlock}
      />
    </div>
  );
};

export default Index;
