import React from 'react';

interface SelectionDemoProps {}

export const SelectionDemo: React.FC<SelectionDemoProps> = () => {
  return (
    <div className="p-4 bg-gray-50 border rounded-lg">
      <h3 className="text-lg font-semibold mb-2">Block Selection Guide</h3>
      <div className="space-y-2 text-sm text-gray-700">
        <p><strong>Single Selection:</strong> Click on any block</p>
        <p><strong>Multi-Selection:</strong> Hold Ctrl/Cmd and click multiple blocks</p>
        <p><strong>Range Selection:</strong> Select one block, then hold Shift and click another block</p>
        <p><strong>Select All:</strong> Press Ctrl/Cmd + A</p>
        <p><strong>Clear Selection:</strong> Press Escape or click elsewhere</p>
        <p><strong>Delete Selected:</strong> Press Ctrl/Cmd + Backspace</p>
        <p><strong>Drag to Reorder:</strong> Drag the grip handle to move blocks</p>
      </div>
    </div>
  );
}; 