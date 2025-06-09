import { useState, useRef, useEffect } from 'react';
import { Database, Plus, Minus, Edit3, MoreHorizontal, Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface EditableTableDisplayProps {
  headers: string[];
  rows: string[][];
  onUpdateCell: (rowIndex: number, colIndex: number, value: string) => void;
  onUpdateHeader: (colIndex: number, value: string) => void;
  onAddRow: () => void;
  onAddColumn: () => void;
  onRemoveRow: () => void;
  onRemoveColumn: () => void;
  onRemoveSpecificRow?: (rowIndex: number) => void;
  onRemoveSpecificColumn?: (colIndex: number) => void;
  onUpdateTitle?: (title: string) => void;
  title?: string;
  className?: string;
  isFocused?: boolean;
  minRows?: number;
  minCols?: number;
}

export const EditableTableDisplay = ({
  headers,
  rows,
  onUpdateCell,
  onUpdateHeader,
  onAddRow,
  onAddColumn,
  onRemoveRow,
  onRemoveColumn,
  onRemoveSpecificRow,
  onRemoveSpecificColumn,
  onUpdateTitle,
  title = "Data Table",
  className = "",
  isFocused = false,
  minRows = 1,
  minCols = 1
}: EditableTableDisplayProps) => {
  const [editingCell, setEditingCell] = useState<{row: number, col: number} | null>(null);
  const [editingHeader, setEditingHeader] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [columnWidths, setColumnWidths] = useState<number[]>([]);
  const [resizing, setResizing] = useState<{colIndex: number, startX: number, startWidth: number} | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    show: boolean;
    x: number;
    y: number;
    type: 'row' | 'column';
    index: number;
  } | null>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  const canRemoveRow = rows.length > minRows;
  const canRemoveCol = headers.length > minCols;

  // Initialize column widths
  useEffect(() => {
    if (columnWidths.length !== headers.length) {
      setColumnWidths(new Array(headers.length).fill(150)); // Default 150px width
    }
  }, [headers.length, columnWidths.length]);

  // Handle clicks outside context menu
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        setContextMenu(null);
      }
    };

    if (contextMenu?.show) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [contextMenu]);

  // Handle column resizing
  const handleMouseDown = (e: React.MouseEvent, colIndex: number) => {
    e.preventDefault();
    e.stopPropagation();
    
    const startX = e.clientX;
    const startWidth = columnWidths[colIndex] || 150;
    
    setResizing({ colIndex, startX, startWidth });
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizing) return;
      
      const deltaX = e.clientX - resizing.startX;
      const newWidth = Math.max(80, resizing.startWidth + deltaX); // Minimum 80px width
      
      setColumnWidths(prev => {
        const newWidths = [...prev];
        newWidths[resizing.colIndex] = newWidth;
        return newWidths;
      });
    };

    const handleMouseUp = () => {
      setResizing(null);
    };

    if (resizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [resizing]);

  const handleCellKeyDown = (e: React.KeyboardEvent, rowIndex: number, cellIndex: number) => {
    if (e.key === 'Enter') {
      // Move to next cell or add new row
      if (cellIndex < headers.length - 1) {
        setEditingCell({row: rowIndex, col: cellIndex + 1});
      } else if (rowIndex < rows.length - 1) {
        setEditingCell({row: rowIndex + 1, col: 0});
      } else {
        // At the last cell, add new row
        onAddRow();
        setTimeout(() => {
          setEditingCell({row: rowIndex + 1, col: 0});
        }, 50);
      }
    } else if (e.key === 'Tab') {
      e.preventDefault();
      if (e.shiftKey) {
        // Move to previous cell
        if (cellIndex > 0) {
          setEditingCell({row: rowIndex, col: cellIndex - 1});
        } else if (rowIndex > 0) {
          setEditingCell({row: rowIndex - 1, col: headers.length - 1});
        }
      } else {
        // Move to next cell or add new column if at last column
        if (cellIndex < headers.length - 1) {
          setEditingCell({row: rowIndex, col: cellIndex + 1});
        } else if (rowIndex < rows.length - 1) {
          setEditingCell({row: rowIndex + 1, col: 0});
        } else {
          // At the last cell of last row, add new column
          onAddColumn();
          setTimeout(() => {
            setEditingCell({row: rowIndex, col: cellIndex + 1});
          }, 50);
        }
      }
    } else if (e.key === 'Escape') {
      setEditingCell(null);
    }
  };

  const handleColumnContextMenu = (e: React.MouseEvent, colIndex: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      show: true,
      x: e.clientX,
      y: e.clientY,
      type: 'column',
      index: colIndex
    });
  };

  const handleRowContextMenu = (e: React.MouseEvent, rowIndex: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      show: true,
      x: e.clientX,
      y: e.clientY,
      type: 'row',
      index: rowIndex
    });
  };

  const handleDeleteColumn = () => {
    if (contextMenu && contextMenu.type === 'column' && onRemoveSpecificColumn) {
      onRemoveSpecificColumn(contextMenu.index);
    }
    setContextMenu(null);
  };

  const handleDeleteRow = () => {
    if (contextMenu && contextMenu.type === 'row' && onRemoveSpecificRow) {
      onRemoveSpecificRow(contextMenu.index);
    }
    setContextMenu(null);
  };

  return (
    <div 
      className={cn("w-full group table-display relative", className)}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
      // Prevent block selection when interacting with table
      onMouseDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Editable Title */}
      <div className="mb-4">
        {editingTitle ? (
          <input
            type="text"
            value={title}
            onChange={(e) => onUpdateTitle?.(e.target.value)}
            onBlur={() => setEditingTitle(false)}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === 'Enter' || e.key === 'Escape') {
                setEditingTitle(false);
              }
            }}
            onClick={(e) => e.stopPropagation()}
            className="text-2xl font-bold text-foreground bg-transparent border-none outline-none placeholder-muted-foreground w-full"
            placeholder="Table Title"
            autoFocus
          />
        ) : (
          <div 
            className="group/title cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              if (onUpdateTitle) {
                setEditingTitle(true);
              }
            }}
          >
            <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
              {title}
              {isFocused && onUpdateTitle && (
                <Edit3 className="h-4 w-4 text-muted-foreground opacity-0 group-hover/title:opacity-100 transition-opacity" />
              )}
            </h2>
          </div>
        )}
      </div>

      {/* Header with controls */}
      <div className="flex items-center justify-between mb-3 px-1 min-h-[28px]">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            {rows.length} {rows.length === 1 ? 'row' : 'rows'}, {headers.length} {headers.length === 1 ? 'column' : 'columns'}
          </span>
        </div>
        
        <div className="flex items-center gap-1">
          <div className={cn(
            "flex items-center gap-1 transition-all duration-150",
            (isFocused || showControls) ? "visible opacity-100" : "invisible opacity-0"
          )}>
            <Button size="sm" variant="ghost" onClick={onAddRow} className="h-7 px-2 text-xs">
              <Plus className="h-3 w-3 mr-1" />
              Row
            </Button>
            <Button size="sm" variant="ghost" onClick={onAddColumn} className="h-7 px-2 text-xs">
              <Plus className="h-3 w-3 mr-1" />
              Column
            </Button>
            <div className="w-px h-4 bg-border mx-1" />
            <Button 
              size="sm" 
              variant="ghost" 
              onClick={onRemoveRow} 
              disabled={!canRemoveRow}
              className={cn("h-7 px-2 text-xs", !canRemoveRow && "opacity-30")}
            >
              <Minus className="h-3 w-3 mr-1" />
              Row
            </Button>
            <Button 
              size="sm" 
              variant="ghost" 
              onClick={onRemoveColumn} 
              disabled={!canRemoveCol}
              className={cn("h-7 px-2 text-xs", !canRemoveCol && "opacity-30")}
            >
              <Minus className="h-3 w-3 mr-1" />
              Column
            </Button>
          </div>
        </div>
      </div>
      
      {/* Table with resizable columns */}
      <div className="w-full overflow-x-auto">
        <table ref={tableRef} className="w-full table-fixed" style={{ minWidth: 'max-content' }}>
          {/* Headers with resize handles */}
          <thead>
            <tr className="border-b border-border">
              {headers.map((header, index) => (
                <th 
                  key={index} 
                  className="text-left py-2 px-3 group/header relative bg-muted/50 border-r border-border last:border-r-0"
                  style={{ width: columnWidths[index] || 150 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingHeader(index);
                  }}
                  onContextMenu={(e) => handleColumnContextMenu(e, index)}
                >
                  {editingHeader === index ? (
                    <input
                      type="text"
                      value={header}
                      onChange={(e) => onUpdateHeader(index, e.target.value)}
                      onBlur={() => setEditingHeader(null)}
                      onKeyDown={(e) => {
                        e.stopPropagation();
                        if (e.key === 'Enter' || e.key === 'Escape') {
                          setEditingHeader(null);
                        }
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full bg-transparent border-none outline-none font-medium text-sm text-muted-foreground placeholder-muted-foreground"
                      placeholder={`Column ${index + 1}`}
                      autoFocus
                    />
                  ) : (
                    <div className="flex items-center gap-2 cursor-pointer">
                      <span className="font-medium text-sm text-muted-foreground truncate">
                        {header || `Column ${index + 1}`}
                      </span>
                      {isFocused && (
                        <Edit3 className="h-3 w-3 text-muted-foreground opacity-0 group-hover/header:opacity-100 transition-opacity" />
                      )}
                    </div>
                  )}
                  
                  {/* Resize handle */}
                  <div
                    className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-ring transition-colors opacity-0 group-hover/header:opacity-100"
                    onMouseDown={(e) => handleMouseDown(e, index)}
                  />
                </th>
              ))}
            </tr>
          </thead>
          
          {/* Body */}
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr 
                key={rowIndex} 
                className="border-b border-border/50 hover:bg-accent/30 transition-colors duration-150 group/row"
                onContextMenu={(e) => handleRowContextMenu(e, rowIndex)}
              >
                {row.map((cell, cellIndex) => (
                  <td 
                    key={cellIndex} 
                    className="py-2 px-3 text-sm text-foreground group/cell relative cursor-text border-r border-border/50 last:border-r-0"
                    style={{ width: columnWidths[cellIndex] || 150 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingCell({row: rowIndex, col: cellIndex});
                    }}
                  >
                    {editingCell?.row === rowIndex && editingCell?.col === cellIndex ? (
                      <textarea
                        value={cell}
                        onChange={(e) => onUpdateCell(rowIndex, cellIndex, e.target.value)}
                        onBlur={() => setEditingCell(null)}
                        onKeyDown={(e) => {
                          e.stopPropagation();
                          handleCellKeyDown(e, rowIndex, cellIndex);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-full bg-transparent border-none outline-none placeholder-muted-foreground resize-none"
                        placeholder="Type something..."
                        autoFocus
                        rows={1}
                        style={{ 
                          minHeight: '20px',
                          maxHeight: '120px',
                          overflow: 'hidden'
                        }}
                        onInput={(e) => {
                          // Auto-resize textarea
                          const target = e.target as HTMLTextAreaElement;
                          target.style.height = 'auto';
                          target.style.height = Math.min(target.scrollHeight, 120) + 'px';
                        }}
                      />
                    ) : (
                      <div className="flex items-center min-h-[20px]">
                        <span className="whitespace-pre-wrap flex-1 break-words">
                          {cell || (
                            <span className="text-muted-foreground italic">
                              {isFocused ? 'Empty' : ''}
                            </span>
                          )}
                        </span>
                        {isFocused && cell && (
                          <Edit3 className="h-3 w-3 text-muted-foreground opacity-0 group-hover/cell:opacity-100 transition-opacity ml-2 flex-shrink-0" />
                        )}
                      </div>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Context Menu */}
      {contextMenu?.show && (
        <div
          ref={contextMenuRef}
          className="fixed bg-card border border-border rounded-md shadow-lg py-1 z-50 min-w-[140px]"
          style={{
            left: contextMenu.x,
            top: contextMenu.y,
          }}
        >
          {contextMenu.type === 'column' ? (
            <button
              onClick={handleDeleteColumn}
              disabled={!canRemoveCol}
              className={cn(
                "w-full text-left px-3 py-2 text-sm hover:bg-accent flex items-center gap-2 text-red-600",
                !canRemoveCol && "opacity-50 cursor-not-allowed"
              )}
            >
              <Trash2 className="h-4 w-4" />
              Delete Column
            </button>
          ) : (
            <button
              onClick={handleDeleteRow}
              disabled={!canRemoveRow}
              className={cn(
                "w-full text-left px-3 py-2 text-sm hover:bg-accent flex items-center gap-2 text-red-600",
                !canRemoveRow && "opacity-50 cursor-not-allowed"
              )}
            >
              <Trash2 className="h-4 w-4" />
              Delete Row
            </button>
          )}
        </div>
      )}

      {/* Help text */}
      {isFocused && (
        <div className="mt-3 px-1 text-xs text-muted-foreground">
          Click any cell to edit • Press <kbd className="px-1 py-0.5 bg-muted text-muted-foreground rounded text-xs">Enter</kbd> to move down • Press <kbd className="px-1 py-0.5 bg-muted text-muted-foreground rounded text-xs">Tab</kbd> to move right (creates new column at end) • Drag column borders to resize • Right-click headers or rows to delete
        </div>
      )}
    </div>
  );
}; 