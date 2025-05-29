import { useState, useEffect } from 'react';
import { Page, Block, Workspace } from '@/types';
import { useStorageManager } from './useStorageManager';

const generateId = () => Math.random().toString(36).substr(2, 9);

const defaultPage: Page = {
  id: 'default',
  title: 'Getting Started',
  icon: '👋',
  blocks: [
    {
      id: generateId(),
      type: 'heading1',
      content: 'Getting Started',
      order: 0
    },
    {
      id: generateId(),
      type: 'text',
      content: 'This is a block-based editor similar to Notion. You can:',
      order: 1
    },
    {
      id: generateId(),
      type: 'bullet',
      content: 'Create different types of content blocks',
      order: 2
    },
    {
      id: generateId(),
      type: 'bullet',
      content: 'Format text with bold, italic, and other styles',
      order: 3
    },
    {
      id: generateId(),
      type: 'bullet',
      content: 'Organize your content in pages',
      order: 4
    },
    {
      id: generateId(),
      type: 'quote',
      content: 'Start typing "/" to see available block types',
      order: 5
    }
  ],
  createdAt: new Date(),
  updatedAt: new Date()
};

const defaultWorkspace: Workspace = {
  id: 'main',
  name: 'My Workspace',
  pages: [defaultPage]
};

export const useWorkspace = () => {
  const { storageManager, saveWorkspace, clearCache, deleteBlock: deleteBlockFromStorage } = useStorageManager({
    edition: 'enterprise',
    apiBaseUrl: import.meta.env.VITE_API_BASE || 'http://localhost:8787'
  });

  const [workspace, setWorkspace] = useState<Workspace>(defaultWorkspace);
  const [currentPageId, setCurrentPageId] = useState<string>('default');
  const [isLoaded, setIsLoaded] = useState(false);

  // Load workspace from storage on mount
  useEffect(() => {
    const loadWorkspace = async () => {
      try {
        const savedWorkspace = await storageManager.getWorkspace('main');
        if (savedWorkspace) {
          setWorkspace(savedWorkspace);
          // Set current page to first page or saved current page
          const firstPageId = savedWorkspace.pages[0]?.id || 'default';
          setCurrentPageId(localStorage.getItem('currentPageId') || firstPageId);
        }
      } catch (error) {
        console.warn('Failed to load workspace from storage:', error);
      } finally {
        setIsLoaded(true);
      }
    };

    loadWorkspace();
  }, [storageManager]);

  // Save workspace changes automatically
  useEffect(() => {
    if (isLoaded) {
      const saveWorkspaceData = async () => {
        try {
          // Save the entire workspace object (which will also save individual pages)
          await saveWorkspace(workspace);
          
          // Save current page ID to localStorage
          localStorage.setItem('currentPageId', currentPageId);
        } catch (error) {
          console.warn('Failed to save workspace:', error);
        }
      };

      // Debounce saves to avoid too frequent updates
      const timeoutId = setTimeout(saveWorkspaceData, 500);
      return () => clearTimeout(timeoutId);
    }
  }, [workspace, currentPageId, saveWorkspace, isLoaded]);

  const currentPage = workspace.pages.find(p => p.id === currentPageId) || defaultPage;

  const createPage = async (title: string = 'Untitled') => {
    const newPage: Page = {
      id: generateId(),
      title,
      blocks: [{
        id: generateId(),
        type: 'heading1',
        content: title,
        order: 0
      }],
      createdAt: new Date(),
      updatedAt: new Date()
    };
    
    setWorkspace(prev => ({
      ...prev,
      pages: [...prev.pages, newPage]
    }));
    
    setCurrentPageId(newPage.id);
    
    // Save immediately for page creation
    try {
      await storageManager.savePage(newPage);
    } catch (error) {
      console.warn('Failed to save new page:', error);
    }
    
    return newPage;
  };

  const updatePage = (pageId: string, updates: Partial<Page>) => {
    setWorkspace(prev => ({
      ...prev,
      pages: prev.pages.map(page => 
        page.id === pageId 
          ? { ...page, ...updates, updatedAt: new Date() }
          : page
      )
    }));
  };

  const deletePage = async (pageId: string) => {
    if (workspace.pages.length <= 1) return;
    
    const pageIndex = workspace.pages.findIndex(p => p.id === pageId);
    setWorkspace(prev => ({
      ...prev,
      pages: prev.pages.filter(page => page.id !== pageId)
    }));
    
    if (currentPageId === pageId) {
      const newCurrentIndex = Math.max(0, pageIndex - 1);
      setCurrentPageId(workspace.pages[newCurrentIndex]?.id || workspace.pages[0]?.id);
    }
  };

  const updateBlock = async (blockId: string, updates: Partial<Block>) => {
    const updatedBlocks = currentPage.blocks.map(block =>
      block.id === blockId ? { ...block, ...updates } : block
    );
    updatePage(currentPageId, { blocks: updatedBlocks });

    // Save block immediately for real-time updates
    try {
      const updatedBlock = updatedBlocks.find(b => b.id === blockId);
      if (updatedBlock) {
        await storageManager.saveBlock(updatedBlock, currentPageId);
      }
    } catch (error) {
      console.warn('Failed to save block:', error);
    }
  };

  const addBlock = (afterBlockId?: string, type: Block['type'] = 'text') => {
    const blocks = [...currentPage.blocks];
    let newOrder: number;
    
    if (afterBlockId) {
      const index = blocks.findIndex(b => b.id === afterBlockId);
      newOrder = blocks[index].order + 0.5; // Insert between existing orders
    } else {
      newOrder = blocks.length > 0 ? Math.max(...blocks.map(b => b.order)) + 1 : 0;
    }

    const newBlock: Block = {
      id: generateId(),
      type,
      content: '',
      order: newOrder
    };

    if (afterBlockId) {
      const index = blocks.findIndex(b => b.id === afterBlockId);
      blocks.splice(index + 1, 0, newBlock);
    } else {
      blocks.push(newBlock);
    }

    // Reorder all blocks to have clean integer orders
    const reorderedBlocks = blocks.map((block, index) => ({
      ...block,
      order: index
    }));

    updatePage(currentPageId, { blocks: reorderedBlocks });
    return newBlock.id;
  };

  const deleteBlock = async (blockId: string) => {
    console.log('useWorkspace deleteBlock called with:', blockId); // Debug log
    console.log('Current blocks before deletion:', currentPage.blocks.map(b => b.id)); // Debug log
    
    let updatedBlocks = currentPage.blocks.filter(block => block.id !== blockId);
    
    // If no blocks remain, add a default empty text block
    if (updatedBlocks.length === 0) {
      updatedBlocks.push({
        id: generateId(),
        type: 'text',
        content: '',
        order: 0
      });
    } else {
      // Reorder remaining blocks to have clean sequential orders
      updatedBlocks = updatedBlocks.map((block, index) => ({
        ...block,
        order: index
      }));
    }
    
    console.log('Blocks after deletion:', updatedBlocks.map(b => b.id)); // Debug log
    updatePage(currentPageId, { blocks: updatedBlocks });
    
    // Delete the block from storage properly
    try {
      await deleteBlockFromStorage(blockId);
      console.log('Block deleted from storage:', blockId);
    } catch (error) {
      console.warn('Failed to delete block from storage:', error);
    }
  };

  const moveBlock = (blockId: string, newIndex: number) => {
    const blocks = [...currentPage.blocks];
    const blockIndex = blocks.findIndex(b => b.id === blockId);
    
    if (blockIndex === -1) return;
    
    const [movedBlock] = blocks.splice(blockIndex, 1);
    blocks.splice(newIndex, 0, movedBlock);
    
    // Reorder all blocks to have clean sequential orders
    const reorderedBlocks = blocks.map((block, index) => ({
      ...block,
      order: index
    }));
    
    updatePage(currentPageId, { blocks: reorderedBlocks });
  };

  return {
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
    isLoaded, // New: indicates if data has been loaded from storage
  };
};
