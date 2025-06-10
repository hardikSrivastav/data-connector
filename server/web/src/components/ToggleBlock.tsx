import { useState, useEffect } from 'react';
import { Block } from '@/types';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ToggleBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
  onAddBlock?: (type?: Block['type']) => void;
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
    <div className="w-full">
      <div className="flex items-center gap-1 py-1">
        <button
          onClick={toggleOpen}
          className="flex-shrink-0 p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors duration-150"
        >
          {isOpen ? (
            <ChevronDown className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          )}
        </button>
        
        <input
          type="text"
          value={title}
          onChange={(e) => updateTitle(e.target.value)}
          placeholder="Toggle"
          className="flex-1 border-none outline-none bg-transparent font-medium py-1 px-1 rounded hover:bg-gray-50 dark:hover:bg-gray-900 focus:bg-gray-50 dark:focus:bg-gray-900 transition-colors duration-150"
        />
      </div>

      {isOpen && (
        <div className="ml-5 mt-1">
          {toggleData.children.map((child, index) => (
            <div key={child.id} className="mb-1 group">
              <div className="flex items-center gap-1">
                <div className="flex-1 relative">
                  <textarea
                    value={child.content}
                    onChange={(e) => updateChildBlock(child.id, { content: e.target.value })}
                    placeholder="List item"
                    className="w-full border-none outline-none bg-transparent py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-900 focus:bg-gray-50 dark:focus:bg-gray-900 transition-colors duration-150 resize-none overflow-hidden"
                    rows={1}
                    onInput={(e) => {
                      const target = e.target as HTMLTextAreaElement;
                      target.style.height = 'auto';
                      target.style.height = target.scrollHeight + 'px';
                    }}
                  />
                  <div className="absolute left-0 top-1.5 w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-500 -ml-3 select-none pointer-events-none"></div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => removeChildBlock(child.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 h-6 w-6 p-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  ×
                </Button>
              </div>
            </div>
          ))}
          
          {isFocused && (
            <div className="mt-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={addChildBlock}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-sm px-2 py-1 h-auto"
              >
                + Add item
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}; 