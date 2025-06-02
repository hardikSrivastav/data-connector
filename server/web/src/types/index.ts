export interface Block {
  id: string;
  type: 'text' | 'heading1' | 'heading2' | 'heading3' | 'bullet' | 'numbered' | 'quote' | 'divider' | 'image' | 'code' | 'subpage' | 'table' | 'toggle' | 'canvas';
  content: string;
  order: number;
  isSelected?: boolean;
  properties?: {
    bold?: boolean;
    italic?: boolean;
    strikethrough?: boolean;
    code?: boolean;
    color?: string;
    // Table-specific properties
    tableData?: {
      rows: number;
      cols: number;
      data: string[][];
      headers?: string[];
    };
    // Toggle-specific properties
    toggleData?: {
      isOpen: boolean;
      children: Block[];
    };
    // Subpage-specific properties
    subpageData?: {
      pageId: string;
      pageTitle: string;
      pageIcon?: string;
    };
    // Canvas-specific properties
    canvasData?: {
      threadId: string;
      threadName: string;
      isExpanded: boolean;
      workspaceId: string;
      pageId: string;
      blockId: string;
      canvasPageId?: string;
      parentPageId?: string;
      blocks?: Block[];
      // Full analysis data
      fullAnalysis?: string;
      sqlQuery?: string;
      fullData?: {
        headers: string[];
        rows: any[][];
        totalRows: number;
      };
      preview?: {
        summary: string;
        stats: Array<{label: string, value: string}>;
        tablePreview: {
          headers: string[];
          rows: any[][];
          totalRows: number;
        };
        charts?: Array<{type: string, title: string}>;
      };
    };
    // Canvas page identification
    isCanvasPage?: boolean;
  };
}

export interface Page {
  id: string;
  title: string;
  icon?: string;
  blocks: Block[];
  createdAt: Date;
  updatedAt: Date;
}

export interface Workspace {
  id: string;
  name: string;
  pages: Page[];
}
