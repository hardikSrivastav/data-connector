import { useState, useEffect } from 'react';
import { Clock, CheckCircle, XCircle, AlertCircle, ChevronDown, ChevronRight, RotateCcw, Play } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ReasoningEvent, ReasoningChainData } from '@/types';

interface ReasoningChainProps {
  reasoningData?: ReasoningChainData;
  query?: string;
  title?: string;
  collapsed?: boolean;
  showRecoveryOptions?: boolean;
  onResumeQuery?: (query: string) => void;
  onRetryQuery?: (query: string) => void;
}

export const ReasoningChain = ({ 
  reasoningData, 
  query = 'AI Query', 
  title = 'AI Reasoning Process',
  collapsed = false,
  showRecoveryOptions = false,
  onResumeQuery,
  onRetryQuery
}: ReasoningChainProps) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [showAllEvents, setShowAllEvents] = useState(false);

  // Default to empty data if none provided
  const data = reasoningData || {
    events: [],
    originalQuery: query,
    isComplete: false,
    lastUpdated: new Date().toISOString(),
    status: 'streaming' as const,
    progress: 0
  };

  console.log('🧠 ReasoningChain: Rendering with data:', {
    eventsCount: data.events?.length || 0,
    isComplete: data.isComplete,
    status: data.status,
    query: data.originalQuery || query
  });

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'complete':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'progress':
        return <Clock className="h-4 w-4 text-blue-500 animate-pulse" />;
      default:
        return <div className="w-2 h-2 rounded-full bg-blue-500" />;
    }
  };

  const getEventTypeLabel = (eventType: string) => {
    switch (eventType) {
      case 'classifying': return 'Query Analysis';
      case 'database_selected': return 'Database Selection';
      case 'schema_loading': return 'Schema Loading';
      case 'query_generating': return 'Query Generation';
      case 'query_executing': return 'Query Execution';
      case 'partial_results': return 'Results Processing';
      case 'analysis_chunk': return 'Analysis Generation';
      case 'planning': return 'Operation Planning';
      case 'aggregating': return 'Data Aggregation';
      case 'complete': return 'Completed';
      case 'error': return 'Error';
      case 'progress': return 'Progress Update';
      default: return 'Processing';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const displayEvents = showAllEvents ? data.events : data.events.slice(-10);
  const hiddenEventsCount = data.events.length - displayEvents.length;

  // Check if this is an incomplete reasoning chain that could be resumed
  const canResume = !data.isComplete && data.status === 'streaming' && data.events.length > 0;
  const canRetry = data.status === 'failed' || data.status === 'cancelled';

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
        onClick={() => setIsCollapsed(!isCollapsed)}
            className="h-8 w-8 p-0"
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              "{data.originalQuery || query}"
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Status indicator */}
          <div className={cn(
            "px-2 py-1 rounded-full text-xs font-medium",
            data.status === 'completed' && "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
            data.status === 'failed' && "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
            data.status === 'streaming' && "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
            data.status === 'cancelled' && "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
          )}>
            {data.status.toUpperCase()}
          </div>
          
          {/* Progress indicator */}
          {data.status === 'streaming' && (
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {Math.round(data.progress * 100)}%
            </div>
          )}
        </div>
      </div>

      {!isCollapsed && (
        <div className="p-4">
          {/* Recovery options */}
          {showRecoveryOptions && (canResume || canRetry) && (
            <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                <span className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                  {canResume ? 'Incomplete Query Detected' : 'Failed Query Found'}
                </span>
              </div>
              <p className="text-sm text-yellow-700 dark:text-yellow-300 mb-3">
                {canResume 
                  ? 'This query was interrupted. You can resume processing or start over.'
                  : 'This query failed to complete. You can retry it.'
                }
              </p>
              <div className="flex gap-2">
                {canResume && onResumeQuery && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onResumeQuery(data.originalQuery || query)}
                    className="text-yellow-700 dark:text-yellow-200 border-yellow-300 dark:border-yellow-600"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    Resume
                  </Button>
                )}
                {(canRetry || canResume) && onRetryQuery && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onRetryQuery(data.originalQuery || query)}
                    className="text-yellow-700 dark:text-yellow-200 border-yellow-300 dark:border-yellow-600"
                  >
                    <RotateCcw className="h-3 w-3 mr-1" />
                    Retry
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Events timeline */}
          {data.events.length > 0 ? (
            <div className="space-y-3">
              {/* Show hidden events indicator */}
              {hiddenEventsCount > 0 && !showAllEvents && (
                <button
                  onClick={() => setShowAllEvents(true)}
                  className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 py-2 border-b border-gray-200 dark:border-gray-700"
                >
                  ↑ Show {hiddenEventsCount} earlier events
                </button>
              )}

              {/* Events list */}
              <div className="max-h-96 overflow-y-auto space-y-2">
                {displayEvents.map((event, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    <div className="flex-shrink-0 mt-0.5">
                    {getEventIcon(event.type)}
                  </div>
                <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {getEventTypeLabel(event.type)}
                    </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                      {formatTimestamp(event.timestamp)}
                    </span>
                  </div>
                      <p className="text-sm text-gray-600 dark:text-gray-300 break-words">
                    {event.message}
                      </p>
                  {/* Show metadata if available */}
                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                        <details className="mt-2">
                          <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-200">
                            View details
                        </summary>
                          <pre className="text-xs text-gray-500 dark:text-gray-400 mt-1 p-2 bg-gray-100 dark:bg-gray-700 rounded overflow-auto max-h-32">
                          {JSON.stringify(event.metadata, null, 2)}
                        </pre>
                      </details>
                  )}
                </div>
              </div>
            ))}
          </div>

              {/* Show all events toggle */}
              {hiddenEventsCount > 0 && showAllEvents && (
                <button
                  onClick={() => setShowAllEvents(false)}
                  className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 py-2 border-t border-gray-200 dark:border-gray-700"
                >
                  ↓ Show recent events only
                </button>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No reasoning events recorded yet</p>
            </div>
          )}

          {/* Summary information */}
          {data.events.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Total Events:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">{data.events.length}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Progress:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
                    {Math.round(data.progress * 100)}%
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Status:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-gray-100 capitalize">
                    {data.status}
              </span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Last Updated:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
                    {formatTimestamp(data.lastUpdated)}
              </span>
            </div>
          </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}; 