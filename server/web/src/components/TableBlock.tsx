import { useState, useEffect } from 'react';
import { Block } from '@/types';
import { EditableTableDisplay } from './EditableTableDisplay';

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
    headers: ['Column 1', 'Column 2']
  };

  const [localData, setLocalData] = useState(tableData);

  useEffect(() => {
    if (block.properties?.tableData) {
      setLocalData(block.properties.tableData);
    }
  }, [block.properties?.tableData]);

  const updateTableData = (newData: any) => {
    setLocalData(newData);
    onUpdate({
      properties: {
        ...block.properties,
        tableData: newData
      }
    });
  };

  const updateCell = (rowIndex: number, colIndex: number, value: string) => {
    const newData = [...localData.data];
    if (!newData[rowIndex]) {
      newData[rowIndex] = [];
    }
    newData[rowIndex][colIndex] = value;
    
    updateTableData({ ...localData, data: newData });
  };

  const updateHeader = (colIndex: number, value: string) => {
    const newHeaders = [...(localData.headers || [])];
    newHeaders[colIndex] = value;
    
    updateTableData({ ...localData, headers: newHeaders });
  };

  const addRow = () => {
    const newRow = new Array(localData.cols).fill('');
    const newData = [...localData.data, newRow];
    
    updateTableData({
      ...localData,
      rows: localData.rows + 1,
      data: newData
    });
  };

  const addColumn = () => {
    const newData = localData.data.map(row => [...row, '']);
    const newHeaders = [...(localData.headers || []), `Column ${localData.cols + 1}`];
    
    updateTableData({
      ...localData,
      cols: localData.cols + 1,
      data: newData,
      headers: newHeaders
    });
  };

  const removeRow = () => {
    if (localData.rows <= 1) return;
    
    const newData = localData.data.slice(0, -1);
    updateTableData({
      ...localData,
      rows: localData.rows - 1,
      data: newData
    });
  };

  const removeColumn = () => {
    if (localData.cols <= 1) return;
    
    const newData = localData.data.map(row => row.slice(0, -1));
    const newHeaders = (localData.headers || []).slice(0, -1);
    
    updateTableData({
      ...localData,
      cols: localData.cols - 1,
      data: newData,
      headers: newHeaders
    });
  };

  const removeSpecificRow = (rowIndex: number) => {
    if (localData.rows <= 1) return;
    
    const newData = localData.data.filter((_, index) => index !== rowIndex);
    updateTableData({
      ...localData,
      rows: localData.rows - 1,
      data: newData
    });
  };

  const removeSpecificColumn = (colIndex: number) => {
    if (localData.cols <= 1) return;
    
    const newData = localData.data.map(row => 
      row.filter((_, index) => index !== colIndex)
    );
    const newHeaders = (localData.headers || []).filter((_, index) => index !== colIndex);
    
    updateTableData({
      ...localData,
      cols: localData.cols - 1,
      data: newData,
      headers: newHeaders
    });
  };

  const updateTitle = (newTitle: string) => {
    onUpdate({
      content: newTitle
    });
  };

  return (
    <div className="w-full table-block">
      <EditableTableDisplay
        headers={localData.headers || []}
        rows={localData.data || []}
        onUpdateCell={updateCell}
        onUpdateHeader={updateHeader}
        onAddRow={addRow}
        onAddColumn={addColumn}
        onRemoveRow={removeRow}
        onRemoveColumn={removeColumn}
        onRemoveSpecificRow={removeSpecificRow}
        onRemoveSpecificColumn={removeSpecificColumn}
        onUpdateTitle={updateTitle}
        title={block.content || "Data Table"}
        isFocused={isFocused}
        minRows={1}
        minCols={1}
      />
    </div>
  );
}; 