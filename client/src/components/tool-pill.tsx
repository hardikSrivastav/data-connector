import React, { useState } from "react";
import { Sparkles, Zap, FileText, CheckCircle } from "lucide-react";

interface ToolPillProps {
  toolName: string;
  toolId: string;
  input?: string;
  result?: string;
  isCompleted?: boolean;
  onClick: () => void;
}

const getToolIcon = (toolName: string) => {
  if (!toolName || typeof toolName !== 'string') {
    return <Zap className="w-3 h-3" />;
  }

  const normalizedName = toolName.toLowerCase().trim();
  
  // Reading/viewing operations
  if (normalizedName.includes('introspect') || 
      normalizedName.includes('read') || 
      normalizedName.includes('view') || 
      normalizedName.includes('show') || 
      normalizedName.includes('get') || 
      normalizedName.includes('fetch') || 
      normalizedName.includes('list') || 
      normalizedName.includes('browse') ||
      normalizedName.includes('search')) {
    return <FileText className="w-3 h-3" />;
  }
  
  // Creation operations
  if (normalizedName.includes('create') || 
      normalizedName.includes('generate') || 
      normalizedName.includes('build') || 
      normalizedName.includes('make') || 
      normalizedName.includes('new') || 
      normalizedName.includes('add') || 
      normalizedName.includes('deploy') ||
      normalizedName.includes('setup') ||
      normalizedName.includes('install')) {
    return <Sparkles className="w-3 h-3" />;
  }
  
  // Editing/modification operations
  if (normalizedName.includes('edit') || 
      normalizedName.includes('update') || 
      normalizedName.includes('modify') || 
      normalizedName.includes('change') || 
      normalizedName.includes('write') || 
      normalizedName.includes('save') || 
      normalizedName.includes('set') || 
      normalizedName.includes('patch') ||
      normalizedName.includes('replace') ||
      normalizedName.includes('configure')) {
    return <Zap className="w-3 h-3" />;
  }
  
  // Default fallback
  return <Zap className="w-3 h-3" />;
};

const getToolDisplayName = (toolName: string) => {
  if (!toolName || typeof toolName !== 'string') {
    return 'tool call';
  }

  const normalizedName = toolName.toLowerCase().trim();
  
  // Extract meaningful action from tool name
  if (normalizedName.includes('introspect') || 
      normalizedName.includes('read') || 
      normalizedName.includes('view') || 
      normalizedName.includes('show') || 
      normalizedName.includes('get') || 
      normalizedName.includes('fetch') || 
      normalizedName.includes('browse')) {
    return 'reading';
  }
  
  if (normalizedName.includes('list') || 
      normalizedName.includes('search') || 
      normalizedName.includes('find') || 
      normalizedName.includes('query')) {
    return 'listing';
  }
  
  if (normalizedName.includes('create') || 
      normalizedName.includes('generate') || 
      normalizedName.includes('build') || 
      normalizedName.includes('make') || 
      normalizedName.includes('new') || 
      normalizedName.includes('add')) {
    return 'creating';
  }
  
  if (normalizedName.includes('deploy') || 
      normalizedName.includes('setup') || 
      normalizedName.includes('install') || 
      normalizedName.includes('configure')) {
    return 'deploying';
  }
  
  if (normalizedName.includes('edit') || 
      normalizedName.includes('update') || 
      normalizedName.includes('modify') || 
      normalizedName.includes('change') || 
      normalizedName.includes('write') || 
      normalizedName.includes('save') || 
      normalizedName.includes('set') || 
      normalizedName.includes('patch') ||
      normalizedName.includes('replace')) {
    return 'editing';
  }
  
  if (normalizedName.includes('delete') || 
      normalizedName.includes('remove') || 
      normalizedName.includes('clean') || 
      normalizedName.includes('clear')) {
    return 'deleting';
  }
  
  if (normalizedName.includes('execute') || 
      normalizedName.includes('run') || 
      normalizedName.includes('start') || 
      normalizedName.includes('launch')) {
    return 'executing';
  }
  
  if (normalizedName.includes('validate') || 
      normalizedName.includes('check') || 
      normalizedName.includes('verify') || 
      normalizedName.includes('test')) {
    return 'validating';
  }
  
  // Fallback: extract first meaningful word or use generic
  const words = normalizedName.replace(/[_-]/g, ' ').split(' ').filter(w => w.length > 2);
  if (words.length > 0) {
    const firstWord = words[0];
    // Return first word if it's meaningful, otherwise generic
    if (firstWord.length > 3 && !['tool', 'function', 'method', 'call'].includes(firstWord)) {
      return firstWord;
    }
  }
  
  // Final fallback
  return 'tool call';
};

export const ToolPill: React.FC<ToolPillProps> = ({ 
  toolName, 
  toolId, 
  input, 
  result, 
  isCompleted = false, 
  onClick 
}) => {
  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium
        transition-all duration-200 active:scale-[0.98]
        backdrop-blur-md
        bg-white/15 hover:bg-[#7b35b8] hover:text-white text-gray-700
        relative overflow-hidden group border border-gray-900 mb-4
      `}
      style={{ 
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.3)',
      }}
    >
      {/* Apple-style glass highlight */}
      <div className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-60" />
      
      {/* Subtle edge highlight */}
      <div className="absolute inset-0 rounded-lg ring-1 ring-inset ring-white/20" />
      
      {/* Icon */}
      <div className={`relative z-10 'text-gray-600' font-baskerville`}>
        {isCompleted ? (
          <FileText className="w-3.5 h-3.5" />
        ) : (
          getToolIcon(toolName)
        )}
      </div>
      
      {/* Text */}
      <span className="relative z-10 font-medium font-baskerville">
        {getToolDisplayName(toolName)}
      </span>
    </button>
  );
};
