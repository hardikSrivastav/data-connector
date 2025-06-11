import { useState, useEffect } from 'react';
import { Block, Workspace } from '@/types';
import { FileText, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface SubpageBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
  workspace: Workspace;
  onNavigateToPage?: (pageId: string) => void;
}

export const SubpageBlock = ({ 
  block, 
  onUpdate, 
  isFocused, 
  workspace, 
  onNavigateToPage 
}: SubpageBlockProps) => {
  const subpageData = block.properties?.subpageData;
  const [selectedPageId, setSelectedPageId] = useState(subpageData?.pageId || '');
  const [showPageSelector, setShowPageSelector] = useState(!subpageData?.pageId);

  useEffect(() => {
    if (block.properties?.subpageData?.pageId) {
      setSelectedPageId(block.properties.subpageData.pageId);
      setShowPageSelector(false);
    }
  }, [block.properties?.subpageData?.pageId]);

  const selectPage = (pageId: string) => {
    const selectedPage = workspace.pages.find(p => p.id === pageId);
    if (!selectedPage) return;

    setSelectedPageId(pageId);
    setShowPageSelector(false);

    onUpdate({
      content: selectedPage.title,
      properties: {
        ...block.properties,
        subpageData: {
          pageId: selectedPage.id,
          pageTitle: selectedPage.title,
          pageIcon: selectedPage.icon
        }
      }
    });
  };

  const changePage = () => {
    setShowPageSelector(true);
  };

  const navigateToPage = () => {
    if (selectedPageId && onNavigateToPage) {
      onNavigateToPage(selectedPageId);
    }
  };

  if (showPageSelector) {
    return (
          <div className="w-full p-4 border border-border rounded-lg bg-muted/50 subpage-selector">
      <div className="mb-3 text-sm font-medium text-foreground">
          Select a page to link to:
        </div>
        <div className="space-y-2">
          {workspace.pages.map((page) => (
            <button
              key={page.id}
              onClick={() => selectPage(page.id)}
              className="w-full text-left p-3 border border-border rounded-lg hover:bg-background hover:border-primary/50 transition-colors bg-background page-option"
            >
              <div className="flex items-center gap-3">
                <div className="text-lg">
                  {page.icon || '📄'}
                </div>
                <div>
                              <div className="font-medium text-foreground">
              {page.title || 'Untitled'}
            </div>
            <div className="text-xs text-muted-foreground">
                    {page.blocks.length} block{page.blocks.length !== 1 ? 's' : ''}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
        {workspace.pages.length === 0 && (
          <div className="text-sm text-muted-foreground p-3 text-center">
            No pages available to link to
          </div>
        )}
      </div>
    );
  }

  const linkedPage = workspace.pages.find(p => p.id === selectedPageId);
  
  if (!linkedPage) {
    return (
      <div className="w-full p-4 border border-destructive/20 rounded-lg bg-destructive/10">
        <div className="flex items-center gap-2 text-red-600">
          <FileText className="h-4 w-4" />
          <span className="text-sm">Page not found</span>
        </div>
        {isFocused && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowPageSelector(true)}
            className="mt-2 text-red-600 hover:text-red-700"
          >
            Select different page
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="w-full subpage-block">
      <div 
        className="flex items-center gap-3 p-4 border border-border rounded-lg hover:bg-muted/30 transition-colors cursor-pointer group subpage-card"
        onClick={navigateToPage}
      >
        <div className="text-lg flex-shrink-0">
          {linkedPage.icon || '📄'}
        </div>
        <div className="flex-1 min-w-0">
                  <div className="font-medium text-foreground group-hover:text-primary transition-colors">
          {linkedPage.title || 'Untitled'}
        </div>
        <div className="text-xs text-muted-foreground">
            {linkedPage.blocks.length} block{linkedPage.blocks.length !== 1 ? 's' : ''} • 
            Last updated {new Date(linkedPage.updatedAt).toLocaleDateString()}
          </div>
        </div>
        <ExternalLink className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>
      
      {isFocused && (
        <div className="flex gap-2 mt-2">
          <Button
            size="sm"
            variant="outline"
            onClick={changePage}
          >
            Change page
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={navigateToPage}
          >
            Go to page
          </Button>
        </div>
      )}
    </div>
  );
}; 