import { useState, useEffect } from 'react';
import { Type, Hash, List, ListOrdered, Quote, Minus, Image, Code, FileText, Table, ChevronRight, BarChart3, BarChart, TrendingUp } from 'lucide-react';
import { Block } from '@/types';
import { cn } from '@/lib/utils';

interface BlockTypeSelectorProps {
  onSelect: (type: Block['type']) => void;
  onClose: () => void;
  query: string;
}

const blockTypes = [
  { type: 'text' as const, label: 'Text', icon: Type, description: 'Just start writing with plain text.' },
  { type: 'heading1' as const, label: 'Heading 1', icon: Hash, description: 'Big section heading.' },
  { type: 'heading2' as const, label: 'Heading 2', icon: Hash, description: 'Medium section heading.' },
  { type: 'heading3' as const, label: 'Heading 3', icon: Hash, description: 'Small section heading.' },
  { type: 'bullet' as const, label: 'Bulleted list', icon: List, description: 'Create a simple bulleted list.' },
  { type: 'numbered' as const, label: 'Numbered list', icon: ListOrdered, description: 'Create a list with numbering.' },
  { type: 'quote' as const, label: 'Quote', icon: Quote, description: 'Capture a quote.' },
  { type: 'divider' as const, label: 'Divider', icon: Minus, description: 'Visually divide blocks.' },
  { type: 'code' as const, label: 'Code', icon: Code, description: 'Capture a code snippet.' },
  { type: 'table' as const, label: 'Table', icon: Table, description: 'Create a table with rows and columns.' },
  { type: 'toggle' as const, label: 'Toggle list', icon: ChevronRight, description: 'Create a collapsible toggle section.' },
  { type: 'stats' as const, label: 'Statistics', icon: BarChart, description: 'Display metrics and key statistics in a grid layout.' },
  { type: 'graphing' as const, label: 'Chart', icon: TrendingUp, description: 'Generate intelligent charts and visualizations with AI.' },
  { type: 'subpage' as const, label: 'Sub-page', icon: FileText, description: 'Link to another page in this workspace.' },
  { type: 'canvas' as const, label: 'Canvas', icon: BarChart3, description: 'Create a data analysis canvas with AI queries and visualizations.' },
];

export const BlockTypeSelector = ({ onSelect, onClose, query }: BlockTypeSelectorProps) => {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredTypes = blockTypes.filter(
    type => 
      type.label.toLowerCase().includes(query.toLowerCase()) ||
      type.description.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, filteredTypes.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredTypes[selectedIndex]) {
          onSelect(filteredTypes[selectedIndex].type);
        }
      } else if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [filteredTypes, selectedIndex, onSelect, onClose]);

  if (filteredTypes.length === 0) {
    return (
      <div className="absolute top-full left-0 bg-background border border-border rounded-lg shadow-lg p-2 min-w-80 z-50">
        <div className="text-sm text-muted-foreground p-2">No matching blocks found</div>
      </div>
    );
  }

  return (
    <div className="absolute top-full left-0 bg-background border border-border rounded-lg shadow-lg p-1 min-w-80 z-50">
      {filteredTypes.map((blockType, index) => {
        const Icon = blockType.icon;
        return (
          <div
            key={blockType.type}
            className={cn(
              "flex items-center gap-3 p-2 rounded-md cursor-pointer transition-colors",
              index === selectedIndex && "bg-accent"
            )}
            onClick={() => onSelect(blockType.type)}
            onMouseEnter={() => setSelectedIndex(index)}
          >
            <div className="flex-shrink-0">
              <Icon className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-foreground">{blockType.label}</div>
              <div className="text-xs text-muted-foreground">{blockType.description}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
