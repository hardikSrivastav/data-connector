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

interface AIQuerySelectorProps {
  query: string;
  onQuerySubmit: (query: string) => void;
  onClose: () => void;
  isLoading?: boolean;
  streamingStatus?: string;
  streamingProgress?: number;
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

export const AIQuerySelector = ({ 
  query, 
  onQuerySubmit, 
  onClose, 
  isLoading = false, 
  streamingStatus,
  streamingProgress,
  // Diff mode props
  diffMode = false,
  originalText = '',
  onDiffAccept,
  onDiffDiscard,
  onDiffInsertBelow,
  onDiffTryAgain,
  blockContext,
  enableSmartRouting = true,
  editingText
}: AIQuerySelectorProps) => {
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

    // If in diff mode, treat input as replacement text
    if (diffMode) {
      console.log('🚀 ROUTE: Already in diff mode, closing dropdown');
      setShowDropdown(false);
      return;
    }

    // Smart routing: classify the query and route appropriately
    console.log('🚀 SMART ROUTING: Checking conditions...');
    console.log('🚀 SMART ROUTING: enableSmartRouting =', enableSmartRouting);
    console.log('🚀 SMART ROUTING: blockContext =', !!blockContext);
    console.log('🚀 SMART ROUTING: trivialSupported.length =', trivialSupported.length);
    
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
        // 3. AND we can map it to a supported trivial operation
        if (classification.tier === 'trivial' && classification.confidence > 0.7 && sourceText.trim()) {
          const operationType = isTextEditingOperation ? 'text editing' : 'content generation';
          console.log(`⚡ Attempting trivial routing for ${operationType}: ${classification.operationType}`);
          
          // Map common queries to trivial operations
          const operationMap: Record<string, string> = {
            'grammar': 'fix_grammar',
            'spelling': 'fix_spelling',
            'concise': 'make_concise',
            'clarity': 'improve_clarity',
            'tone': 'improve_tone',
            'expand': 'expand_text',
            'simplify': 'simplify_language',
            'examples': 'add_examples',
            'summarize': isTextEditingOperation ? 'make_concise' : 'summarize_content',
            'summary': isTextEditingOperation ? 'make_concise' : 'summarize_content',
            'shorten': 'make_concise',
            'lengthen': 'expand_text',
            'professional': 'improve_tone',
            'title': 'generate_title',
            'outline': 'create_outline'
          };
          
          // Try to map the operation type to a trivial operation
          let trivialOp = operationMap[classification.operationType];
          
          // If no direct mapping, try fuzzy matching
          if (!trivialOp) {
            const queryLower = trimmedQuery.toLowerCase();
            
            // Check for summarization keywords
            if (queryLower.includes('summarise') || queryLower.includes('summarize') || 
                queryLower.includes('summary') || queryLower.includes('overview')) {
              trivialOp = isTextEditingOperation ? 'make_concise' : 'summarize_content';
            }
            // Check for title generation
            else if (queryLower.includes('title') || queryLower.includes('heading')) {
              trivialOp = 'generate_title';
            }
            // Check for outline generation  
            else if (queryLower.includes('outline') || queryLower.includes('structure')) {
              trivialOp = 'create_outline';
            }
            // Fallback to supported operations
            else {
              trivialOp = trivialSupported.find(op => 
                classification.operationType.includes(op.replace('_', '')) ||
                queryLower.includes(op.replace('_', ' '))
              ) || 'improve_clarity';
            }
          }
          
          console.log(`🚀 TRIVIAL CHECK: Checking if operation '${trivialOp}' is supported...`);
          console.log(`🚀 TRIVIAL CHECK: Available operations:`, trivialSupported);
          console.log(`🚀 TRIVIAL CHECK: Operation supported:`, trivialSupported.includes(trivialOp));
          
          if (trivialSupported.includes(trivialOp)) {
            console.log(`⚡ SUCCESS: Routing to trivial LLM with operation: ${trivialOp}`);
            
            // For content generation operations, handle differently
            if (!isTextEditingOperation) {
              console.log(`📝 Content generation mode: creating new content`);
              // For content generation, we'll still use the trivial operation but mark it differently
              await handleTrivialOperation(trivialOp, sourceText);
            } else {
              console.log(`✏️ Text editing mode: modifying existing content`);
              await handleTrivialOperation(trivialOp, sourceText);
            }
            
            setShowDropdown(false);
            console.log('🚀 === TRIVIAL ROUTING COMPLETE ===');
            return;
          } else {
            console.log(`❌ FAILED: Trivial operation '${trivialOp}' not supported. Available: ${trivialSupported.join(', ')}`);
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

    // Check if this is a known trivial operation
    if (enableSmartRouting && originalText && trivialSupported.length > 0) {
      const trivialOperationNames = {
        'Fix grammar': 'fix_grammar',
        'Fix spelling': 'fix_spelling', 
        'Make it shorter': 'make_concise',
        'Make it longer': 'expand_text',
        'Improve clarity': 'improve_clarity',
        'Improve tone': 'improve_tone',
        'Simplify language': 'simplify_language',
        'Add examples': 'add_examples'
      };

      const operation = trivialOperationNames[optionQuery as keyof typeof trivialOperationNames];
      if (operation && trivialSupported.includes(operation)) {
        console.log(`⚡ Quick trivial operation: ${operation}`);
        await handleTrivialOperation(operation, originalText);
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
                                   <div className="text-sm leading-relaxed">
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
                      <span className="text-gray-600">{trivialResult}</span>
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
        <div className="absolute top-full left-0 mt-1 bg-card border border-border rounded-lg shadow-lg z-50 py-4 w-full">
          <div className="px-4">
            <div className="flex items-center justify-center gap-3 text-sm text-gray-600 mb-3">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span className="font-medium">Generating...</span>
            </div>
            
            {/* Streaming Status */}
            {streamingStatus && (
              <div className="text-center mb-3">
                <div className="text-xs text-gray-500 mb-1">Current step:</div>
                <div className="text-sm text-gray-700 font-medium">{streamingStatus}</div>
              </div>
            )}
            
            {/* Progress Bar */}
            {streamingProgress !== undefined && (
              <div className="mb-3">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Progress</span>
                  <span>{Math.round(streamingProgress * 100)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div 
                    className="bg-blue-500 h-1.5 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${Math.round(streamingProgress * 100)}%` }}
                  />
                </div>
              </div>
            )}
            
            {/* Streaming Steps Indicator */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('classif') ? 'bg-blue-500' : 
                  streamingStatus?.includes('databas') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('classif') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Analyzing query
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('schema') || streamingStatus?.includes('loading') ? 'bg-blue-500' : 
                  streamingStatus?.includes('generat') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('schema') || streamingStatus?.includes('loading') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Loading schemas
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('generat') ? 'bg-blue-500' : 
                  streamingStatus?.includes('execut') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('generat') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Generating query
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('execut') ? 'bg-blue-500' : 
                  streamingStatus?.includes('analyz') || streamingStatus?.includes('insight') ? 'bg-green-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('execut') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Executing query
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <div className={`w-2 h-2 rounded-full ${
                  streamingStatus?.includes('analyz') || streamingStatus?.includes('insight') ? 'bg-blue-500' : 'bg-gray-300'
                }`} />
                <span className={streamingStatus?.includes('analyz') || streamingStatus?.includes('insight') ? 'text-blue-600 font-medium' : 'text-gray-500'}>
                  Generating insights
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 