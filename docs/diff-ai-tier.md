# Diff-Based AI Text Editing: Two-Tier LLM Architecture Implementation Guide

## Overview

This document outlines the implementation of a real-time diff-based text editing system that provides instant visual feedback as users type, similar to Notion's AI replacement feature. The system integrates with our two-tier LLM architecture: a trivial LLM for simple text edits and an overpowered LLM for complex operations, coordinated by an orchestration agent.

## System Architecture

### Two-Tier LLM Design

**Trivial LLM (Fast, Local-focused)**
- Purpose: Handle simple text transformations
- Operations: Grammar fixes, style improvements, basic reformatting
- Characteristics: Fast response, low compute cost, no external data access
- Implementation: Local model or lightweight API calls

**Overpowered LLM (Complex, Cross-database)**
- Purpose: Handle complex operations requiring context and data access
- Operations: Content generation with data, cross-database analysis, complex summarizations
- Characteristics: Slower response, high capability, full system access
- Implementation: GPT-4, Claude, or similar with tool access

**Orchestration Agent**
- Purpose: Route operations to appropriate LLM tier
- Responsibilities: Request classification, operation planning, result coordination
- Implementation: Smart routing logic with fallback mechanisms

### Component Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│   User Input    │────▶│ Orchestration Agent   │────▶│   Operation Router   │
└─────────────────┘     └──────────────────────┘     └─────────────────────┘
                               │                               │
                               ▼                               ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ Diff Algorithm  │◀───▶│  Trivial LLM     │     │  Overpowered LLM        │
│ (Real-time)     │     │  (Text Edits)    │     │  (Complex Operations)   │
└─────────────────┘     └──────────────────┘     └─────────────────────────┘
         │                       │                             │
         ▼                       ▼                             ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ Visual Renderer │     │ Direct Text Diff │     │ Structured Result Diff  │
└─────────────────┘     └──────────────────┘     └─────────────────────────┘
```

## Core Components Implementation

### 1. Diff Algorithm Implementation

**Core Interface:**
```typescript
interface DiffChange {
  type: 'added' | 'removed' | 'unchanged';
  value: string;
  index: number;
  confidence?: number;
}

function computeTextDiff(originalText: string, newText: string): DiffChange[]
```

**Algorithm Requirements:**
- Word-level granularity for natural editing boundaries
- Look-ahead mechanism to prevent fragmentation
- Performance optimized for real-time updates
- Support for both character and semantic-level changes

**Implementation Strategy:**
1. **Split Strategy**: Words + whitespace preservation
2. **Matching Algorithm**: Myers diff with semantic awareness
3. **Optimization**: Debounced updates with incremental processing
4. **Context Awareness**: Understand code vs prose vs structured data

### 2. Orchestration Agent Implementation

**Request Classification Logic:**
```typescript
interface OperationClassification {
  tier: 'trivial' | 'overpowered' | 'hybrid';
  confidence: number;
  reasoning: string;
  estimatedTime: number;
}

async function classifyOperation(request: string, context: BlockContext): Promise<OperationClassification>
```

**Classification Rules:**
- **Trivial Operations**: Grammar, punctuation, basic formatting, simple rewrites
- **Overpowered Operations**: Data-driven content, cross-block analysis, complex generation
- **Hybrid Operations**: Multi-step processes requiring both tiers

### 3. Visual Diff Rendering

**Component Structure:**
```typescript
const DiffRenderer = ({ changes, className, animationSpeed = 200 }) => {
  return (
    <span className={cn("diff-container", className)}>
      {changes.map((change, index) => (
        <DiffSpan 
          key={index}
          change={change}
          animationSpeed={animationSpeed}
        />
      ))}
    </span>
  );
};
```

**Styling System:**
- **Additions**: Green background, left border, fade-in animation
- **Deletions**: Red background, strikethrough, fade-out animation  
- **Unchanged**: Transparent, maintains text flow
- **Transitions**: Smooth 200ms transitions between states

## Step-by-Step Implementation Plan

### Phase 1: Foundation Components (Week 1)

#### Step 1: Core Diff Algorithm
**File**: `server/web/src/lib/diff/textDiff.ts`

**Implementation Tasks:**
1. Create Myers diff algorithm implementation
2. Add word-boundary detection logic
3. Implement look-ahead matching for context
4. Add performance optimizations (memoization, lazy evaluation)
5. Create unit tests for edge cases

**Acceptance Criteria:**
- Handles 10,000+ character documents in <50ms
- Preserves whitespace and formatting accurately
- Produces minimal, semantically meaningful changes
- Passes comprehensive test suite

#### Step 2: Visual Diff Components
**Files**: 
- `server/web/src/components/DiffRenderer.tsx`
- `server/web/src/components/DiffSpan.tsx`
- `server/web/src/styles/diff.css`

**Implementation Tasks:**
1. Create base DiffRenderer component
2. Implement DiffSpan with animation states
3. Design CSS for addition/deletion/unchanged states
4. Add accessibility support (screen readers, high contrast)
5. Create Storybook stories for component testing

**Acceptance Criteria:**
- Smooth animations without jank
- Accessible to screen readers
- Supports light/dark themes
- Responsive design for different screen sizes

#### Step 3: Orchestration Agent Core
**File**: `server/web/src/lib/orchestration/agent.ts`

**Implementation Tasks:**
1. Create operation classification system
2. Implement tier routing logic
3. Add confidence scoring mechanism
4. Create fallback handling for misclassifications
5. Add logging and analytics hooks

**Acceptance Criteria:**
- 95%+ accuracy on operation classification test suite
- <100ms classification time for typical requests
- Graceful degradation when classification is uncertain
- Comprehensive logging for optimization

### Phase 2: LLM Integration (Week 2)

#### Step 4: Trivial LLM Client
**File**: `server/web/src/lib/llm/trivialClient.ts`

**Implementation Tasks:**
1. Create lightweight LLM client interface
2. Implement text transformation methods
3. Add response streaming for real-time updates
4. Create caching layer for common operations
5. Add rate limiting and error handling

**Core Methods:**
```typescript
class TrivialLLMClient {
  async improveText(text: string): Promise<AsyncIterator<DiffChange[]>>
  async fixGrammar(text: string): Promise<AsyncIterator<DiffChange[]>>
  async adjustTone(text: string, tone: string): Promise<AsyncIterator<DiffChange[]>>
  async formatCode(code: string, language: string): Promise<AsyncIterator<DiffChange[]>>
}
```

#### Step 5: Integration with Existing Overpowered LLM
**File**: `server/web/src/lib/llm/overpoweredClient.ts`

**Implementation Tasks:**
1. Extend existing LLM client for diff operations
2. Add diff-aware prompt templates
3. Implement structured response parsing
4. Create cross-database context injection
5. Add result validation and safety checks

**Enhanced Methods:**
```typescript
class OverpoweredLLMClient extends LLMClient {
  async generateWithData(prompt: string, context: BlockContext): Promise<AsyncIterator<DiffChange[]>>
  async analyzeAndSummarize(data: any[], prompt: string): Promise<AsyncIterator<DiffChange[]>>
  async crossReferenceContent(text: string, sources: DataSource[]): Promise<AsyncIterator<DiffChange[]>>
}
```

#### Step 6: Orchestration Implementation
**File**: `server/web/src/lib/orchestration/orchestrator.ts`

**Implementation Tasks:**
1. Implement main orchestration logic
2. Add parallel processing for hybrid operations
3. Create result merging algorithms
4. Add progress tracking and cancellation
5. Implement error recovery and retry logic

**Core Interface:**
```typescript
class DiffOrchestrator {
  async processRequest(
    originalText: string,
    operation: string,
    context: BlockContext
  ): Promise<AsyncIterator<OrchestrationResult>>
}
```

### Phase 3: Editor Integration (Week 3)

#### Step 7: Enhanced AIQuerySelector
**File**: `server/web/src/components/AIQuerySelector.tsx`

**Implementation Tasks:**
1. Add diff mode toggle and controls
2. Implement streaming response handling
3. Create real-time preview system
4. Add operation cancellation support
5. Enhance error handling and recovery

**New Features:**
- Diff preview mode alongside existing functionality
- Progress indicators for long-running operations
- Real-time text transformation preview
- Undo/redo support for diff operations

#### Step 8: BlockEditor Integration
**File**: `server/web/src/components/BlockEditor.tsx`

**Implementation Tasks:**
1. Add diff editing mode to existing editor
2. Implement inline diff visualization
3. Create seamless mode switching
4. Add keyboard shortcuts for diff operations
5. Integrate with existing block type system

**Integration Points:**
- Extend existing `//` command system for diff operations
- Add new command patterns: `//improve`, `//fix`, `//tone:formal`
- Maintain compatibility with existing block operations
- Add diff history and rollback capabilities

#### Step 9: InlineEditor Component
**File**: `server/web/src/components/InlineEditor.tsx`

**Implementation Tasks:**
1. Create dual-view editor (input + preview)
2. Implement real-time diff computation
3. Add accept/reject controls for changes
4. Create smooth transitions between modes
5. Add collaborative editing support hooks

**Component Features:**
```typescript
interface InlineEditorProps {
  initialText: string;
  onSave: (finalText: string) => void;
  onCancel: () => void;
  placeholder?: string;
  showDiff?: boolean;
  diffMode?: 'inline' | 'side-by-side' | 'unified';
  operationType?: 'trivial' | 'overpowered' | 'auto';
}
```

### Phase 4: Advanced Features (Week 4)

#### Step 10: Performance Optimization
**Files**: 
- `server/web/src/lib/diff/performance.ts`
- `server/web/src/hooks/useDiffOptimization.ts`

**Implementation Tasks:**
1. Add debouncing and throttling for real-time updates
2. Implement virtual scrolling for large documents
3. Create worker threads for heavy diff computations
4. Add memory management for diff history
5. Optimize re-rendering with React optimization patterns

#### Step 11: Collaboration Features
**File**: `server/web/src/lib/collaboration/diffSync.ts`

**Implementation Tasks:**
1. Create operational transformation for diff operations
2. Add conflict resolution for simultaneous edits
3. Implement real-time diff broadcasting
4. Create merge algorithms for collaborative changes
5. Add user presence indicators during diff operations

#### Step 12: Analytics and Monitoring
**File**: `server/web/src/lib/analytics/diffAnalytics.ts`

**Implementation Tasks:**
1. Add usage tracking for operation types
2. Implement performance monitoring
3. Create user satisfaction feedback system
4. Add A/B testing framework for diff algorithms
5. Generate insights on operation effectiveness

## Integration with Existing Architecture

### BlockEditor Integration Strategy

**Current Flow Enhancement:**
```typescript
// Existing: //query → AIQuerySelector → creates new block
// Enhanced: //improve → DiffOrchestrator → modifies current block

const handleAICommand = async (command: string, content: string) => {
  if (command.startsWith('//')) {
    // Existing AI query flow (creates new blocks)
    return handleAIQuery(command.slice(2));
  } else if (command.startsWith('/improve') || command.startsWith('/fix')) {
    // New diff-based editing flow (modifies current block)
    return handleDiffOperation(command, content);
  }
  // ... other command handling
};
```

### Database Integration Points

**Schema Registry Integration:**
- Extend schema registry to track text content patterns
- Add context-aware suggestions based on content type
- Integrate with cross-database operations for data-driven edits

**Streaming Infrastructure:**
- Leverage existing streaming implementation for real-time diff updates
- Extend streaming status indicators for diff operations
- Add progress tracking for complex multi-tier operations

## Testing Strategy

### Unit Testing
- **Diff Algorithm**: Test with various text types and edge cases
- **LLM Clients**: Mock responses and test error handling
- **Orchestration**: Test classification accuracy and routing logic
- **Components**: Test rendering, animations, and user interactions

### Integration Testing
- **End-to-End Flows**: Complete diff operations from input to result
- **Performance Testing**: Large documents and concurrent operations
- **Cross-Browser Testing**: Ensure compatibility across browsers
- **Accessibility Testing**: Screen reader and keyboard navigation support

### User Acceptance Testing
- **Usability Studies**: Real users performing editing tasks
- **Performance Benchmarks**: Response time and system resource usage
- **Quality Assessment**: Accuracy of diff operations and LLM outputs
- **Edge Case Handling**: Unusual inputs and error scenarios

## Deployment Considerations

### Feature Flags
- **Gradual Rollout**: Enable diff editing for subsets of users
- **A/B Testing**: Compare different diff algorithms and UX patterns
- **Fallback Options**: Disable features if performance issues occur

### Performance Monitoring
- **Real-time Metrics**: Track response times and success rates
- **Resource Usage**: Monitor CPU, memory, and network utilization
- **User Analytics**: Measure adoption and satisfaction metrics

### Scaling Considerations
- **LLM API Limits**: Implement queuing and rate limiting
- **Client Performance**: Optimize for low-end devices
- **Server Resources**: Plan for increased computational load

## Future Enhancements

### Advanced Diff Features
- **Semantic Diffing**: Understand meaning changes vs cosmetic changes
- **Multi-language Support**: Language-specific diff algorithms
- **Rich Content**: Support for images, links, and formatted text

### AI Capabilities
- **Learning System**: Improve classification based on user feedback
- **Personalization**: Adapt to individual writing styles and preferences
- **Predictive Editing**: Suggest changes before user requests them

### Collaboration
- **Real-time Co-editing**: Multiple users editing with live diff sync
- **Review Workflows**: Approval processes for AI-suggested changes
- **Version Control**: Track and merge different edit branches

This implementation guide provides a comprehensive roadmap for building a sophisticated diff-based AI editing system that integrates seamlessly with the existing two-tier LLM architecture while providing real-time visual feedback and intelligent operation routing. 