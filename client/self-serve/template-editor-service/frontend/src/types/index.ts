export interface Template {
  version: string;
  name: string;
  description?: string;
  hash: string;
  schema?: Record<string, any>;
  created_at: string;
  category?: string;
  format?: string;
}

export interface DeploymentScenario {
  id: string;
  name: string;
  description: string;
  category: string;
  template_versions: string[];
  dependencies: {
    cross_file_variables: Record<string, string[]>;
    validation_rules: any[];
  };
  variable_mappings: {
    shared_variables: string[];
    role_mappings?: string[];
  };
  created_at: string;
}

export interface Session {
  id: string;
  user_id: string;
  scenario_id?: string;
  template_version?: string;
  template_hash?: string;
  status: 'active' | 'completed' | 'failed';
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface SessionTemplate {
  id: number;
  session_id: string;
  template_version: string;
  template_hash: string;
  status: string;
  variables?: Record<string, string>;
  created_at: string;
}

export interface FileContent {
  path: string;
  content: string;
  hash: string;
  original_template?: string;
  template_version?: string;
  template_category?: string;
  template_format?: string;
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

export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: any;
  error?: string;
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
  toolCalls?: ToolCall[];
  isToolCallUpdate?: boolean;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  similarity_score?: number;
}

export interface SessionCreateRequest {
  user_id: string;
  scenario_id?: string;
  template_version?: string;
  project_context?: Record<string, any>;
  variables?: Record<string, string>;
}

export interface ScenarioValidationRequest {
  scenario_id: string;
  variables: Record<string, string>;
}

export interface ScenarioValidationResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
}