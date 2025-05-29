# Block Selection Feature

This document explains the multi-block selection functionality added to the Notion clone editor.

## Features

### 1. Button Layout Changes
- The grip handle and plus button now appear **side-by-side** instead of vertically stacked
- Improved width allocation from `w-16` to `w-20` to accommodate horizontal layout
- Better visual alignment with Notion's design

### 2. Multi-Block Selection

#### Selection Methods:
1. **Single Selection**: Click on any block to select it
2. **Multi-Selection**: Hold `Ctrl/Cmd` and click multiple blocks
3. **Range Selection**: Select one block, then hold `Shift` and click another to select all blocks in between
4. **Select All**: Press `Ctrl/Cmd + A` to select all blocks on the page

#### Visual Feedback:
- Selected blocks have a blue background (`bg-blue-50`) with a blue ring (`ring-2 ring-blue-200`)
- Selection indicator shows number of selected blocks
- Clear visual distinction between selected and unselected blocks

#### Keyboard Shortcuts:
- `Ctrl/Cmd + A` - Select all blocks
- `Escape` - Clear selection
- `Ctrl/Cmd + Backspace` - Delete selected blocks

### 3. Drag and Drop
- Blocks can be dragged using the grip handle
- Visual feedback during drag operations
- Automatic reordering when blocks are dropped

### 4. Selection Management
- Selection is cleared when:
  - Adding new blocks
  - Focusing on text input
  - Clicking the page title
- Bulk operations available for selected blocks:
  - Delete multiple blocks at once
  - Clear selection

## Implementation Details

### Components Modified:
1. **BlockEditor.tsx** - Added selection props and visual feedback
2. **PageEditor.tsx** - Integrated selection management
3. **types/index.ts** - Added `isSelected` property to Block interface

### New Files:
1. **hooks/useBlockSelection.ts** - Custom hook managing selection state
2. **components/SelectionDemo.tsx** - Demo component showing usage

### Key Props Added to BlockEditor:
```typescript
interface BlockEditorProps {
  // ... existing props
  isSelected?: boolean;
  onSelect?: () => void;
  onDragStart?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}
```

## Usage Example

```typescript
import { useBlockSelection } from '@/hooks/useBlockSelection';

const {
  selectedBlocks,
  selectBlock,
  clearSelection,
  handleBlockClick,
  handleDragStart,
  handleDragOver,
  handleDrop,
} = useBlockSelection(blocks);

// Use in BlockEditor
<BlockEditor
  block={block}
  isSelected={selectedBlocks.has(block.id)}
  onSelect={handleBlockSelect(block.id)}
  onDragStart={handleBlockDragStart(block.id)}
  onDragOver={handleDragOver}
  onDrop={handleBlockDrop(block.id)}
  // ... other props
/>
```

## Compatibility

This implementation maintains backward compatibility with existing block functionality while adding the new selection features. All existing keyboard shortcuts and behaviors continue to work as expected. 