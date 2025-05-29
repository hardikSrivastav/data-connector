import { useState, useEffect } from 'react';
import { Page, Block, Workspace } from '@/types';

const generateId = () => Math.random().toString(36).substr(2, 9);

const defaultPage: Page = {
  id: 'default',
  title: 'Getting Started',
  icon: '👋',
  blocks: [
    {
      id: generateId(),
      type: 'heading1',
      content: 'Welcome to Your Notion Clone'
    },
    {
      id: generateId(),
      type: 'text',
      content: 'This is a block-based editor similar to Notion. You can:'
    },
    {
      id: generateId(),
      type: 'bullet',
      content: 'Create different types of content blocks'
    },
    {
      id: generateId(),
      type: 'bullet',
      content: 'Format text with bold, italic, and other styles'
    },
    {
      id: generateId(),
      type: 'bullet',
      content: 'Organize your content in pages'
    },
    {
      id: generateId(),
      type: 'quote',
      content: 'Start typing "/" to see available block types'
    }
  ],
  createdAt: new Date(),
  updatedAt: new Date()
};

export const useWorkspace = () => {
  const [workspace, setWorkspace] = useState<Workspace>({
    id: 'main',
    name: 'My Workspace',
    pages: [defaultPage]
  });
  
  const [currentPageId, setCurrentPageId] = useState<string>('default');

  const currentPage = workspace.pages.find(p => p.id === currentPageId) || defaultPage;

  const createPage = (title: string = 'Untitled') => {
    const newPage: Page = {
      id: generateId(),
      title,
      blocks: [{
        id: generateId(),
        type: 'text',
        content: ''
      }],
      createdAt: new Date(),
      updatedAt: new Date()
    };
    
    setWorkspace(prev => ({
      ...prev,
      pages: [...prev.pages, newPage]
    }));
    
    setCurrentPageId(newPage.id);
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

  const deletePage = (pageId: string) => {
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

  const updateBlock = (blockId: string, updates: Partial<Block>) => {
    const updatedBlocks = currentPage.blocks.map(block =>
      block.id === blockId ? { ...block, ...updates } : block
    );
    updatePage(currentPageId, { blocks: updatedBlocks });
  };

  const addBlock = (afterBlockId?: string, type: Block['type'] = 'text') => {
    const newBlock: Block = {
      id: generateId(),
      type,
      content: ''
    };

    const blocks = [...currentPage.blocks];
    if (afterBlockId) {
      const index = blocks.findIndex(b => b.id === afterBlockId);
      blocks.splice(index + 1, 0, newBlock);
    } else {
      blocks.push(newBlock);
    }

    updatePage(currentPageId, { blocks });
    return newBlock.id;
  };

  const deleteBlock = (blockId: string) => {
    console.log('useWorkspace deleteBlock called with:', blockId); // Debug log
    console.log('Current blocks before deletion:', currentPage.blocks.map(b => b.id)); // Debug log
    
    const updatedBlocks = currentPage.blocks.filter(block => block.id !== blockId);
    
    // If no blocks remain, add a default empty text block
    if (updatedBlocks.length === 0) {
      updatedBlocks.push({
        id: generateId(),
        type: 'text',
        content: ''
      });
    }
    
    console.log('Blocks after deletion:', updatedBlocks.map(b => b.id)); // Debug log
    updatePage(currentPageId, { blocks: updatedBlocks });
  };

  const moveBlock = (blockId: string, newIndex: number) => {
    const blocks = [...currentPage.blocks];
    const blockIndex = blocks.findIndex(b => b.id === blockId);
    
    if (blockIndex === -1) return;
    
    const [movedBlock] = blocks.splice(blockIndex, 1);
    blocks.splice(newIndex, 0, movedBlock);
    
    updatePage(currentPageId, { blocks });
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
    moveBlock
  };
};
