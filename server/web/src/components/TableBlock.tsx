import { useState, useEffect } from 'react';
import { Block } from '@/types';
import { Button } from '@/components/ui/button';
import { Plus, Minus } from 'lucide-react';

interface TableBlockProps {
  block: Block;
  onUpdate: (updates: Partial<Block>) => void;
  isFocused: boolean;
}

export const TableBlock = ({ block, onUpdate, isFocused }: TableBlockProps) => {
  const tableData = block.properties?.tableData || {
    rows: 2,
    cols: 2,
    data: [['', ''], ['', '']],
    headers: ['', '']
  };

  const [localData, setLocalData] = useState(tableData);

  useEffect(() => {
    if (block.properties?.tableData) {
      setLocalData(block.properties.tableData);
    }
  }, [block.properties?.tableData]);

  const updateCell = (rowIndex: number, colIndex: number, value: string) => {
    const newData = [...localData.data];
    if (!newData[rowIndex]) {
      newData[rowIndex] = [];
    }
    newData[rowIndex][colIndex] = value;
    
    const updatedTableData = { ...localData, data: newData };
    setLocalData(updatedTableData);
    
    onUpdate({
      properties: {
        ...block.properties,
        tableData: updatedTableData
      }
    });
  };

  const updateHeader = (colIndex: number, value: string) => {
    const newHeaders = [...(localData.headers || [])];
    newHeaders[colIndex] = value;
    
    const updatedTableData = { ...localData, headers: newHeaders };
    setLocalData(updatedTableData);
    
    onUpdate({
      properties: {
        ...block.properties,
        tableData: updatedTableData
      }
    });
  };

  const addRow = () => {
    const newRow = new Array(localData.cols).fill('');
    const newData = [...localData.data, newRow];
    
    const updatedTableData = {
      ...localData,
      rows: localData.rows + 1,
      data: newData
    };
    setLocalData(updatedTableData);
    
    onUpdate({
      properties: {
        ...block.properties,
        tableData: updatedTableData
      }
    });
  };

  const addColumn = () => {
    const newData = localData.data.map(row => [...row, '']);
    const newHeaders = [...(localData.headers || []), ''];
    
    const updatedTableData = {
      ...localData,
      cols: localData.cols + 1,
      data: newData,
      headers: newHeaders
    };
    setLocalData(updatedTableData);
    
    onUpdate({
      properties: {
        ...block.properties,
        tableData: updatedTableData
      }
    });
  };

  const removeRow = () => {
    if (localData.rows <= 1) return;
    
    const newData = localData.data.slice(0, -1);
    const updatedTableData = {
      ...localData,
      rows: localData.rows - 1,
      data: newData
    };
    setLocalData(updatedTableData);
    
    onUpdate({
      properties: {
        ...block.properties,
        tableData: updatedTableData
      }
    });
  };

  const removeColumn = () => {
    if (localData.cols <= 1) return;
    
    const newData = localData.data.map(row => row.slice(0, -1));
    const newHeaders = (localData.headers || []).slice(0, -1);
    
    const updatedTableData = {
      ...localData,
      cols: localData.cols - 1,
      data: newData,
      headers: newHeaders
    };
    setLocalData(updatedTableData);
    
    onUpdate({
      properties: {
        ...block.properties,
        tableData: updatedTableData
      }
    });
  };

  return (
    <div className="w-full table-block">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-gray-300">
          <thead>
            <tr>
              {Array.from({ length: localData.cols }, (_, colIndex) => (
                <th key={colIndex} className="border border-gray-300 p-2 bg-gray-50">
                  <input
                    type="text"
                    value={localData.headers?.[colIndex] || ''}
                    onChange={(e) => updateHeader(colIndex, e.target.value)}
                    placeholder={`Column ${colIndex + 1}`}
                    className="w-full border-none outline-none bg-transparent font-semibold text-center"
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: localData.rows }, (_, rowIndex) => (
              <tr key={rowIndex}>
                {Array.from({ length: localData.cols }, (_, colIndex) => (
                  <td key={colIndex} className="border border-gray-300 p-2">
                    <input
                      type="text"
                      value={localData.data[rowIndex]?.[colIndex] || ''}
                      onChange={(e) => updateCell(rowIndex, colIndex, e.target.value)}
                      placeholder="Enter text"
                      className="w-full border-none outline-none bg-transparent"
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {isFocused && (
        <div className="flex gap-2 mt-2">
          <Button size="sm" variant="outline" onClick={addRow}>
            <Plus className="h-3 w-3 mr-1" />
            Add Row
          </Button>
          <Button size="sm" variant="outline" onClick={addColumn}>
            <Plus className="h-3 w-3 mr-1" />
            Add Column
          </Button>
          <Button size="sm" variant="outline" onClick={removeRow} disabled={localData.rows <= 1}>
            <Minus className="h-3 w-3 mr-1" />
            Remove Row
          </Button>
          <Button size="sm" variant="outline" onClick={removeColumn} disabled={localData.cols <= 1}>
            <Minus className="h-3 w-3 mr-1" />
            Remove Column
          </Button>
        </div>
      )}
    </div>
  );
}; 