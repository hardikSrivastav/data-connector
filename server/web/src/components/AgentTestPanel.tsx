import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { agentClient, AgentQueryResponse } from '@/lib/agent-client';
import { Loader2, CheckCircle, XCircle, Send } from 'lucide-react';

export const AgentTestPanel = () => {
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'unknown' | 'connected' | 'disconnected'>('unknown');
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryText, setQueryText] = useState('Show me the first 5 users');
  const [queryResult, setQueryResult] = useState<AgentQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const testConnection = async () => {
    setIsTestingConnection(true);
    setError(null);
    
    try {
      await agentClient.healthCheck();
      setConnectionStatus('connected');
    } catch (error) {
      setConnectionStatus('disconnected');
      setError(error instanceof Error ? error.message : 'Connection failed');
    } finally {
      setIsTestingConnection(false);
    }
  };

  const executeQuery = async () => {
    if (!queryText.trim()) return;
    
    setIsQuerying(true);
    setError(null);
    setQueryResult(null);
    
    try {
      const result = await agentClient.query({
        question: queryText,
        analyze: true
      });
      setQueryResult(result);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Query failed');
    } finally {
      setIsQuerying(false);
    }
  };

  const formatResults = (rows: Array<Record<string, any>>) => {
    if (rows.length === 0) return 'No results';
    
    const maxRows = Math.min(rows.length, 10);
    const columns = Object.keys(rows[0]);
    
    return (
      <div className="overflow-x-auto">
        <table className="min-w-full border border-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              {columns.map(col => (
                <th key={col} className="border border-gray-200 px-2 py-1 text-left font-medium">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, maxRows).map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                {columns.map(col => (
                  <td key={col} className="border border-gray-200 px-2 py-1">
                    {row[col] !== null && row[col] !== undefined ? String(row[col]) : ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > maxRows && (
          <p className="text-gray-500 text-xs mt-2">
            ... and {rows.length - maxRows} more rows
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-4 bg-white">
      <h3 className="text-lg font-semibold text-gray-900">AI Agent Test Panel</h3>
      
      {/* Connection Test */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Connection Status:</span>
          <div className="flex items-center gap-2">
            {connectionStatus === 'connected' && (
              <>
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm text-green-600">Connected</span>
              </>
            )}
            {connectionStatus === 'disconnected' && (
              <>
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-sm text-red-600">Disconnected</span>
              </>
            )}
            {connectionStatus === 'unknown' && (
              <span className="text-sm text-gray-600">Unknown</span>
            )}
          </div>
        </div>
        
        <Button 
          onClick={testConnection} 
          disabled={isTestingConnection}
          size="sm"
          variant="outline"
          className="w-full"
        >
          {isTestingConnection ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Testing...
            </>
          ) : (
            'Test Connection'
          )}
        </Button>
      </div>

      {/* Query Test */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Test Query:</label>
        <div className="flex gap-2">
          <Input
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder="Enter your question..."
            className="flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                executeQuery();
              }
            }}
          />
          <Button 
            onClick={executeQuery} 
            disabled={isQuerying || !queryText.trim()}
            size="sm"
          >
            {isQuerying ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700">
            <strong>Error:</strong> {error}
          </p>
        </div>
      )}

      {/* Query Results */}
      {queryResult && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium">Query Results:</h4>
          
          {/* SQL Query */}
          {queryResult.sql && (
            <div className="bg-gray-50 p-3 rounded-md">
              <p className="text-xs font-medium text-gray-700 mb-1">Generated SQL:</p>
              <code className="text-xs text-gray-800 bg-white p-2 rounded border block overflow-x-auto">
                {queryResult.sql}
              </code>
            </div>
          )}

          {/* Analysis */}
          {queryResult.analysis && (
            <div className="bg-blue-50 p-3 rounded-md">
              <p className="text-xs font-medium text-blue-700 mb-1">Analysis:</p>
              <p className="text-sm text-blue-800">{queryResult.analysis}</p>
            </div>
          )}

          {/* Data Results */}
          <div className="bg-gray-50 p-3 rounded-md">
            <p className="text-xs font-medium text-gray-700 mb-2">
              Data ({queryResult.rows.length} rows):
            </p>
            {formatResults(queryResult.rows)}
          </div>
        </div>
      )}
    </div>
  );
}; 