import React from "react";
import { FileText, CheckCircle, Clock } from "lucide-react";

interface ProgressPillProps {
  progress: number;
  filesCompleted?: number;
  totalFiles?: number;
  onClick?: () => void;
}

export const ProgressPill: React.FC<ProgressPillProps> = ({ 
  progress, 
  filesCompleted = 0, 
  totalFiles = 0, 
  onClick 
}) => {
  const getProgressIcon = () => {
    if (progress >= 100) {
      return <CheckCircle className="w-3.5 h-3.5 text-green-600" />;
    } else if (progress > 0) {
      return <Clock className="w-3.5 h-3.5 text-purple-600" />;
    } else {
      return <FileText className="w-3.5 h-3.5 text-gray-600" />;
    }
  };

  const getProgressText = () => {
    if (totalFiles > 0) {
      return `${filesCompleted}/${totalFiles} files • ${progress.toFixed(0)}%`;
    }
    return `progress: ${progress.toFixed(0)}%`;
  };

  const getProgressColor = () => {
    if (progress >= 100) return 'text-green-700';
    if (progress >= 50) return 'text-purple-700';
    return 'text-gray-700';
  };

  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium
        transition-all duration-200 active:scale-[0.98]
        backdrop-blur-md
        bg-white/15 hover:bg-[#7b35b8] hover:text-white ${getProgressColor()}
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
      <div className="relative z-10 font-baskerville">
        {getProgressIcon()}
      </div>
      
      {/* Text */}
      <span className="relative z-10 font-medium font-baskerville">
        {getProgressText()}
      </span>
    </button>
  );
}; 