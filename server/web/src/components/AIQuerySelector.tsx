import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, Sparkles, Send, X, FileText, CheckSquare, Edit3, Lightbulb, Code, Search, Zap } from 'lucide-react';
import styles from './BlockEditor.module.css';
import { DiffInterface } from './DiffInterface';
import { orchestrationAgent, type BlockContext, type OperationClassification } from '@/lib/orchestration/agent';
import { agentClient } from '@/lib/agent-client';
import { type TrivialQueryRequest } from '@/lib/AgentClient';
import { computeTextDiff, type DiffChange } from '@/lib/diff/textDiff';
import { useAuth } from '@/contexts/AuthContext';

interface StreamingStatusEntry {
  type: 'status' | 'progress' | 'error' | 'complete' | 'partial_sql' | 'analysis_chunk';
  message: string;
  timestamp: string;
  metadata?: any;
}

interface StreamingStep {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'complete' | 'error';
  message?: string;
  timestamp?: number;
}

interface AIQuerySelectorProps {
  query: string;
  onQuerySubmit: (query: string) => void;
  onClose: () => void;
  isLoading?: boolean;
  streamingStatus?: string;
  streamingProgress?: number;
  // Enhanced streaming props for real-time updates
  streamingHistory?: StreamingStatusEntry[];
  // New diff mode props
  diffMode?: boolean;
  originalText?: string;
  onDiffAccept?: (newText: string) => void;
  onDiffDiscard?: () => void;
  onDiffInsertBelow?: (newText: string) => void;
  onDiffTryAgain?: () => void;
  // Block context for orchestration agent
  blockContext?: BlockContext;
  // Auto-classify and route queries
  enableSmartRouting?: boolean;
  // Text for editing operations (when in diff/edit mode)
  editingText?: string;
}

const AI_OPTIONS = [
  {
    section: 'Write',
    items: [
      { icon: '📄', text: 'Add a summary', query: 'Add a summary' },
      { icon: '✓', text: 'Add action items', query: 'Add action items' },
      { icon: '✏️', text: 'Write anything...', query: 'Write anything...' },
    ]
  },
  {
    section: 'Think, ask, chat',
    items: [
      { icon: '💡', text: 'Brainstorm ideas...', query: 'Brainstorm ideas...' },
      { icon: '{ }', text: 'Get help with code...', query: 'Get help with code...' },
    ]
  },
  {
    section: 'Find, search',
    items: [
      { icon: '?', text: 'Ask a question...', query: 'Ask a question...' },
      { icon: '🔍', text: 'Query database...', query: 'enhanced:query' },
      { icon: '🌐', text: 'Cross-database search...', query: 'enhanced:cross-db' },
    ]
  },
  {
    section: 'Edit',
    items: [
      { icon: '✓', text: 'Fix grammar', query: 'Fix grammar' },
      { icon: '↓', text: 'Make it shorter', query: 'Make it shorter' },
      { icon: '✨', text: 'Improve clarity', query: 'Improve clarity' },
      { icon: '♫', text: 'Improve tone', query: 'Improve tone' },
      { icon: '⚡', text: 'Test diff editing...', query: 'diff:test' },
    ]
  }
];

  // If in diff mode, show different options
  const DIFF_OPTIONS = [
    {
      section: 'Edit Text',
      items: [
        { icon: '✨', text: 'Improve clarity', query: 'Make this text clearer and more professional' },
        { icon: '✓', text: 'Fix grammar', query: 'Fix any grammar and spelling mistakes' },
        { icon: '↓', text: 'Make it shorter', query: 'Make this text more concise' },
        { icon: '↑', text: 'Make it longer', query: 'Expand this text with more detail' },
    ]
  }
];

export default function AIQuerySelector({
  query,
  onQuerySubmit,
  onClose,
  isLoading = false,
  streamingStatus,
  streamingProgress,
  streamingHistory,
  diffMode = false,
  originalText,
  onDiffAccept,
  onDiffDiscard,
  onDiffInsertBelow,
  onDiffTryAgain,
  blockContext,
  enableSmartRouting = true,
  editingText
}: AIQuerySelectorProps) {
  const [inputValue, setInputValue] = useState(query);
  const [showDropdown, setShowDropdown] = useState(true);
  const [classification, setClassification] = useState<OperationClassification | null>(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  
  // Trivial operation state
  const [isTrivialOperation, setIsTrivialOperation] = useState(false);
  const [trivialResult, setTrivialResult] = useState<string>('');
  const [trivialDiffChanges, setTrivialDiffChanges] = useState<DiffChange[]>([]);
  const [trivialStreamingState, setTrivialStreamingState] = useState<{
    isStreaming: boolean;
    operation: string;
    provider: string;
    model: string;
    duration: number;
    cached: boolean;
  }>({
    isStreaming: false,
    operation: '',
    provider: '',
    model: '',
    duration: 0,
    cached: false
  });
  const [trivialSupported, setTrivialSupported] = useState<string[]>([]);

  useEffect(() => {
    if (inputRef.current && !isLoading) {
      inputRef.current.focus();
      inputRef.current.setSelectionRange(inputValue.length, inputValue.length);
    }
  }, []);

  // Check trivial LLM availability
  useEffect(() => {
    const checkTrivialSupport = async () => {
      if (!enableSmartRouting) return;
      
      try {
        const health = await agentClient.checkTrivialHealth();
        if (health.status === 'healthy') {
          setTrivialSupported(health.supported_operations || []);
        }
      } catch (error) {
        console.warn('Trivial LLM not available:', error);
      }
    };

    checkTrivialSupport();
  }, [enableSmartRouting]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [inputValue]);

  const handleTrivialOperation = async (operation: string, text: string) => {
    console.log('⚡ === handleTrivialOperation START ===');
    console.log('⚡ Operation:', operation);
    console.log('⚡ Text length:', text.length);
    console.log('⚡ Text preview:', `"${text.substring(0, 100)}..."`);
    console.log('⚡ === FULL TEXT BEING SENT TO TRIVIAL CLIENT ===');
    console.log('⚡ FULL TEXT START:');
    console.log(text);
    console.log('⚡ FULL TEXT END');
    console.log('⚡ === END FULL TEXT ===');
    
    setIsTrivialOperation(true);
    setTrivialStreamingState({
      isStreaming: true,
      operation,
      provider: '',
      model: '',
      duration: 0,
      cached: false
    });
    
    console.log('⚡ Set trivial streaming state, starting API call...');

    const request: TrivialQueryRequest = {
      operation,
      text,
      context: {
        block_type: blockContext?.type || 'text'
      }
    };

    try {
      console.log('⚡ Calling agentClient.streamTrivialOperation...');
      await agentClient.streamTrivialOperation(
        request,
        (chunk) => {
          console.log('⚡ Received chunk:', chunk.type, chunk);
          if (chunk.type === 'start') {
            setTrivialStreamingState(prev => ({
              ...prev,
              provider: chunk.provider || '',
              model: chunk.model || ''
            }));
          } else if (chunk.type === 'chunk') {
            const partialResult = chunk.partial_result || chunk.content || '';
            const sourceText = editingText || originalText || '';
            if (partialResult && sourceText) {
              const changes = computeTextDiff(sourceText, partialResult);
              setTrivialDiffChanges(changes);
            }
          } else if (chunk.type === 'complete') {
            const finalResult = chunk.result || '';
            setTrivialResult(finalResult);
            setTrivialStreamingState(prev => ({
              ...prev,
              isStreaming: false,
              duration: chunk.duration || 0,
              cached: chunk.cached || false
            }));
            
            const sourceText = editingText || originalText || '';
            if (finalResult && sourceText) {
              const changes = computeTextDiff(sourceText, finalResult);
              setTrivialDiffChanges(changes);
            }
          }
        },
        (error) => {
          console.error('⚡ Trivial operation failed:', error);
          setTrivialStreamingState(prev => ({ ...prev, isStreaming: false }));
        }
      );
      console.log('⚡ === handleTrivialOperation COMPLETE ===');
    } catch (error) {
      console.error('⚡ Failed to start trivial operation:', error);
      setTrivialStreamingState(prev => ({ ...prev, isStreaming: false }));
    }
  };

  const handleEnhancedQuery = async (commandQuery: string) => {
    console.log('🚀✨ === handleEnhancedQuery START ===');
    console.log('🚀✨ Command:', commandQuery);
    
    try {
      // Parse the enhanced command
      if (commandQuery === 'enhanced:query') {
        // Single database query with tools
        console.log('🚀✨ Executing single database query with tools');
        const actualQuery = inputValue.replace('enhanced:query', '').trim() || 'Show me the latest data';
        
        const request: CrossDatabaseQueryRequest = {
          question: actualQuery,
          analyze: true,
          cross_database: false,
          enable_tools: true,
          user_preferences: {
            style: 'modern',
            performance: 'high'
          }
        };
        
        const result = await enhancedAgentClient.queryWithTools(request);
        console.log('🚀✨ Enhanced query result:', result);
        
        // Handle the result - for now, forward to parent component with special prefix
        onQuerySubmit(`enhanced_result:${JSON.stringify(result)}`);
        
      } else if (commandQuery === 'enhanced:cross-db') {
        // Cross-database query with tools
        console.log('🚀✨ Executing cross-database query with tools');
        const actualQuery = inputValue.replace('enhanced:cross-db', '').trim() || 'Compare data across all databases';
        
        const request: CrossDatabaseQueryRequest = {
          question: actualQuery,
          analyze: true,
          cross_database: true,
          enable_tools: true,
          preferred_tools: ['chart_block', 'text_block'],
          user_preferences: {
            style: 'modern',
            performance: 'high'
          }
        };
        
        const result = await enhancedAgentClient.queryWithTools(request);
        console.log('🚀✨ Enhanced cross-database result:', result);
        
        // Handle the result - for now, forward to parent component with special prefix
        onQuerySubmit(`enhanced_result:${JSON.stringify(result)}`);
        
      } else {
        console.log('🚀✨ Unknown enhanced command, falling back to normal query');
        onQuerySubmit(commandQuery);
      }
      
    } catch (error) {
      console.error('🚀✨ Enhanced query failed:', error);
      // Fallback to normal query
      onQuerySubmit(inputValue.trim());
    }
    
    console.log('🚀✨ === handleEnhancedQuery END ===');
  };

  const handleSubmit = async () => {
    console.log('🚀 === AIQuerySelector.handleSubmit START ===');
    console.log('🚀 Input query:', `"${inputValue.trim()}"`);
    console.log('🚀 Current state:', {
      isLoading,
      trivialStreamingState: trivialStreamingState.isStreaming,
      diffMode,
      enableSmartRouting,
      hasBlockContext: !!blockContext,
      trivialSupportedCount: trivialSupported.length
    });

    if (isLoading || trivialStreamingState.isStreaming) {
      console.log('🚀 EARLY EXIT: Already loading or streaming');
      return;
    }

    const trimmedQuery = inputValue.trim();
    if (!trimmedQuery) {
      console.log('🚀 EARLY EXIT: Empty query');
      return;
    }

    console.log('🚀 Processing query:', `"${trimmedQuery}"`);

    // Check if this is a diff mode command
    if (trimmedQuery.startsWith('diff:')) {
      console.log('🚀 ROUTE: Diff mode command detected');
      // Switch to diff mode - this will be handled by parent component
      onQuerySubmit(trimmedQuery);
      setShowDropdown(false);
      return;
    }

    // Check if this is an enhanced query command
    if (trimmedQuery.startsWith('enhanced:')) {
      console.log('🚀✨ ROUTE: Enhanced query command detected');
      await handleEnhancedQuery(trimmedQuery);
      setShowDropdown(false);
      return;
    }

    // If in diff mode, treat input as replacement text
    if (diffMode) {
      console.log('🚀 ROUTE: Already in diff mode, closing dropdown');
      setShowDropdown(false);
      return;
    }

    // Smart routing: classify the query and route appropriately
    console.log('🚀 SMART ROUTING: Checking conditions...');
    console.log('🚀 SMART ROUTING: enableSmartRouting =', enableSmartRouting);
    console.log('🚀 SMART ROUTING: blockContext =', !!blockContext, blockContext);
    console.log('🚀 SMART ROUTING: trivialSupported.length =', trivialSupported.length);
    console.log('🚀 SMART ROUTING: originalText =', !!originalText, originalText?.length);
    console.log('🚀 SMART ROUTING: editingText =', !!editingText, editingText?.length);
    
    if (enableSmartRouting && blockContext && trivialSupported.length > 0) {
      console.log('🚀 SMART ROUTING: Conditions met, starting classification...');
      try {
        console.log('🤖 Classifying query for smart routing...');
        const classification = await orchestrationAgent.classifyOperation(trimmedQuery, blockContext);
        console.log('🤖 Classification result:', classification);
        
        // Check if this is a text editing operation vs content generation
        const hasOriginalText = !!(editingText || originalText);
        const sourceText = editingText || originalText || '';
        
        // Determine operation type based on source text and query intent
        const isTextEditingOperation = hasOriginalText && diffMode;
        const isContentGeneration = hasOriginalText && !diffMode;
        
        console.log(`🤖 Operation analysis:`);
        console.log(`🤖   - Diff mode: ${diffMode}`);
        console.log(`🤖   - Has source text: ${!!sourceText} (${sourceText.length} chars)`);
        console.log(`🤖   - Source text preview: "${sourceText.substring(0, 100)}..."`);
        console.log(`🤖   - Operation type: ${isTextEditingOperation ? 'Text Editing' : isContentGeneration ? 'Content Generation' : 'Unknown'}`);
        console.log(`🤖   - Classification: ${classification.tier} (${Math.round(classification.confidence * 100)}%)`);
        console.log(`🤖   - Query: "${trimmedQuery}"`);
        console.log(`🤖 === FULL SOURCE TEXT AVAILABLE FOR ROUTING ===`);
        console.log(`🤖 editingText:`, editingText || '(empty)');
        console.log(`🤖 originalText:`, originalText || '(empty)');
        console.log(`🤖 Final sourceText:`, sourceText || '(empty)');
        console.log(`🤖 === END SOURCE TEXT ===`);
        
        // Route to trivial client if:
        // 1. Classified as trivial with high confidence
        // 2. AND we have source text to work with (either for editing or content generation)  
        // 3. AND natural language requests are supported
        if (classification.tier === 'trivial' && classification.confidence > 0.7 && sourceText.trim()) {
          const operationType = isTextEditingOperation ? 'text editing' : 'content generation';
          console.log(`⚡ Attempting trivial routing for ${operationType}: ${classification.operationType}`);
          
          // Check if natural language requests are supported
          const supportsNaturalLanguage = trivialSupported.includes("natural_language_request") || 
                                          trivialSupported.length === 0;
          
          console.log(`🚀 TRIVIAL CHECK: Checking if natural language is supported...`);
          console.log(`🚀 TRIVIAL CHECK: Available operations:`, trivialSupported);
          console.log(`🚀 TRIVIAL CHECK: Supports natural language:`, supportsNaturalLanguage);
          
          if (supportsNaturalLanguage) {
            console.log(`⚡ SUCCESS: Routing to trivial LLM with natural language request: "${trimmedQuery}"`);
            
            // Pass the user's exact request without categorization
            await handleTrivialOperation(trimmedQuery, sourceText);
            
            setShowDropdown(false);
            console.log('🚀 === TRIVIAL ROUTING COMPLETE ===');
            return;
          } else {
            console.log(`❌ FAILED: Natural language requests not supported. Available: ${trivialSupported.join(', ')}`);
          }
        }
        
        // For content generation or complex operations, use main LLM
        if (isTextEditingOperation) {
          console.log(`🚀 FALLBACK: Text editing operation routing to main LLM (${classification.tier}, confidence: ${Math.round(classification.confidence * 100)}%)`);
        } else {
          console.log(`🚀 FALLBACK: Content generation operation routing to main LLM (${classification.tier})`);
        }
        
      } catch (error) {
        console.error('🚀 CLASSIFICATION ERROR: Classification failed, using main LLM:', error);
      }
    } else {
      console.log('🚀 SMART ROUTING DISABLED: Requirements not met, using main LLM');
      console.log('🚀 Missing requirements:', {
        enableSmartRouting: enableSmartRouting ? '✅' : '❌',
        hasBlockContext: blockContext ? '✅' : '❌', 
        trivialSupportedCount: trivialSupported.length > 0 ? `✅ (${trivialSupported.length})` : '❌ (0)'
      });
    }

    // Fallback to normal AI query mode
    console.log('🚀 FINAL FALLBACK: Routing to main LLM via onQuerySubmit');
    console.log('🚀 === AIQuerySelector.handleSubmit END (MAIN LLM) ===');
    onQuerySubmit(trimmedQuery);
    setShowDropdown(false);
  };

  const handleOptionClick = async (optionQuery: string) => {
    setInputValue(optionQuery);
    
    if (optionQuery.startsWith('diff:') || diffMode) {
      // Handle diff mode selection
      if (diffMode) {
        // Replace the input value for diff editing
        setInputValue(optionQuery);
      } else {
        // Switch to diff mode
        onQuerySubmit(optionQuery);
      }
      setShowDropdown(false);
      return;
    }

    // Handle enhanced query options
    if (optionQuery.startsWith('enhanced:')) {
      console.log('🚀✨ Enhanced option selected:', optionQuery);
      await handleEnhancedQuery(optionQuery);
      setShowDropdown(false);
      return;
    }

    // Check if this is a known trivial operation
    if (enableSmartRouting && originalText && trivialSupported.length > 0) {
      // Check if natural language requests are supported
      const supportsNaturalLanguage = trivialSupported.includes("natural_language_request") || 
                                      trivialSupported.length === 0;

      if (supportsNaturalLanguage) {
        console.log(`⚡ Quick natural language operation: "${optionQuery}"`);
        await handleTrivialOperation(optionQuery, originalText);
        setShowDropdown(false);
        return;
      }
    }

    // Normal AI query
    onQuerySubmit(optionQuery);
    setShowDropdown(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    setShowDropdown(e.target.value.length === 0);
    
    // Clear previous classification when input changes
    setClassification(null);
  };

  // Test classification function
  const testClassification = async () => {
    if (!inputValue.trim() || !blockContext) return;
    
    setIsClassifying(true);
    try {
      console.log('🧪 Testing OrchestrationAgent classification...');
      const result = await orchestrationAgent.classifyOperation(inputValue, blockContext);
      setClassification(result);
      console.log('🧪 Classification result:', result);
    } catch (error) {
      console.error('🧪 Classification test failed:', error);
    } finally {
      setIsClassifying(false);
    }
  };

  // Trivial operation result handlers
  const handleTrivialAccept = () => {
    if (onDiffAccept && trivialResult) {
      // For content generation, the result is new content
      // For text editing, the result replaces existing content
      // The trivial client now returns markdown-formatted text
      onDiffAccept(trivialResult);
    }
    onClose();
  };

  const handleTrivialDiscard = () => {
    setIsTrivialOperation(false);
    setTrivialResult('');
    setTrivialDiffChanges([]);
    if (onDiffDiscard) {
      onDiffDiscard();
    } else {
      onClose();
    }
  };

  const handleTrivialInsertBelow = () => {
    if (onDiffInsertBelow && trivialResult) {
      onDiffInsertBelow(trivialResult);
    }
    onClose();
  };

  const handleTrivialTryAgain = () => {
    setIsTrivialOperation(false);
    setTrivialResult('');
    setTrivialDiffChanges([]);
    setShowDropdown(true);
  };

  // If showing trivial operation result, show the diff interface
  if (isTrivialOperation && trivialResult && (editingText || originalText)) {
    return (
      <div ref={containerRef} className="relative w-full max-w-none">
        <div className="bg-card border border-border rounded-lg shadow-lg p-4">
          {/* Generated Content Header */}
                      <div className="flex items-center justify-between mb-3 pb-2 border-b border-border">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-500" />
                              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Generated</span>
              {trivialStreamingState.cached && (
                <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">cached</span>
              )}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {trivialStreamingState.duration > 0 && `${trivialStreamingState.duration.toFixed(0)}ms`}
            </div>
          </div>

                     {/* Diff Display */}
           {trivialStreamingState.isStreaming ? (
             <div className="p-3 bg-gray-50 rounded border border-gray-200 min-h-24">
               <div className="flex items-center gap-2 text-sm text-gray-600">
                 <Loader2 className="h-4 w-4 animate-spin" />
                 <span>Generating...</span>
               </div>
             </div>
           ) : (
             <>
               {/* Custom Diff Renderer for Trivial Operations */}
               <div className="p-3 bg-gray-50 rounded border border-gray-200 min-h-24">
                                   <div className="text-sm leading-relaxed prose prose-sm max-w-none">
                    {trivialDiffChanges.length > 0 ? (
                      trivialDiffChanges.map((change, index) => (
                        <span
                          key={index}
                          className={
                            change.type === 'added'
                              ? 'bg-green-100 text-green-800 px-1 py-0.5 rounded'
                              : change.type === 'removed'
                              ? 'bg-red-100 text-red-800 line-through px-1 py-0.5 rounded'
                              : ''
                          }
                        >
                          {change.value}
                        </span>
                      ))
                    ) : (
                      // Render markdown content properly
                      <div 
                        className="text-gray-600"
                        dangerouslySetInnerHTML={{
                          __html: trivialResult
                            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                            .replace(/\*(.*?)\*/g, '<em>$1</em>')
                            .replace(/`(.*?)`/g, '<code class="bg-gray-200 px-1 py-0.5 rounded text-xs">$1</code>')
                            .replace(/^## (.*$)/gm, '<h2 class="text-lg font-semibold mt-3 mb-2">$1</h2>')
                            .replace(/^### (.*$)/gm, '<h3 class="text-base font-semibold mt-2 mb-1">$1</h3>')
                            .replace(/^- (.*$)/gm, '<li class="ml-4">$1</li>')
                            .replace(/\n/g, '<br>')
                        }}
                      />
                    )}
                  </div>
               </div>

               {/* Action Buttons */}
               <div className="flex gap-2 mt-3">
                 <Button
                   onClick={handleTrivialAccept}
                   size="sm"
                   className="bg-green-600 hover:bg-green-700 text-white"
                 >
                   Accept
                 </Button>
                 <Button
                   onClick={handleTrivialInsertBelow}
                   size="sm"
                   variant="outline"
                 >
                   Insert Below
                 </Button>
                 <Button
                   onClick={handleTrivialTryAgain}
                   size="sm"
                   variant="outline"
                 >
                   Try Again
                 </Button>
                 <Button
                   onClick={handleTrivialDiscard}
                   size="sm"
                   variant="ghost"
                 >
                   Cancel
                 </Button>
               </div>
             </>
           )}
        </div>
      </div>
    );
  }

  // If in diff mode, show the diff interface instead
  if (diffMode && (editingText || originalText) && onDiffAccept && onDiffDiscard && onDiffInsertBelow && onDiffTryAgain) {
    return (
      <div ref={containerRef} className="relative w-full max-w-none">
        <DiffInterface
          originalText={editingText || originalText || ''}
          onAccept={onDiffAccept}
          onDiscard={onDiffDiscard}
          onInsertBelow={onDiffInsertBelow}
          onTryAgain={onDiffTryAgain}
        />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-none">
      {/* Search Input */}
      <div className="relative">
        <div className="flex items-center bg-card border border-border rounded-lg shadow-lg hover:shadow-xl transition-shadow w-full">
          <div className="flex items-center pl-3">
            {trivialStreamingState.isStreaming ? (
              <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
            ) : (
            <Sparkles className="h-4 w-4 text-gray-400" />
            )}
          </div>
          <input
            ref={inputRef}
            type="text"
            value={trivialStreamingState.isStreaming ? "" : inputValue}
            onChange={handleInputChange}
            placeholder={
              trivialStreamingState.isStreaming 
                ? "Generating..." 
                : diffMode 
                ? "Type replacement text..." 
                : "Ask AI anything..."
            }
            className={`flex-1 px-3 py-2.5 bg-transparent border-none outline-none text-sm ${
              trivialStreamingState.isStreaming 
                ? 'text-blue-600 placeholder-blue-500' 
                : 'text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500'
            }`}
            disabled={isLoading || trivialStreamingState.isStreaming}
          />

          {inputValue && (
            <button
              onClick={() => {
                setInputValue('');
                setShowDropdown(true);
                setClassification(null);
                inputRef.current?.focus();
              }}
              className="p-1 mr-2 text-gray-400 hover:text-gray-600 rounded"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Classification Results */}
      {classification && !showDropdown && (
        <div className="absolute top-full left-0 mt-1 bg-card border border-border rounded-lg shadow-lg z-50 p-4 w-full">
          <div className="mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">🧪</span>
                              <span className="font-semibold text-gray-900 dark:text-gray-100">OrchestrationAgent Classification</span>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Tier</div>
                <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                  classification.tier === 'trivial' 
                    ? 'bg-green-100 text-green-800' 
                    : classification.tier === 'overpowered'
                    ? 'bg-purple-100 text-purple-800'
                    : 'bg-blue-100 text-blue-800'
                }`}>
                  {classification.tier === 'trivial' && '⚡'} 
                  {classification.tier === 'overpowered' && '🚀'} 
                  {classification.tier === 'hybrid' && '🔗'} 
                  {classification.tier}
                </div>
              </div>
              
              <div>
                <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-1">Confidence</div>
                <div className="font-mono text-gray-900 dark:text-gray-100">
                  {Math.round(classification.confidence * 100)}%
                </div>
              </div>
              
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Operation Type</div>
                <div className="text-gray-900 text-xs bg-gray-100 px-2 py-1 rounded">
                  {classification.operationType}
                </div>
              </div>
              
              <div>
                <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Est. Time</div>
                <div className="font-mono text-gray-900">
                  {classification.estimatedTime}ms
                </div>
              </div>
            </div>
            
            <div className="mt-3">
              <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Reasoning</div>
              <div className="text-xs text-gray-700 bg-gray-50 p-2 rounded leading-relaxed">
                {classification.reasoning}
              </div>
            </div>
            
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => {
                  onQuerySubmit(inputValue.trim());
                  setShowDropdown(false);
                }}
                className="flex-1 px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700 transition-colors"
              >
                Proceed with {classification.tier} LLM
              </button>
              <button
                onClick={() => {
                  setClassification(null);
                  setShowDropdown(true);
                }}
                className="px-3 py-1.5 border border-gray-300 rounded text-xs text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Back
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dropdown Menu */}
      {showDropdown && !isLoading && !classification && (
        <div className="absolute top-full left-0 mt-1 bg-card border border-border rounded-lg shadow-lg z-50 py-1 w-full">
          {(diffMode ? DIFF_OPTIONS : AI_OPTIONS).map((section, sectionIndex) => (
            <div key={sectionIndex}>
              {/* Section Header */}
              <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {section.section}
              </div>
              
              {/* Section Items */}
              <div className="mb-1">
                {section.items.map((item, itemIndex) => (
                  <button
                    key={itemIndex}
                    onClick={() => handleOptionClick(item.query)}
                    className="w-full flex items-center px-3 py-2 text-sm text-foreground hover:bg-accent hover:text-accent-foreground transition-colors text-left rounded-sm mx-1"
                  >
                    <span className="text-muted-foreground mr-2 text-sm">{item.icon}</span>
                    <span>{item.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Streaming Progress State - Only for main LLM operations */}
      {isLoading && !trivialStreamingState.isStreaming && (
        <div className="absolute top-full left-0 mt-1 bg-card dark:bg-gray-800 border border-border dark:border-gray-700 rounded-lg shadow-lg z-50 py-4 w-full">
          <div className="px-4">
            <div className="flex items-center justify-center gap-3 text-sm text-gray-600 dark:text-gray-300 mb-3">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span className="font-medium">AI Processing...</span>
            </div>
            
            {/* Progress Bar */}
            {streamingProgress !== undefined && (
              <div className="mb-4">
                <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                  <span>Progress</span>
                  <span>{Math.round(streamingProgress * 100)}%</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                  <div 
                    className="bg-blue-500 h-1.5 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${Math.round(streamingProgress * 100)}%` }}
                  />
                </div>
              </div>
            )}
            
            {/* Live Status Feed - Show exactly what backend sends */}
            <div className="space-y-2">
              <div className="text-xs text-gray-500 dark:text-gray-400 font-medium mb-2">Live Updates:</div>
              
              {/* Current Status - Direct from backend */}
              {streamingStatus && (
                <div className="flex items-start gap-2 text-xs">
                  <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse mt-1 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="text-blue-600 dark:text-blue-400 font-medium">
                      {streamingStatus}
                    </div>
                    <div className="text-gray-400 dark:text-gray-500 text-xs">
                      {new Date().toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              )}
              
              {/* Show streaming history if available */}
              {streamingHistory && streamingHistory.length > 0 && (
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {streamingHistory.slice(-5).map((entry, index) => (
                    <div key={index} className="flex items-start gap-2 text-xs opacity-70">
                      <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                        entry.type === 'error' ? 'bg-red-400' :
                        entry.type === 'complete' ? 'bg-green-400' :
                        'bg-gray-400'
                      }`} />
                      <div className="flex-1">
                        <div className="text-gray-600 dark:text-gray-300">
                          {entry.message}
                        </div>
                        <div className="text-gray-400 dark:text-gray-500 text-xs">
                          {new Date(entry.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Fallback: If no history, just show current status prominently */}
              {(!streamingHistory || streamingHistory.length === 0) && streamingStatus && (
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                  <div className="text-sm text-blue-800 dark:text-blue-200 font-medium">
                    {streamingStatus}
                  </div>
                  {streamingProgress !== undefined && (
                    <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                      {Math.round(streamingProgress * 100)}% complete
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 