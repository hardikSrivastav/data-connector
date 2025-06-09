import { useState, useEffect, useRef, KeyboardEvent } from 'react';
import { Block } from '@/types';
import { cn } from '@/lib/utils';

interface StatsBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
  onFocus?: () => void;
  onAddBlock?: () => void;
}

interface StatItem {
  label: string;
  value: string;
  id: string;
}

export const StatsBlock = ({ block, onUpdate, isFocused, onFocus, onAddBlock }: StatsBlockProps) => {
  const statsData = block.properties?.statsData || {
    stats: [
      { id: '1', label: 'METRIC 1', value: '100' },
      { id: '2', label: 'METRIC 2', value: '25' },
      { id: '3', label: 'METRIC 3', value: '50' },
      { id: '4', label: 'METRIC 4', value: '75' }
    ],
    columns: 4
  };

  const [localData, setLocalData] = useState(statsData);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<'label' | 'value' | null>(null);
  const [selectedStatIndex, setSelectedStatIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (block.properties?.statsData) {
      setLocalData(block.properties.statsData);
    }
  }, [block.properties?.statsData]);

  // Debug isFocused prop changes
  useEffect(() => {
    console.log('StatsBlock isFocused prop changed to:', isFocused);
  }, [isFocused]);

  // Focus management
  useEffect(() => {
    if (isFocused && !editingId) {
      // Small delay to ensure the block is fully rendered
      const timer = setTimeout(() => {
        if (containerRef.current) {
          containerRef.current.focus();
          console.log('StatsBlock focused');
        }
      }, 10);
      
      return () => clearTimeout(timer);
    }
  }, [isFocused, editingId]);

  // Reset editing state when block loses focus
  useEffect(() => {
    if (!isFocused) {
      setEditingId(null);
      setEditingField(null);
      console.log('StatsBlock lost focus, clearing editing state');
    }
  }, [isFocused]);

  const updateStatsData = (newData: any) => {
    setLocalData(newData);
    onUpdate({
      properties: {
        ...block.properties,
        statsData: newData
      }
    });
  };

  const updateStat = (id: string, field: 'label' | 'value', newValue: string) => {
    const newStats = localData.stats.map(stat =>
      stat.id === id ? { ...stat, [field]: newValue } : stat
    );
    
    updateStatsData({
      ...localData,
      stats: newStats
    });
  };

  const addStat = () => {
    const newStat: StatItem = {
      id: Date.now().toString(),
      label: 'NEW METRIC',
      value: '0'
    };
    
    const newStats = [...localData.stats, newStat];
    updateStatsData({
      ...localData,
      stats: newStats
    });
    
    // Select the new stat
    setSelectedStatIndex(newStats.length - 1);
  };

  const removeStat = (index: number) => {
    if (localData.stats.length <= 1) return;
    
    const newStats = localData.stats.filter((_, i) => i !== index);
    updateStatsData({
      ...localData,
      stats: newStats
    });
    
    // Adjust selection
    setSelectedStatIndex(Math.min(index, newStats.length - 1));
  };

  const updateColumns = (columns: number) => {
    updateStatsData({
      ...localData,
      columns: Math.max(1, Math.min(6, columns))
    });
  };

  // Add global keyboard event listener when block is focused
  useEffect(() => {
    if (!isFocused) return;

    console.log('Setting up global keyboard listener for StatsBlock');

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      console.log('Raw key event:', {
        key: e.key,
        code: e.code,
        altKey: e.altKey,
        ctrlKey: e.ctrlKey,
        metaKey: e.metaKey,
        shiftKey: e.shiftKey,
        target: e.target,
        activeElement: document.activeElement?.tagName
      });

      // Only handle if we're not editing and no other input is focused
      if (editingId || document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
        console.log('Skipping event - editing or input focused');
        return;
      }

      // Try multiple approaches for adding stats
      const shouldAddStat = (
        (e.key === 'n' && e.altKey) ||
        (e.code === 'KeyN' && e.altKey) ||
        (e.key === 'n' && e.metaKey) ||  // Try Cmd+N as fallback
        (e.code === 'KeyN' && e.metaKey)
      );

      const shouldRemoveStat = (
        ((e.key === 'Backspace' || e.key === 'Delete') && e.altKey) ||
        ((e.code === 'Backspace' || e.code === 'Delete') && e.altKey) ||
        ((e.key === 'Backspace' || e.key === 'Delete') && e.metaKey) ||
        ((e.code === 'Backspace' || e.code === 'Delete') && e.metaKey)
      );

      if (shouldAddStat) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Adding stat via keyboard shortcut');
        addStat();
      } else if (shouldRemoveStat) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Removing stat via keyboard shortcut');
        removeStat(selectedStatIndex);
      }
    };

    // Add listener to document to catch all keyboard events
    document.addEventListener('keydown', handleGlobalKeyDown as any);

    // Also try adding to window as a backup
    window.addEventListener('keydown', handleGlobalKeyDown as any);

    return () => {
      console.log('Cleaning up global keyboard listener for StatsBlock');
      document.removeEventListener('keydown', handleGlobalKeyDown as any);
      window.removeEventListener('keydown', handleGlobalKeyDown as any);
    };
  }, [isFocused, editingId, selectedStatIndex, addStat, removeStat]);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (!isFocused || editingId) return;

    console.log('Container key event:', e.key, 'altKey:', e.altKey);

    switch (e.key) {
      case 'Tab':
        e.preventDefault();
        if (e.shiftKey) {
          // Go to previous stat
          setSelectedStatIndex(prev => 
            prev > 0 ? prev - 1 : localData.stats.length - 1
          );
        } else {
          // Go to next stat
          setSelectedStatIndex(prev => 
            prev < localData.stats.length - 1 ? prev + 1 : 0
          );
        }
        break;
      
      case 'Enter':
        // Check if Shift is pressed for different behavior
        if (e.shiftKey) {
          // Shift+Enter: Start editing the label of selected stat
          e.preventDefault();
          const selectedStat = localData.stats[selectedStatIndex];
          if (selectedStat) {
            setEditingId(selectedStat.id);
            setEditingField('label');
          }
        } else {
          // Enter: Create new block after this one
          e.preventDefault();
          if (onAddBlock) {
            onAddBlock();
          }
        }
        break;
      
      case ' ': // Space
        e.preventDefault();
        // Start editing the value of selected stat
        const selectedStatForValue = localData.stats[selectedStatIndex];
        if (selectedStatForValue) {
          setEditingId(selectedStatForValue.id);
          setEditingField('value');
        }
        break;
      
      case 'ArrowLeft':
        e.preventDefault();
        updateColumns(Math.max(1, localData.columns - 1));
        break;
      
      case 'ArrowRight':
        e.preventDefault();
        updateColumns(Math.min(6, localData.columns + 1));
        break;
    }
  };

  const handleEditKeyDown = (e: KeyboardEvent, statId: string, field: 'label' | 'value') => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (field === 'label') {
        // Move to editing value
        setEditingField('value');
      } else {
        // Finished editing value
        if (e.shiftKey) {
          // Shift+Enter: Create new block after finishing editing
          setEditingId(null);
          setEditingField(null);
          if (onAddBlock) {
            onAddBlock();
          }
        } else {
          // Enter: Just finish editing and stay in the stats block
          setEditingId(null);
          setEditingField(null);
          // Refocus container after editing
          setTimeout(() => {
            if (containerRef.current) {
              containerRef.current.focus();
            }
          }, 10);
        }
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setEditingId(null);
      setEditingField(null);
      // Refocus container after editing
      setTimeout(() => {
        if (containerRef.current) {
          containerRef.current.focus();
        }
      }, 10);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      if (field === 'label' && !e.shiftKey) {
        // Tab from label to value
        setEditingField('value');
      } else {
        // Exit editing mode
        setEditingId(null);
        setEditingField(null);
        // Refocus container after editing
        setTimeout(() => {
          if (containerRef.current) {
            containerRef.current.focus();
          }
        }, 10);
      }
    }
  };

  const getGridClasses = () => {
    const { columns } = localData;
    const baseClasses = "grid gap-2";
    
    switch (columns) {
      case 1: return `${baseClasses} grid-cols-1`;
      case 2: return `${baseClasses} grid-cols-1 md:grid-cols-2`;
      case 3: return `${baseClasses} grid-cols-1 md:grid-cols-3`;
      case 4: return `${baseClasses} grid-cols-2 md:grid-cols-4`;
      case 5: return `${baseClasses} grid-cols-2 md:grid-cols-5`;
      case 6: return `${baseClasses} grid-cols-2 md:grid-cols-6`;
      default: return `${baseClasses} grid-cols-2 md:grid-cols-4`;
    }
  };

  return (
    <div 
      ref={containerRef}
      className="w-full stats-block focus-within:outline-none"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      onFocus={() => {
        console.log('StatsBlock container gained focus');
        if (onFocus) {
          onFocus();
        }
      }}
      onBlur={() => console.log('StatsBlock container lost focus')}
    >
      {/* Stats Grid */}
      <div className={getGridClasses()}>
        {localData.stats.map((stat, index) => (
          <div
            key={stat.id}
            className={cn(
              "bg-muted border border-transparent rounded-md p-3 text-center transition-all",
              isFocused && selectedStatIndex === index && "border-border bg-card shadow-sm",
              !isFocused && "hover:bg-accent"
            )}
          >
            {/* Label */}
            {editingId === stat.id && editingField === 'label' ? (
              <input
                type="text"
                value={stat.label}
                onChange={(e) => updateStat(stat.id, 'label', e.target.value.toUpperCase())}
                onBlur={() => {
                  setEditingId(null);
                  setEditingField(null);
                }}
                onKeyDown={(e) => handleEditKeyDown(e, stat.id, 'label')}
                className="w-full text-xs text-muted-foreground uppercase tracking-wide text-center border-none p-0 h-auto bg-transparent focus:outline-none"
                autoFocus
              />
            ) : (
              <div className="text-xs text-muted-foreground uppercase tracking-wide">
                {stat.label}
              </div>
            )}

            {/* Value */}
            {editingId === stat.id && editingField === 'value' ? (
              <input
                type="text"
                value={stat.value}
                onChange={(e) => updateStat(stat.id, 'value', e.target.value)}
                onBlur={() => {
                  setEditingId(null);
                  setEditingField(null);
                }}
                onKeyDown={(e) => handleEditKeyDown(e, stat.id, 'value')}
                className="w-full text-lg font-semibold text-foreground mt-1 text-center border-none p-0 h-auto bg-transparent focus:outline-none"
                autoFocus
              />
            ) : (
              <div className="text-lg font-semibold text-foreground mt-1">
                {stat.value}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Subtle help text - only show when focused */}
      {isFocused && (
        <div className="mt-3 text-xs text-muted-foreground space-y-1">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-1 flex-wrap">
              <span className="inline-flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">Tab</kbd>
                <span>: navigate •</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">
                  {navigator.platform.toLowerCase().includes('mac') ? '↵' : 'Enter'}
                </kbd>
                <span>: new block •</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">Shift</kbd>
                <span>+</span>
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">
                  {navigator.platform.toLowerCase().includes('mac') ? '↵' : 'Enter'}
                </kbd>
                <span>: edit label •</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">Space</kbd>
                <span>: edit value •</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">
                  {navigator.platform.toLowerCase().includes('mac') ? '⌥' : 'Alt'}
                </kbd>
                <span>+</span>
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">N</kbd>
                <span>: add •</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">
                  {navigator.platform.toLowerCase().includes('mac') ? '⌥' : 'Alt'}
                </kbd>
                <span>+</span>
                <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-xs font-mono text-muted-foreground">Del</kbd>
                <span>: remove</span>
              </span>
            </div>
            <div>
              {localData.stats.length} stat{localData.stats.length !== 1 ? 's' : ''} • {localData.columns} col{localData.columns !== 1 ? 's' : ''} (←→ to adjust)
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 