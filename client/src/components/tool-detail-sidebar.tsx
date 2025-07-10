"use client";

import React from "react";
import { X, ChevronDown, ChevronRight } from "lucide-react";

interface ToolDetail {
  toolName: string;
  toolId: string;
  input?: string;
  result?: string;
  isCompleted?: boolean;
}

interface ToolDetailSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  toolDetail: ToolDetail | null;
}

export const ToolDetailSidebar: React.FC<ToolDetailSidebarProps> = ({
  isOpen,
  onClose,
  toolDetail
}) => {
  const [showInput, setShowInput] = React.useState(false);
  const [showResult, setShowResult] = React.useState(false);

  if (!toolDetail) return null;

  const formatJSON = (str: string) => {
    try {
      return JSON.stringify(JSON.parse(str), null, 2);
    } catch {
      return str;
    }
  };

  // Consistent monospace font stack
  const monospaceFont = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';

  return (
    <div
      className={`
        fixed right-6 top-1/2 transform -translate-y-1/2 w-80 
        bg-white border border-gray-900 text-gray-900 rounded-2xl shadow-xl
        transition-all duration-300 ease-in-out z-50
        ${isOpen ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0 pointer-events-none'}
      `}
      style={{ fontFamily: 'Baskerville, serif' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="text-lg font-medium">
          Tool Details
        </h3>
        <button
          onClick={onClose}
          className="p-1 border border-gray-200 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 max-h-96 overflow-y-auto">
        {/* Tool Name */}
        <div>
          <h4 className="text-sm font-medium mb-2">
            Tool Name
          </h4>
          <div 
            className="text-sm text-gray-600 bg-gray-50 p-2 rounded"
            style={{ fontFamily: monospaceFont }}
          >
            {toolDetail.toolName}
          </div>
        </div>

        {/* Tool ID */}
        <div>
          <h4 className="text-sm font-medium mb-2">
            Tool ID
          </h4>
          <div 
            className="text-xs text-gray-500 bg-gray-50 p-2 rounded"
            style={{ fontFamily: monospaceFont }}
          >
            {toolDetail.toolId}
          </div>
        </div>

        {/* Input Parameters */}
        {toolDetail.input && (
          <div>
            <button
              onClick={() => setShowInput(!showInput)}
              className="flex items-center gap-2 w-full text-left hover:bg-gray-50 p-2 rounded transition-colors"
            >
              {showInput ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">
                Input Parameters
              </span>
            </button>
            {showInput && (
              <div className="mt-2 bg-gray-50 p-3 rounded">
                <pre 
                  className="text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap"
                  style={{ fontFamily: monospaceFont }}
                >
                  {formatJSON(toolDetail.input)}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Result */}
        {toolDetail.result && (
          <div>
            <button
              onClick={() => setShowResult(!showResult)}
              className="flex items-center gap-2 w-full text-left hover:bg-gray-50 p-2 rounded transition-colors"
            >
              {showResult ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">
                Result
              </span>
            </button>
            {showResult && (
              <div className="mt-2 bg-gray-50 p-3 rounded">
                <pre 
                  className="text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto"
                  style={{ fontFamily: monospaceFont }}
                >
                  {toolDetail.result}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Status */}
        <div>
          <h4 className="text-sm font-medium mb-2">
            Status
          </h4>
          <div className={`text-sm px-3 py-1 rounded-full inline-block ${
            toolDetail.isCompleted 
              ? 'bg-green-100 text-green-700' 
              : 'bg-purple-100 text-purple-700'
          }`}>
            {toolDetail.isCompleted ? 'Completed' : 'In Progress'}
          </div>
        </div>
      </div>
    </div>
  );
}; 