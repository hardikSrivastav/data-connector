"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ToolPill } from "./tool-pill";
import { ToolDetailSidebar } from "./tool-detail-sidebar";

interface ParsedContent {
  type: 'text' | 'tool' | 'result';
  content: string;
  toolName?: string;
  toolId?: string;
  input?: string;
  result?: string;
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

    // Updated regex patterns for simplified markers
    const allMarkersRegex = /\[(?:TOOL|RESULT):([^:]+):([^\]]+)\]/g;
    let lastIndex = 0;
    const processedTools = new Set<string>();

    let match;
    while ((match = allMarkersRegex.exec(text)) !== null) {
      const [fullMatch, toolName, toolId] = match;
      const start = match.index;

      // Add text before the marker
      if (start > lastIndex) {
        const textContent = text.slice(lastIndex, start);
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
            input: toolData.input ? JSON.stringify(toolData.input) : undefined,
            result: toolData.result
          });
          processedTools.add(toolId);
        }
      }

      lastIndex = start + fullMatch.length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      const textContent = text.slice(lastIndex);
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
      isCompleted: !!result
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
                  ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                  li: ({ children }) => <li className="ml-0">{children}</li>,
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
                  isCompleted={!!part.result}
                  onClick={() => handleToolClick(part.toolName!, part.toolId!, part.input, part.result)}
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