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
  const { storageManager, saveWorkspace, clearCache, deleteBlock: deleteBlockFromStorage, deletePage: deletePageFromStorage } = useStorageManager({
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
        console.log('🔄 useWorkspace: Loading workspace from storage...');
        const savedWorkspace = await storageManager.getWorkspace('main');
        if (savedWorkspace) {
          console.log('✅ useWorkspace: Workspace loaded from storage:', {
            id: savedWorkspace.id,
            name: savedWorkspace.name,
            pagesCount: savedWorkspace.pages.length,
            pages: savedWorkspace.pages.map(p => ({
              id: p.id,
              title: p.title,
              blocksCount: p.blocks.length
            }))
          });
          
          // Ensure all pages have their blocks sorted by order
          let workspaceWithSortedBlocks = {
            ...savedWorkspace,
            pages: savedWorkspace.pages.map(page => ({
              ...page,
              blocks: [...page.blocks].sort((a, b) => a.order - b.order)
            }))
          };
          
          // Clean up orphaned Canvas pages (pages that were referenced by Canvas blocks that no longer exist)
          console.log('🧹 useWorkspace: Checking for orphaned Canvas pages...');
          const allCanvasPageIds = new Set<string>();
          
          // Collect all canvas page IDs referenced by existing Canvas blocks
          workspaceWithSortedBlocks.pages.forEach(page => {
            page.blocks.forEach(block => {
              if (block.type === 'canvas' && block.properties?.canvasPageId) {
                allCanvasPageIds.add(block.properties.canvasPageId);
              }
            });
          });
          
          // Find pages that might be orphaned Canvas pages
          const orphanedCanvasPages: string[] = [];
          workspaceWithSortedBlocks.pages.forEach(page => {
            // A page is potentially orphaned if:
            // 1. It's not referenced by any Canvas block
            // 2. AND it has very little content (suggesting it was auto-generated)
            // 3. AND its title suggests it was a Canvas page
            if (!allCanvasPageIds.has(page.id)) {
              const hasMinimalContent = page.blocks.length <= 2 && 
                page.blocks.every(block => 
                  block.type === 'heading1' || 
                  block.type === 'divider' || 
                  (block.type === 'text' && block.content.trim().length === 0)
                );
              
              const hasCanvasTitle = page.title.toLowerCase().includes('canvas') || 
                page.title.toLowerCase().includes('analysis') ||
                page.icon === '🎨';
              
              if (hasMinimalContent && hasCanvasTitle) {
                console.log('🗑️ useWorkspace: Found orphaned Canvas page:', {
                  id: page.id,
                  title: page.title,
                  icon: page.icon,
                  blocks: page.blocks.length
                });
                orphanedCanvasPages.push(page.id);
              }
            }
          });
          
          // Remove orphaned Canvas pages
          if (orphanedCanvasPages.length > 0) {
            console.log(`🧹 useWorkspace: Removing ${orphanedCanvasPages.length} orphaned Canvas pages:`, orphanedCanvasPages);
            workspaceWithSortedBlocks = {
              ...workspaceWithSortedBlocks,
              pages: workspaceWithSortedBlocks.pages.filter(page => !orphanedCanvasPages.includes(page.id))
            };
            
            // Also delete them from storage
            for (const pageId of orphanedCanvasPages) {
              try {
                await deletePageFromStorage(pageId);
                console.log('✅ useWorkspace: Deleted orphaned Canvas page from storage:', pageId);
              } catch (error) {
                console.warn('⚠️ useWorkspace: Failed to delete orphaned Canvas page from storage:', pageId, error);
              }
            }
          } else {
            console.log('✅ useWorkspace: No orphaned Canvas pages found');
          }
          
          setWorkspace(workspaceWithSortedBlocks);
          // Set current page to first page or saved current page
          const firstPageId = workspaceWithSortedBlocks.pages[0]?.id || 'default';
          const currentPageIdFromStorage = localStorage.getItem('currentPageId') || firstPageId;
          console.log('🎯 useWorkspace: Setting current page ID:', currentPageIdFromStorage);
          setCurrentPageId(currentPageIdFromStorage);
        } else {
          console.log('⚠️ useWorkspace: No saved workspace found, using default');
        }
      } catch (error) {
        console.warn('❌ useWorkspace: Failed to load workspace from storage:', error);
      } finally {
        setIsLoaded(true);
      }
    };

    loadWorkspace();
  }, [storageManager, deletePageFromStorage]);

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

  const currentPage = (() => {
    const page = workspace.pages.find(p => p.id === currentPageId) || defaultPage;
    // Always ensure blocks are sorted by order
    return {
      ...page,
      blocks: [...page.blocks].sort((a, b) => a.order - b.order)
    };
  })();

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
    console.log(`📄 useWorkspace: updatePage called with pageId='${pageId}'`);
    console.log(`📄 useWorkspace: Updates:`, {
      hasBlocks: !!updates.blocks,
      blocksCount: updates.blocks?.length,
      hasTitle: !!updates.title,
      title: updates.title,
      otherKeys: Object.keys(updates).filter(k => k !== 'blocks' && k !== 'title')
    });
    
    // Debug canvas-specific data
    if (updates.blocks) {
      console.log(`📄 useWorkspace: ${updates.blocks.length} blocks being updated`);
    }
    
    setWorkspace(prev => {
      const updatedWorkspace = {
        ...prev,
        pages: prev.pages.map(page => 
          page.id === pageId 
            ? { ...page, ...updates, updatedAt: new Date() }
            : page
        )
      };
      
      const updatedPage = updatedWorkspace.pages.find(p => p.id === pageId);
      console.log(`📄 useWorkspace: Page after update:`, {
        pageId: updatedPage?.id,
        blocksCount: updatedPage?.blocks?.length,
        title: updatedPage?.title
      });
      
      return updatedWorkspace;
    });
    
    console.log(`✅ useWorkspace: updatePage completed for pageId='${pageId}'`);
  };

  const deletePage = async (pageId: string) => {
    if (workspace.pages.length <= 1) return;
    
    const pageIndex = workspace.pages.findIndex(p => p.id === pageId);
    
    // First, clean up any canvas references to this page across all pages
    const updatedPages = workspace.pages.map(page => {
      const updatedBlocks = page.blocks.map(block => {
        // Check if this is a canvas block with a reference to the deleted page
        if (block.type === 'canvas' && 
            block.properties?.canvasData?.canvasPageId === pageId) {
          
          console.log(`Cleaning up canvas reference in block ${block.id} on page ${page.id}`);
          
          // Remove the broken reference
          return {
            ...block,
            properties: {
              ...block.properties,
              canvasData: {
                ...block.properties.canvasData,
                canvasPageId: undefined
              }
            }
          };
        }
        return block;
      });
      
      // Only return updated page if blocks were actually changed
      if (updatedBlocks.some((block, index) => block !== page.blocks[index])) {
        return { ...page, blocks: updatedBlocks, updatedAt: new Date() };
      }
      return page;
    });
    
    // Update workspace with cleaned references and remove the deleted page
    setWorkspace(prev => ({
      ...prev,
      pages: updatedPages.filter(page => page.id !== pageId)
    }));
    
    if (currentPageId === pageId) {
      const newCurrentIndex = Math.max(0, pageIndex - 1);
      setCurrentPageId(workspace.pages[newCurrentIndex]?.id || workspace.pages[0]?.id);
    }
    
    // Delete the page from storage properly
    try {
      await deletePageFromStorage(pageId);
      console.log('Page deleted from storage:', pageId);
    } catch (error) {
      console.warn('Failed to delete page from storage:', error);
    }
  };

  const updateBlock = async (blockId: string, updates: Partial<Block>) => {
    console.log(`🏗️ useWorkspace: updateBlock called with blockId='${blockId}'`);
    console.log(`🏗️ useWorkspace: Updates:`, updates);
    console.log(`🏗️ useWorkspace: Current page blocks:`, currentPage.blocks.length);
    
    const existingBlock = currentPage.blocks.find(block => block.id === blockId);
    if (!existingBlock) {
      console.error(`❌ useWorkspace: Block with id '${blockId}' not found!`);
      console.log(`🏗️ useWorkspace: Available block IDs:`, currentPage.blocks.map(b => b.id));
      return;
    }
    
    console.log(`🏗️ useWorkspace: Found existing block:`, {
      id: existingBlock.id,
      type: existingBlock.type,
      content_length: existingBlock.content?.length || 0,
      content_preview: existingBlock.content?.substring(0, 50) || 'No content'
    });
    
    const updatedBlocks = currentPage.blocks.map(block =>
      block.id === blockId ? { ...block, ...updates } : block
    );
    
    const updatedBlock = updatedBlocks.find(b => b.id === blockId);
    console.log(`🏗️ useWorkspace: Block after update:`, {
      id: updatedBlock?.id,
      type: updatedBlock?.type,
      content_length: updatedBlock?.content?.length || 0,
      content_preview: updatedBlock?.content?.substring(0, 50) || 'No content'
    });
    
    // Check if the updated block is the first H1 and sync its content to page title
    const firstBlock = updatedBlocks.find(block => block.order === 0);
    if (firstBlock && firstBlock.id === blockId && firstBlock.type === 'heading1' && updates.content !== undefined) {
      // Sync the H1 content to the page title
      console.log(`🏗️ useWorkspace: Syncing H1 content to page title:`, updates.content);
      updatePage(currentPageId, { 
        blocks: updatedBlocks,
        title: updates.content || 'Untitled'
      });
    } else {
      console.log(`🏗️ useWorkspace: Updating page with new blocks array`);
      updatePage(currentPageId, { blocks: updatedBlocks });
    }

    // Save block immediately for real-time updates
    try {
      const updatedBlock = updatedBlocks.find(b => b.id === blockId);
      if (updatedBlock) {
        console.log(`🏗️ useWorkspace: Saving block to storage manager...`);
        await storageManager.saveBlock(updatedBlock, currentPageId);
        console.log(`✅ useWorkspace: Block saved successfully`);
      }
    } catch (error) {
      console.warn('Failed to save block:', error);
    }
    
    console.log(`✅ useWorkspace: updateBlock completed for blockId='${blockId}'`);
  };

  const addBlock = (afterBlockId?: string, type: Block['type'] = 'text') => {
    const blocks = [...currentPage.blocks];
    let newOrder: number;
    
    if (afterBlockId) {
      const index = blocks.findIndex(b => b.id === afterBlockId);
      if (index >= 0) {
        newOrder = blocks[index].order + 0.5; // Insert between existing orders
      } else {
        console.warn(`addBlock: Block with ID ${afterBlockId} not found, adding at end`);
        newOrder = blocks.length > 0 ? Math.max(...blocks.map(b => b.order)) + 1 : 0;
      }
    } else {
      newOrder = blocks.length > 0 ? Math.max(...blocks.map(b => b.order)) + 1 : 0;
    }

    const newBlock: Block = {
      id: generateId(),
      type,
      content: type === 'table' ? 'Table' : type === 'toggle' ? 'Toggle' : type === 'subpage' ? 'Sub-page' : '',
      order: newOrder
    };

    // If creating a list item after another block, preserve indentation level
    if (afterBlockId && (type === 'bullet' || type === 'numbered')) {
      const afterBlock = blocks.find(b => b.id === afterBlockId);
      if (afterBlock && (afterBlock.type === 'bullet' || afterBlock.type === 'numbered')) {
        newBlock.indentLevel = afterBlock.indentLevel || 0;
      }
    }

    // Initialize properties for specific block types
    if (type === 'table') {
      newBlock.properties = {
        tableData: {
          rows: 2,
          cols: 2,
          data: [['', ''], ['', '']],
          headers: ['Column 1', 'Column 2']
        }
      };
    } else if (type === 'toggle') {
      newBlock.properties = {
        toggleData: {
          isOpen: false,
          children: []
        }
      };
    } else if (type === 'subpage') {
      newBlock.properties = {
        subpageData: {
          pageId: '',
          pageTitle: '',
          pageIcon: ''
        }
      };
    }

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
    
    // Find the block being deleted to check if it's a canvas block
    const blockToDelete = currentPage.blocks.find(b => b.id === blockId);
    console.log('Block to delete:', blockToDelete);
    
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
    
    // Special handling for canvas blocks - delete associated canvas page
    if (blockToDelete?.type === 'canvas' && blockToDelete.properties?.canvasPageId) {
      const canvasPageId = blockToDelete.properties.canvasPageId;
      console.log('🎨 Canvas block detected - cleaning up associated canvas page:', canvasPageId);
      
      // Check if the canvas page exists
      const canvasPageExists = workspace.pages.some(p => p.id === canvasPageId);
      if (canvasPageExists) {
        console.log('🗑️ Deleting associated canvas page:', canvasPageId);
        
        // Remove the canvas page from workspace
        setWorkspace(prev => ({
          ...prev,
          pages: prev.pages.filter(page => page.id !== canvasPageId)
        }));
        
        // Delete from storage
        try {
          await deletePageFromStorage(canvasPageId);
          console.log('✅ Canvas page deleted from storage:', canvasPageId);
        } catch (error) {
          console.warn('⚠️ Failed to delete canvas page from storage:', error);
        }
        
        // If we're currently viewing the canvas page that's being deleted, navigate away
        if (currentPageId === canvasPageId) {
          const remainingPages = workspace.pages.filter(p => p.id !== canvasPageId);
          if (remainingPages.length > 0) {
            setCurrentPageId(remainingPages[0].id);
          } else {
            // Create a new page if no pages remain
            const newPage = await createPage('New Page');
            setCurrentPageId(newPage.id);
          }
        }
      } else {
        console.log('📝 Canvas page does not exist or was already deleted:', canvasPageId);
      }
    }
    
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
    setWorkspace, // Expose setWorkspace for direct workspace updates
  };
};
