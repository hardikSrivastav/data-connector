export interface Block {
  id: string;
  type: 'text' | 'heading1' | 'heading2' | 'heading3' | 'bullet' | 'numbered' | 'quote' | 'divider' | 'image' | 'code';
  content: string;
  isSelected?: boolean;
  properties?: {
    bold?: boolean;
    italic?: boolean;
    strikethrough?: boolean;
    code?: boolean;
    color?: string;
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
