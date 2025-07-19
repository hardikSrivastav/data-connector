export interface Template {
  version: string;
  name: string;
  description?: string;
  hash: string;
  schema?: Record<string, any>;
  created_at: string;
}

export interface Session {
  id: string;
  user_id: string;
  template_version: string;
  template_hash: string;
  status: 'active' | 'completed' | 'failed';
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface FileContent {
  path: string;
  content: string;
  hash: string;
  original_template?: string;
  modified?: boolean;
}

export interface WorkspaceData {
  session_id: string;
  files: FileContent[];
  metadata: {
    session_id: string;
    template_version: string;
    template_hash: string;
    created_at: string;
    files: FileContent[];
    placeholders: string[];
    schema?: Record<string, any>;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  similarity_score?: number;
}

export interface SessionCreateRequest {
  user_id: string;
  template_version: string;
  project_context?: Record<string, any>;
}