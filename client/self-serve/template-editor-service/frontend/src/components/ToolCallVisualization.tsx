import React, { useState } from 'react';
import type { ToolCall } from '../types';

interface ToolCallVisualizationProps {
  toolCalls: ToolCall[];
}

const getToolIcon = (toolName: string): string => {
  const iconMap: Record<string, string> = {
    'read_file': '[READ]',
    'write_file': '[WRITE]',
    'edit_file': '[EDIT]',
    'multi_edit_file': '[MULTI]',
    'list_files': '[LIST]',
    'get_session_context': '[CTX]',
    'analyze_cross_file_dependencies': '[DEPS]',
    'apply_cross_file_changes': '[APPLY]',
    'validate_workspace': '[VALID]'
  };
  return iconMap[toolName] || '[TOOL]';
};

const getToolDescription = (toolCall: ToolCall): string => {
  const { name, input } = toolCall;
  
  switch (name) {
    case 'read_file':
      return `Reading ${input.file_path}`;
    case 'write_file':
      return `Writing to ${input.file_path}`;
    case 'edit_file':
      return `Editing ${input.file_path}`;
    case 'multi_edit_file':
      return `Making ${input.edits?.length || 0} edits to ${input.file_path}`;
    case 'list_files':
      return 'Listing workspace files';
    case 'get_session_context':
      return 'Getting session context';
    case 'analyze_cross_file_dependencies':
      return 'Analyzing file dependencies';
    case 'apply_cross_file_changes':
      return `Updating ${Object.keys(input.changes || {}).length} files`;
    case 'validate_workspace':
      return 'Validating workspace';
    default:
      return `Executing ${name}`;
  }
};

const getStatusColor = (status: ToolCall['status']): string => {
  switch (status) {
    case 'pending':
      return 'text-gray-500 bg-gray-100';
    case 'running':
      return 'text-blue-600 bg-blue-100';
    case 'completed':
      return 'text-green-600 bg-green-100';
    case 'failed':
      return 'text-red-600 bg-red-100';
    default:
      return 'text-gray-500 bg-gray-100';
  }
};

const getStatusIcon = (status: ToolCall['status']): string => {
  switch (status) {
    case 'pending':
      return '[PENDING]';
    case 'running':
      return '[RUNNING]';
    case 'completed':
      return '[DONE]';
    case 'failed':
      return '[FAILED]';
    default:
      return '[UNKNOWN]';
  }
};

export const ToolCallVisualization: React.FC<ToolCallVisualizationProps> = ({ toolCalls }) => {
  const [expandedCalls, setExpandedCalls] = useState<Set<string>>(new Set());

  const toggleExpanded = (callId: string) => {
    setExpandedCalls(prev => {
      const next = new Set(prev);
      if (next.has(callId)) {
        next.delete(callId);
      } else {
        next.add(callId);
      }
      return next;
    });
  };

  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  console.log('Rendering ToolCallVisualization with', toolCalls.length, 'tool calls:', toolCalls);

  return (
    <div className="border border-border rounded-lg bg-card p-3 space-y-2">
      <div className="flex items-center space-x-2 text-sm text-muted-foreground">
        <span className="font-medium">Tool Execution</span>
        <span className="text-xs bg-muted px-2 py-1 rounded">
          {toolCalls.length} {toolCalls.length === 1 ? 'call' : 'calls'}
        </span>
      </div>
      
      <div className="space-y-2">
        {toolCalls.map((toolCall) => {
          const isExpanded = expandedCalls.has(toolCall.id);
          const statusColor = getStatusColor(toolCall.status);
          
          return (
            <div key={toolCall.id} className="border border-border rounded bg-background">
              <button
                onClick={() => toggleExpanded(toolCall.id)}
                className="w-full px-3 py-2 flex items-center justify-between hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <span className="text-xs font-mono font-bold text-muted-foreground">{getToolIcon(toolCall.name)}</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium font-mono">
                      {getToolDescription(toolCall)}
                    </span>
                    <span className={`text-xs px-2 py-1 rounded-full ${statusColor} font-mono`}>
                      {getStatusIcon(toolCall.status)}
                    </span>
                  </div>
                </div>
                <span className="text-muted-foreground">
                  {isExpanded ? '▼' : '▶'}
                </span>
              </button>
              
              {isExpanded && (
                <div className="px-3 pb-3 border-t border-border bg-muted/30">
                  <div className="pt-2 space-y-2 text-xs">
                    {/* Input Details */}
                    <div>
                      <div className="text-muted-foreground font-medium mb-1">Input:</div>
                      <pre className="bg-background border border-border rounded p-2 overflow-x-auto font-mono">
                        {JSON.stringify(toolCall.input, null, 2)}
                      </pre>
                    </div>
                    
                    {/* Result/Error */}
                    {toolCall.status === 'completed' && toolCall.result && (
                      <div>
                        <div className="text-muted-foreground font-medium mb-1">Result:</div>
                        <pre className="bg-green-50 border border-green-200 rounded p-2 overflow-x-auto font-mono text-green-800">
                          {typeof toolCall.result === 'string' 
                            ? toolCall.result 
                            : JSON.stringify(toolCall.result, null, 2)}
                        </pre>
                      </div>
                    )}
                    
                    {toolCall.status === 'failed' && toolCall.error && (
                      <div>
                        <div className="text-muted-foreground font-medium mb-1">Error:</div>
                        <pre className="bg-red-50 border border-red-200 rounded p-2 overflow-x-auto font-mono text-red-800">
                          {toolCall.error}
                        </pre>
                      </div>
                    )}
                    
                    {/* Timestamp */}
                    <div className="text-muted-foreground">
                      <span className="font-medium">Time:</span> {new Date(toolCall.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};