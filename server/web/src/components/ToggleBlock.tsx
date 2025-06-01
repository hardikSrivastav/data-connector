import { useState, useEffect } from 'react';
import { Block } from '@/types';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ToggleBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
  onAddBlock?: () => void;
}

export const ToggleBlock = ({ block, onUpdate, isFocused, onAddBlock }: ToggleBlockProps) => {
  const toggleData = block.properties?.toggleData || {
    isOpen: false,
    children: []
  };

  const [isOpen, setIsOpen] = useState(toggleData.isOpen);
  const [title, setTitle] = useState(block.content || 'Toggle');

  useEffect(() => {
    if (block.properties?.toggleData) {
      setIsOpen(block.properties.toggleData.isOpen);
    }
  }, [block.properties?.toggleData?.isOpen]);

  const toggleOpen = () => {
    const newIsOpen = !isOpen;
    setIsOpen(newIsOpen);
    
    onUpdate({
      properties: {
        ...block.properties,
        toggleData: {
          ...toggleData,
          isOpen: newIsOpen
        }
      }
    });
  };

  const updateTitle = (newTitle: string) => {
    setTitle(newTitle);
    onUpdate({
      content: newTitle,
      properties: {
        ...block.properties,
        toggleData: toggleData
      }
    });
  };

  const addChildBlock = () => {
    const newChild: Block = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type: 'text',
      content: '',
      order: toggleData.children.length
    };

    const updatedChildren = [...toggleData.children, newChild];
    
    onUpdate({
      properties: {
        ...block.properties,
        toggleData: {
          ...toggleData,
          children: updatedChildren
        }
      }
    });
  };

  const updateChildBlock = (childId: string, updates: Partial<Block>) => {
    const updatedChildren = toggleData.children.map(child =>
      child.id === childId ? { ...child, ...updates } : child
    );
    
    onUpdate({
      properties: {
        ...block.properties,
        toggleData: {
          ...toggleData,
          children: updatedChildren
        }
      }
    });
  };

  const removeChildBlock = (childId: string) => {
    const updatedChildren = toggleData.children.filter(child => child.id !== childId);
    
    onUpdate({
      properties: {
        ...block.properties,
        toggleData: {
          ...toggleData,
          children: updatedChildren
        }
      }
    });
  };

  return (
    <div className="w-full toggle-block">
      <div className="flex items-center gap-2 toggle-header">
        <button
          onClick={toggleOpen}
          className="flex-shrink-0 p-1 hover:bg-gray-100 rounded transition-colors"
        >
          {isOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
        
        <input
          type="text"
          value={title}
          onChange={(e) => updateTitle(e.target.value)}
          placeholder="Toggle title"
          className="flex-1 border-none outline-none bg-transparent font-medium py-1"
        />
      </div>

      {isOpen && (
        <div className="ml-6 mt-2 border-l-2 border-gray-200 pl-4 toggle-content">
          {toggleData.children.map((child, index) => (
            <div key={child.id} className="mb-2 toggle-item group">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={child.content}
                  onChange={(e) => updateChildBlock(child.id, { content: e.target.value })}
                  placeholder="Type something..."
                  className="flex-1 border-none outline-none bg-transparent py-1 px-2 hover:bg-gray-50 rounded"
                />
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => removeChildBlock(child.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ×
                </Button>
              </div>
            </div>
          ))}
          
          {isFocused && (
            <Button
              size="sm"
              variant="ghost"
              onClick={addChildBlock}
              className="text-gray-500 hover:text-gray-700 mt-1"
            >
              + Add item
            </Button>
          )}
        </div>
      )}
    </div>
  );
}; 