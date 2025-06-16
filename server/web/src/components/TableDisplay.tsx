import { Database, Download, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface TableDisplayProps {
  headers: string[];
  rows: string[][];
  totalRows?: number;
  title?: string;
  className?: string;
  showControls?: boolean;
  maxRows?: number;
  onDownload?: () => void;
  onFilter?: () => void;
  isPreview?: boolean;
}

export const TableDisplay = ({
  headers,
  rows,
  totalRows,
  title = "Data Table",
  className = "",
  showControls = false,
  maxRows = 50,
  onDownload,
  onFilter,
  isPreview = false
}: TableDisplayProps) => {
  const displayRows = maxRows ? rows.slice(0, maxRows) : rows;
  const actualTotalRows = totalRows || rows.length;
  const hasMoreRows = rows.length > maxRows;

  return (
    <div className={cn("w-full", className)}>
      {/* Notion-style minimal header */}
      {(title !== "Data Table" || showControls) && (
        <div className="flex items-center justify-between mb-3 px-1">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-gray-400 dark:text-gray-500" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{title}</span>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {actualTotalRows.toLocaleString()} {actualTotalRows === 1 ? 'row' : 'rows'}
            </span>
          </div>
          
          {showControls && (
            <div className="flex items-center gap-1">
              {onFilter && (
                <Button size="sm" variant="ghost" onClick={onFilter} className="h-7 px-2 text-xs">
                  <Filter className="h-3 w-3 mr-1" />
                  Filter
                </Button>
              )}
              {onDownload && (
                <Button size="sm" variant="ghost" onClick={onDownload} className="h-7 px-2 text-xs">
                  <Download className="h-3 w-3 mr-1" />
                  Export
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Notion-style table */}
      <div className="w-full overflow-x-auto">
        <table className="w-full">
          {/* Notion-style headers */}
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              {headers.map((header, index) => (
                <th 
                  key={index} 
                  className="text-left py-2 px-3 font-medium text-sm text-gray-600 dark:text-gray-300 bg-gray-50/50 dark:bg-gray-800/50"
                >
                  {header || `Column ${index + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          
          {/* Notion-style body */}
          <tbody>
            {displayRows.map((row, rowIndex) => (
              <tr 
                key={rowIndex} 
                className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50/30 dark:hover:bg-gray-800/30 transition-colors duration-150"
              >
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="py-2 px-3 text-sm text-gray-900 dark:text-gray-100">
                    {typeof cell === 'string' && cell.length > 80 ? (
                      <div className="max-w-xs truncate" title={cell}>
                        {cell}
                      </div>
                    ) : (
                      <span className="whitespace-pre-wrap">
                        {String(cell || '')}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Notion-style footer for preview */}
      {isPreview && hasMoreRows && (
        <div className="text-center py-2 px-3 text-xs text-gray-400 dark:text-gray-500 border-t border-gray-100 dark:border-gray-800 bg-gray-50/30 dark:bg-gray-800/30">
          +{(actualTotalRows - displayRows.length).toLocaleString()} more rows
        </div>
      )}
    </div>
  );
}; 