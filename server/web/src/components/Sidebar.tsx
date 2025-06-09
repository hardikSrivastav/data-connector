import { useState } from 'react';
import { Plus, Search, Settings, ChevronDown, ChevronRight, FileText, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Page } from '@/types';
import { cn } from '@/lib/utils';
import { useNavigate } from 'react-router-dom';

interface SidebarProps {
  pages: Page[];
  currentPageId: string;
  onPageSelect: (pageId: string) => void;
  onPageCreate: () => void;
  onPageDelete: (pageId: string) => void;
  onPageTitleUpdate: (pageId: string, title: string) => void;
}

export const Sidebar = ({ 
  pages, 
  currentPageId, 
  onPageSelect, 
  onPageCreate, 
  onPageDelete,
  onPageTitleUpdate 
}: SidebarProps) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingPageId, setEditingPageId] = useState<string | null>(null);
  const navigate = useNavigate();

  const filteredPages = pages.filter(page => 
    page.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleTitleEdit = (pageId: string, newTitle: string) => {
    if (newTitle.trim()) {
      onPageTitleUpdate(pageId, newTitle.trim());
    }
    setEditingPageId(null);
  };

  return (
    <div 
      className={cn(
        "bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-200",
        isCollapsed ? "w-12" : "w-64"
      )}
    >
      {/* Header */}
      <div className="p-3 border-b border-sidebar-border">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="h-6 w-6 p-0 hover:bg-sidebar-accent"
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4 text-gray-600 dark:text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-600 dark:text-gray-400" />}
          </Button>
          {!isCollapsed && (
            <span className="font-semibold text-sm text-gray-900 dark:text-gray-100">My Workspace</span>
          )}
        </div>
      </div>

      {!isCollapsed && (
        <>
          {/* Search */}
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400 dark:text-gray-500" />
              <Input
                placeholder="Search pages..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-8 text-sm bg-card border-border text-foreground placeholder-muted-foreground"
              />
            </div>
          </div>

          {/* Quick Actions */}
          <div className="px-3 pb-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={onPageCreate}
              className="w-full justify-start h-8 text-sm hover:bg-sidebar-accent text-sidebar-foreground"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Page
            </Button>
          </div>

          {/* Pages List */}
          <div className="flex-1 overflow-y-auto">
            <div className="px-2">
              {filteredPages.map((page) => (
                <div
                  key={page.id}
                  className={cn(
                    "group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer hover:bg-sidebar-accent transition-colors",
                    currentPageId === page.id && "bg-sidebar-accent"
                  )}
                  onClick={() => onPageSelect(page.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-sm">{page.icon || '📄'}</span>
                    {editingPageId === page.id ? (
                      <Input
                        value={page.title}
                        onChange={(e) => onPageTitleUpdate(page.id, e.target.value)}
                        onBlur={() => setEditingPageId(null)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            handleTitleEdit(page.id, e.currentTarget.value);
                          } else if (e.key === 'Escape') {
                            setEditingPageId(null);
                          }
                        }}
                        autoFocus
                        className="h-6 text-sm bg-card border-border text-foreground"
                      />
                    ) : (
                      <span
                        className="text-sm truncate text-gray-700 dark:text-gray-300"
                        onDoubleClick={() => setEditingPageId(page.id)}
                      >
                        {page.title}
                      </span>
                    )}
                  </div>
                  {pages.length > 1 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        onPageDelete(page.id);
                      }}
                      className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-sidebar-accent text-sidebar-foreground"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-sidebar-border">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/settings')}
              className="w-full justify-start h-8 text-sm hover:bg-sidebar-accent text-sidebar-foreground"
            >
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </Button>
          </div>
        </>
      )}
    </div>
  );
};
