"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ToolPill } from "./tool-pill";
import { ToolDetailSidebar } from "./tool-detail-sidebar";
import { ProgressPill } from "./progress-pill";

interface ParsedContent {
  type: 'text' | 'tool' | 'result' | 'progress';
  content: string;
  toolName?: string;
  toolId?: string;
  input?: string;
  result?: string;
  progress?: number;
  deploymentFiles?: any[];
  isCompleted?: boolean; // Added for tool pills
}

interface MessageRendererProps {
  content: string;
  role: 'user' | 'assistant';
  toolCalls?: {
    name: string;
    id: string;
    input?: any;
    result?: string;
  }[];
  onSidebarStateChange?: (isOpen: boolean) => void;
}

// Custom CodeBlock component with syntax highlighting
const CodeBlock: React.FC<{ children: string; className?: string; inline?: boolean }> = ({ 
  children, 
  className, 
  inline = false 
}) => {
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : 'text';
  
  if (inline) {
    return (
      <code 
        className="bg-gray-100 px-1.5 py-0.5 rounded text-sm text-gray-800"
        style={{
          fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        }}
      >
        {children}
      </code>
    );
  }
  
  return (
    <SyntaxHighlighter
      style={oneLight}
      language={language}
      customStyle={{
        margin: '12px 0',
        padding: '12px',
        fontSize: '14px',
        lineHeight: '1.5',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      }}
      codeTagProps={{
        style: {
          fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        }
      }}
    >
      {children}
    </SyntaxHighlighter>
  );
};

export const MessageRenderer: React.FC<MessageRendererProps> = ({ 
  content, 
  role, 
  toolCalls = [], 
  onSidebarStateChange 
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedTool, setSelectedTool] = useState<{
    toolName: string;
    toolId: string;
    input?: string;
    result?: string;
    isCompleted?: boolean;
  } | null>(null);

  const parseContent = (text: string): ParsedContent[] => {
    const parts: ParsedContent[] = [];
    
    // Create a map of tool data from the toolCalls prop
    const toolMap = new Map<string, { toolName: string; toolId: string; input?: any; result?: string }>();
    toolCalls.forEach(toolCall => {
      toolMap.set(toolCall.id, {
        toolName: toolCall.name,
        toolId: toolCall.id,
        input: toolCall.input,
        result: toolCall.result
      });
    });

    // Helper function to check if a tool is completed
    const isToolCompleted = (toolId: string): boolean => {
      const toolData = toolMap.get(toolId);
      return !!(toolData?.result && toolData.result !== 'Processing...');
    };

    // Helper function to format tool input for display
    const formatToolInput = (input: any): string => {
      try {
        if (typeof input === 'string') {
          return input;
        }
        return JSON.stringify(input, null, 2);
      } catch (e) {
        return String(input);
      }
    };

    // Helper function to safely parse JSON with better error handling
    const safeParseJSON = (text: string): any => {
      try {
        return JSON.parse(text);
      } catch (e) {
        // If JSON parsing fails, try to extract readable content
        console.warn('JSON parsing failed:', e, 'Text:', text);
        return null;
      }
    };

    // Helper function to detect and parse progress JSON
    const parseProgressJSON = (content: string): { progress: number; deploymentFiles?: any[]; jsonMatch?: string } | null => {
      try {
        // Find all potential JSON blocks by looking for { and matching closing }
        const findJsonBlocks = (text: string): string[] => {
          const blocks: string[] = [];
          let braceCount = 0;
          let start = -1;
          
          for (let i = 0; i < text.length; i++) {
            if (text[i] === '{') {
              if (braceCount === 0) {
                start = i;
              }
              braceCount++;
            } else if (text[i] === '}') {
              braceCount--;
              if (braceCount === 0 && start !== -1) {
                const block = text.substring(start, i + 1);
                if (block.includes('"deploymentProgress"')) {
                  blocks.push(block);
                }
              }
            }
          }
          return blocks;
        };
        
        const jsonBlocks = findJsonBlocks(content);
        
        for (const block of jsonBlocks) {
          const parsed = safeParseJSON(block);
          if (parsed && parsed.deploymentProgress !== undefined) {
            return {
              progress: parsed.deploymentProgress,
              deploymentFiles: parsed.deploymentFiles,
              jsonMatch: block
            };
          }
        }
      } catch (e) {
        // Ignore JSON parsing errors
      }
      return null;
    };

    // Helper function to remove tool parameter JSON from text with better handling
    const removeToolParameterJSON = (content: string): string => {
      // Remove JSON blocks that look like tool parameters, but be more careful about malformed JSON
      const toolParamPatterns = [
        // Pattern for tool parameters - look for complete JSON blocks
        /\{\s*"[^"]*"[\s\S]*?\}\s*(?=\n|$)/g,
      ];
      
      let cleaned = content;
      
      // Try to find and remove complete JSON blocks more safely
      let braceCount = 0;
      let start = -1;
      let i = 0;
      const toRemove: Array<{start: number, end: number}> = [];
      
      while (i < content.length) {
        if (content[i] === '{') {
          if (braceCount === 0) {
            start = i;
          }
          braceCount++;
        } else if (content[i] === '}') {
          braceCount--;
          if (braceCount === 0 && start !== -1) {
            const block = content.substring(start, i + 1);
            // Check if this looks like a tool parameter block
            if (block.includes('"filePath"') || 
                block.includes('"packageName"') || 
                block.includes('"target_file"') ||
                block.includes('"query"') ||
                block.includes('"command"')) {
              toRemove.push({start, end: i + 1});
            }
            start = -1;
          }
        }
        i++;
      }
      
      // Remove blocks in reverse order to maintain indices
      for (let j = toRemove.length - 1; j >= 0; j--) {
        const {start, end} = toRemove[j];
        cleaned = cleaned.slice(0, start) + cleaned.slice(end);
      }
      
      // Clean up multiple consecutive newlines
      cleaned = cleaned.replace(/\n\s*\n\s*\n/g, '\n\n');
      
      return cleaned.trim();
    };

    // First, check for progress JSON and replace it
    let processedText = text;
    const progressData = parseProgressJSON(text);
    if (progressData && progressData.jsonMatch) {
      // Remove the specific JSON match from the text
      processedText = text.replace(progressData.jsonMatch, '').trim();
      
      // Add progress pill
      parts.push({
        type: 'progress',
        content: '',
        progress: progressData.progress,
        deploymentFiles: progressData.deploymentFiles
      });
    }

    // Remove tool parameter JSON from the processed text
    processedText = removeToolParameterJSON(processedText);

    // Updated regex patterns for simplified markers
    const allMarkersRegex = /\[(?:TOOL|RESULT):([^:]+):([^\]]+)\]/g;
    let lastIndex = 0;
    const processedTools = new Set<string>();

    let match;
    while ((match = allMarkersRegex.exec(processedText)) !== null) {
      const [fullMatch, toolName, toolId] = match;
      const start = match.index;

      // Add text before the marker
      if (start > lastIndex) {
        const textContent = processedText.slice(lastIndex, start);
        if (textContent.trim()) {
          parts.push({ type: 'text', content: textContent });
        }
      }

          // Add tool pill (only once per tool)
    if (!processedTools.has(toolId)) {
      const toolData = toolMap.get(toolId);
      if (toolData) {
        parts.push({
          type: 'tool',
          content: '',
          toolName: toolData.toolName,
          toolId: toolData.toolId,
          input: toolData.input ? formatToolInput(toolData.input) : undefined,
          result: toolData.result,
          isCompleted: isToolCompleted(toolId)
        });
        processedTools.add(toolId);
      } else {
        // Fallback: show basic tool info even without complete data
        parts.push({
          type: 'tool',
          content: '',
          toolName: toolName,
          toolId: toolId,
          input: undefined,
          result: undefined,
          isCompleted: false
        });
        processedTools.add(toolId);
      }
    }

      lastIndex = start + fullMatch.length;
    }

    // Add remaining text
    if (lastIndex < processedText.length) {
      const textContent = processedText.slice(lastIndex);
      if (textContent.trim()) {
        parts.push({ type: 'text', content: textContent });
      }
    }

    return parts;
  };

  const parsedContent = parseContent(content);

  const handleToolClick = (toolName: string, toolId: string, input?: string, result?: string) => {
    setSelectedTool({
      toolName,
      toolId,
      input,
      result,
      isCompleted: !!result && result !== 'Processing...' // Only mark as completed if we have a real result
    });
    setSidebarOpen(true);
    onSidebarStateChange?.(true);
  };

  const handleSidebarClose = () => {
    setSidebarOpen(false);
    onSidebarStateChange?.(false);
  };

  return (
    <>
      <div className="text-md leading-relaxed prose prose-sm max-w-none" style={{ fontFamily: 'Baskerville, serif' }}>
        {parsedContent.map((part, index) => {
          if (part.type === 'text') {
            return (
              <ReactMarkdown
                key={index}
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                  ul: ({ children }) => <ul className="list-disc pl-6 mb-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-6 mb-2 space-y-1">{children}</ol>,
                  li: ({ children, ...props }) => {
                    // Check if this is a nested list item
                    const hasNestedList = React.Children.toArray(children).some(
                      child => React.isValidElement(child) && (child.type === 'ul' || child.type === 'ol')
                    );
                    return (
                      <li className={`${hasNestedList ? 'mb-1' : ''}`} {...props}>
                        {children}
                      </li>
                    );
                  },
                  h1: ({ children }) => <h1 className="text-lg font-semibold mb-2 text-gray-900">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-base font-semibold mb-2 text-gray-900">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-md font-semibold mb-1 text-gray-900">{children}</h3>,
                  code: ({ node, className, children, ...props }) => {
                    // Check if this is inline code - block code has language- classes, inline doesn't
                    const isInline = !className || !className.startsWith('language-');
                    
                    return (
                      <CodeBlock 
                        className={className} 
                        inline={isInline}
                        {...props}
                      >
                        {String(children).replace(/\n$/, '')}
                      </CodeBlock>
                    );
                  },
                  pre: ({ children }) => {
                    // For block code, return the children directly (CodeBlock handles its own wrapper)
                    return <>{children}</>;
                  },
                  // Better handling for tool results that contain file contents
                  blockquote: ({ children }) => {
                    return (
                      <div className="bg-gray-50 border-l-4 border-gray-300 pl-4 py-2 my-2 text-sm">
                        <div className="font-mono whitespace-pre-wrap">{children}</div>
                      </div>
                    );
                  },
                }}
              >
                {part.content}
              </ReactMarkdown>
            );
          } else if (part.type === 'tool') {
            return (
              <span key={index} className="inline-block mx-1 my-0.5">
                <ToolPill
                  toolName={part.toolName!}
                  toolId={part.toolId!}
                  input={part.input}
                  result={part.result}
                  isCompleted={part.isCompleted}
                  onClick={() => handleToolClick(part.toolName!, part.toolId!, part.input, part.result)}
                />
              </span>
            );
          } else if (part.type === 'progress') {
            const completedFiles = part.deploymentFiles?.filter(f => f.status === 'completed')?.length || 0;
            const totalFiles = part.deploymentFiles?.length || 0;
            return (
              <span key={index} className="inline-block mx-1 my-0.5">
                <ProgressPill
                  progress={part.progress || 0}
                  filesCompleted={completedFiles}
                  totalFiles={totalFiles}
                  onClick={() => {
                    // Could open files sidebar or show more details
                  }}
                />
              </span>
            );
          }
          return null;
        })}
      </div>

      <ToolDetailSidebar
        isOpen={sidebarOpen}
        onClose={handleSidebarClose}
        toolDetail={selectedTool}
      />
    </>
  );
}; 