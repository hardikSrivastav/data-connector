import { useState, useEffect } from 'react';
import { Page, Workspace, Block, ReasoningChainData, ReasoningChainEvent } from '@/types';
import { agentClient, AgentQueryResponse } from '@/lib/agent-client';
import { useStorageManager } from '@/hooks/useStorageManager';
import { 
  BarChart3, 
  GitBranch, 
  Clock, 
  Database, 
  TrendingUp, 
  Eye, 
  Play,
  RotateCcw,
  Download,
  Share,
  Settings,
  Plus,
  AlertTriangle,
  Layout,
  Type,
  Table,
  BarChart2,
  Code,
  Quote,
  Minus,
  Hash
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ReasoningChain } from './ReasoningChain';
import { BlockEditor } from './BlockEditor';

interface CanvasWorkspaceProps {
  page: Page;
  workspace: Workspace;
  onNavigateBack: () => void;
  onUpdatePage: (updates: Partial<Page>) => void;
  onAddBlock?: (afterBlockId?: string, type?: Block['type']) => string;
  onUpdateBlock?: (blockId: string, updates: Partial<Block>) => void;
  onDeleteBlock?: (blockId: string) => void;
}

// Helper function to determine if a reasoning chain belongs to a specific canvas
const isChainRelevantToCanvas = (
  chain: ReasoningChainData, 
  canvasBlock: Block | undefined, 
  canvasPageId: string
): boolean => {
  if (!canvasBlock) return false;
  
  // Get canvas data for comparison
  const canvasData = canvasBlock.properties?.canvasData;
  
  // Method 1: Direct blockId match to canvas block
  if (chain.blockId === canvasBlock.id) {
    console.log(`🎯 Reasoning chain matched by blockId: ${chain.blockId} === ${canvasBlock.id}`);
    return true;
  }
  
  // Method 2: SessionId/threadId match
  if (chain.sessionId && canvasData?.threadId && chain.sessionId === canvasData.threadId) {
    console.log(`🎯 Reasoning chain matched by sessionId: ${chain.sessionId} === ${canvasData.threadId}`);
    return true;
  }
  
  // Method 3: Original query match (exact match)
  if (chain.originalQuery && canvasData?.originalQuery && chain.originalQuery === canvasData.originalQuery) {
    console.log(`🎯 Reasoning chain matched by originalQuery: "${chain.originalQuery}" === "${canvasData.originalQuery}"`);
    return true;
  }
  
  // Method 4: Check if chain's pageId matches this canvas workspace page
  if ((chain as any).pageId === canvasPageId) {
    console.log(`🎯 Reasoning chain matched by pageId: ${(chain as any).pageId} === ${canvasPageId}`);
    return true;
  }
  
  // Method 5: Check if chain's originalPageId matches canvas workspace page
  if ((chain as any).originalPageId === canvasPageId) {
    console.log(`🎯 Reasoning chain matched by originalPageId: ${(chain as any).originalPageId} === ${canvasPageId}`);
    return true;
  }
  
  console.log(`🎯 Reasoning chain NOT relevant:`, {
    chainBlockId: chain.blockId,
    canvasBlockId: canvasBlock.id,
    chainSessionId: chain.sessionId,
    canvasThreadId: canvasData?.threadId,
    chainQuery: chain.originalQuery?.substring(0, 50),
    canvasQuery: canvasData?.originalQuery?.substring(0, 50),
    chainPageId: (chain as any).pageId,
    chainOriginalPageId: (chain as any).originalPageId,
    canvasPageId
  });
  
  return false;
};

export const CanvasWorkspace = ({ 
  page, 
  workspace, 
  onNavigateBack, 
  onUpdatePage,
  onAddBlock,
  onUpdateBlock,
  onDeleteBlock
}: CanvasWorkspaceProps) => {
  const { storageManager } = useStorageManager({
    edition: 'enterprise',
    apiBaseUrl: import.meta.env.VITE_API_BASE || 'http://localhost:8787'
  });
  
  // Remove sidebar state since sidebar is removed
  const [selectedView, setSelectedView] = useState<'analysis' | 'data' | 'history' | 'reasoning' | 'visualizations'>('analysis');
  const [isQueryRunning, setIsQueryRunning] = useState(false);
  const [reasoningChains, setReasoningChains] = useState<Map<string, ReasoningChainData>>(new Map());
  const [incompleteChains, setIncompleteChains] = useState<Array<{ blockId: string; data: ReasoningChainData }>>();
  const [reasoningChainsLoaded, setReasoningChainsLoaded] = useState<Set<string>>(new Set());
  const [isLoadingReasoningChains, setIsLoadingReasoningChains] = useState(false);
  const [focusedBlockId, setFocusedBlockId] = useState<string | null>(null);
  const [showAddBlockMenu, setShowAddBlockMenu] = useState(false);
  const [visualizationData, setVisualizationData] = useState<Array<any>>([]);

  // ✅ NEW: Log visualizationData state changes
  useEffect(() => {
    console.log('📊📊📊 VISUALIZATION DATA STATE CHANGE 📊📊📊');
    console.log('  - New visualizationData length:', visualizationData.length);
    if (visualizationData.length > 0) {
      console.log('  - Visualization data items:');
      visualizationData.forEach((item, index) => {
        console.log(`    ${index + 1}. Session: ${item.sessionId}, Source: ${item.source}, Chart Type: ${item.complete_chart_config?.type || 'Unknown'}`);
        console.log(`       Has complete_chart_config: ${!!item.complete_chart_config}`);
        console.log(`       Chart config keys: ${item.complete_chart_config ? Object.keys(item.complete_chart_config).join(', ') : 'none'}`);
      });
    } else {
      console.log('  - No visualization data available');
    }
    console.log('📊📊📊 END VISUALIZATION DATA STATE CHANGE 📊📊📊\n');
  }, [visualizationData]);

  // Helper function to extract visualization data from reasoning chains
  const extractVisualizationData = () => {
    console.log('🔍 DEBUGGING: extractVisualizationData called');
    console.log('🔍 DEBUGGING: reasoningChains size:', reasoningChains.size);
    console.log('🔍 DEBUGGING: reasoningChains content:', Array.from(reasoningChains.entries()));
    
    const visualizations: any[] = [];
    
    reasoningChains.forEach((chainData, blockId) => {
      console.log(`🔍 DEBUGGING: Processing chain ${blockId}:`, {
        hasEvents: !!chainData.events,
        eventsCount: chainData.events?.length || 0,
        sessionId: chainData.sessionId,
        originalQuery: chainData.originalQuery,
        isComplete: chainData.isComplete
      });
      
              if (chainData.events) {
          console.log(`🔍 DEBUGGING: Chain ${blockId} events:`, chainData.events.map(e => ({ type: e.type, message: e.message?.substring(0, 50) })));
          
          // Log all unique event types
          const eventTypes = [...new Set(chainData.events.map((e: any) => e.type))];
          console.log(`🔍 DEBUGGING: Chain ${blockId} unique event types:`, eventTypes);
          
        // ✅ ENHANCED: Check for each visualization event type separately with detailed logging
          const visualizationCreatedEvents = chainData.events.filter((event: any) => event.type === 'visualization_created');
        const chartConfigEvents = chainData.events.filter((event: any) => event.type === 'chart_config');
        const chartConfigJsonEvents = chainData.events.filter((event: any) => event.type === 'chart_config_json');
        const hybridChartConfigJsonEvents = chainData.events.filter((event: any) => event.type === 'hybrid_chart_config_json');
        const chartJsonSavedEvents = chainData.events.filter((event: any) => event.type === 'chart_json_saved');
        const hybridChartJsonSavedEvents = chainData.events.filter((event: any) => event.type === 'hybrid_chart_json_saved');
        const hybridVisualizationFoundEvents = chainData.events.filter((event: any) => event.type === 'hybrid_visualization_found');
          const finalSynthesisEvents = chainData.events.filter((event: any) => event.type === 'final_synthesis_analysis');
          const chartEmojiEvents = chainData.events.filter((event: any) => event.message?.includes('🎨'));
          const visualizationWordEvents = chainData.events.filter((event: any) => event.message?.includes('visualization'));
          const chartWordEvents = chainData.events.filter((event: any) => event.message?.includes('chart'));
          
        console.log(`🔍 DEBUGGING: Chain ${blockId} DETAILED event breakdown:`, {
            visualization_created: visualizationCreatedEvents.length,
          chart_config: chartConfigEvents.length,
          chart_config_json: chartConfigJsonEvents.length,
          hybrid_chart_config_json: hybridChartConfigJsonEvents.length,
          chart_json_saved: chartJsonSavedEvents.length,
          hybrid_chart_json_saved: hybridChartJsonSavedEvents.length,
          hybrid_visualization_found: hybridVisualizationFoundEvents.length,
            final_synthesis_analysis: finalSynthesisEvents.length,
            chart_emoji: chartEmojiEvents.length,
            visualization_word: visualizationWordEvents.length,
            chart_word: chartWordEvents.length
          });
        
        // ✅ ENHANCED: Log the actual content of important visualization events
        if (chartConfigJsonEvents.length > 0) {
          console.log(`🎨 CHART CONFIG JSON EVENTS FOUND (${chartConfigJsonEvents.length}):`, chartConfigJsonEvents.map(e => ({
            type: e.type,
            message: e.message,
            metadata: e.metadata,
            hasChartConfig: !!e.metadata?.chart_config,
            chartConfigKeys: e.metadata?.chart_config ? Object.keys(e.metadata.chart_config) : [],
            timestamp: e.timestamp
          })));
        }
        
        if (hybridChartConfigJsonEvents.length > 0) {
          console.log(`🎨 HYBRID CHART CONFIG JSON EVENTS FOUND (${hybridChartConfigJsonEvents.length}):`, hybridChartConfigJsonEvents.map(e => ({
            type: e.type,
            message: e.message,
            metadata: e.metadata,
            hasChartConfig: !!e.metadata?.chart_config,
            chartConfigKeys: e.metadata?.chart_config ? Object.keys(e.metadata.chart_config) : [],
            timestamp: e.timestamp
          })));
        }
        
        if (visualizationCreatedEvents.length > 0) {
          console.log(`🎨 VISUALIZATION CREATED EVENTS FOUND (${visualizationCreatedEvents.length}):`, visualizationCreatedEvents.map(e => ({
            type: e.type,
            message: e.message,
            metadata: e.metadata,
            timestamp: e.timestamp
          })));
        }
          
          // ✅ NEW: Prioritize the consolidated visualization_complete event
          const visualizationCompleteEvents = chainData.events.filter((event: any) => 
            event.type === 'visualization_complete'
          );
          
          const vizEvents = chainData.events.filter((event: any) => 
            event.type === 'visualization_created' || 
            event.type === 'chart_config' ||
            event.type === 'chart_config_json' ||
            event.type === 'hybrid_chart_config_json' ||
            event.type === 'chart_json_saved' ||
            event.type === 'hybrid_chart_json_saved' ||
            event.type === 'hybrid_visualization_found' ||
            event.type === 'final_synthesis_analysis' ||
            event.message?.includes('🎨') ||
            event.message?.includes('visualization') ||
            event.message?.includes('chart')
          );
          
          // ✅ If we have visualization_complete events, use those; otherwise fall back to individual events
          const vizEventsToUse = visualizationCompleteEvents.length > 0 ? visualizationCompleteEvents : vizEvents;
          
          console.log(`🎯 VISUALIZATION EVENT PROCESSING:`, {
            blockId,
            visualizationCompleteEvents: visualizationCompleteEvents.length,
            otherVizEvents: vizEvents.length,
            usingCompleteEvents: visualizationCompleteEvents.length > 0,
            totalVizEvents: vizEventsToUse.length
          });
          
          console.log(`🔍 DEBUGGING: Chain ${blockId} found ${vizEventsToUse.length} visualization events:`, vizEventsToUse);
        
        vizEventsToUse.forEach(event => {
          const vizData: any = {
            blockId,
            sessionId: chainData.sessionId,
            originalQuery: chainData.originalQuery,
            timestamp: event.timestamp,
            event: event,
            rawData: event,
            source: event.type
          };

          // ✅ ENHANCED: Extract chart configuration data from specific events
          console.log(`🔍 PROCESSING EVENT FOR CHART CONFIG:`, {
            eventType: event.type,
            blockId,
            sessionId: chainData.sessionId,
            hasMetadata: !!event.metadata,
            metadataKeys: event.metadata ? Object.keys(event.metadata) : [],
            messageLength: event.message?.length || 0,
            messagePreview: event.message?.substring(0, 100)
          });
          
          if (event.type === 'chart_config_json' || event.type === 'hybrid_chart_config_json') {
            console.log(`🎨 FOUND CHART CONFIG EVENT:`, {
              type: event.type,
              hasMetadata: !!event.metadata,
              metadataKeys: event.metadata ? Object.keys(event.metadata) : [],
              hasChartConfig: !!event.metadata?.chart_config,
              hasFilePath: !!event.metadata?.file_path,
              hasMessage: !!event.message
            });
            
            // Extract the complete chart configuration from the event
            if (event.metadata?.chart_config) {
              vizData.complete_chart_config = event.metadata.chart_config;
              console.log('✅ CHART CONFIG EXTRACTED FROM METADATA:', {
                type: event.type,
                configSize: JSON.stringify(event.metadata.chart_config).length,
                hasData: !!event.metadata.chart_config.data,
                hasLayout: !!event.metadata.chart_config.layout,
                configType: event.metadata.chart_config.type,
                configKeys: Object.keys(event.metadata.chart_config)
              });
            } else {
              console.warn('❌ NO CHART CONFIG IN METADATA:', {
                type: event.type,
                metadataKeys: event.metadata ? Object.keys(event.metadata) : [],
                fullMetadata: event.metadata
              });
            }
            
            // Extract file path if available
            if (event.metadata?.file_path) {
              vizData.chart_json_file_path = event.metadata.file_path;
              console.log('📁 CHART FILE PATH FOUND:', event.metadata.file_path);
            }
            
            // Try to extract from message if no metadata
            if (!event.metadata?.chart_config && event.message) {
              console.log('🔍 TRYING TO EXTRACT CONFIG FROM MESSAGE:', event.message.substring(0, 200));
              try {
                const configMatch = event.message.match(/({.*})/s);
                if (configMatch) {
                  const parsedConfig = JSON.parse(configMatch[1]);
                  vizData.complete_chart_config = parsedConfig;
                  console.log('✅ CHART CONFIG EXTRACTED FROM MESSAGE:', {
                    configType: parsedConfig.type,
                    configKeys: Object.keys(parsedConfig),
                    hasData: !!parsedConfig.data
                  });
                } else {
                  console.warn('❌ NO JSON PATTERN FOUND IN MESSAGE');
                }
              } catch (e) {
                console.warn('❌ FAILED TO PARSE JSON FROM MESSAGE:', e);
              }
            }
          }

          // ✅ ENHANCED: Extract visualization creation metadata
          if (event.type === 'visualization_created') {
            if (event.metadata?.chart_type) {
              vizData.chart_type = event.metadata.chart_type;
            }
            if (event.metadata?.dataset_size) {
              vizData.dataset_size = event.metadata.dataset_size;
            }
            if (event.metadata?.intent) {
              vizData.intent = event.metadata.intent;
            }
          }

          // ✅ ENHANCED: Group related visualization events
          if (!vizData.visualization_events) {
            vizData.visualization_events = [];
          }
          vizData.visualization_events.push(event);

          console.log(`🔍 FINAL VISUALIZATION DATA ITEM:`, {
            blockId: vizData.blockId,
            sessionId: vizData.sessionId,
            eventType: vizData.event.type,
            source: vizData.source,
            hasCompleteChartConfig: !!vizData.complete_chart_config,
            hasChartJsonFilePath: !!vizData.chart_json_file_path,
            chartConfigKeys: vizData.complete_chart_config ? Object.keys(vizData.complete_chart_config) : [],
            visualizationEventsCount: vizData.visualization_events?.length || 0
          });
          
          // ✅ NEW: Handle the consolidated visualization_complete event
          if (event.type === 'visualization_complete') {
            console.log(`🎯 FOUND VISUALIZATION_COMPLETE EVENT:`, {
              type: event.type,
              hasMetadata: !!event.metadata,
              metadataKeys: event.metadata ? Object.keys(event.metadata) : [],
              hasChartConfig: !!event.metadata?.chart_config,
              hasVisualizationData: !!event.metadata?.visualization_data,
              hasChartSummary: !!event.metadata?.chart_summary,
              isVisualization: event.metadata?.is_visualization,
              readyForRender: event.metadata?.ready_for_render
            });
            
            // Extract complete chart configuration from consolidated event
            if (event.metadata?.chart_config) {
              vizData.complete_chart_config = event.metadata.chart_config;
              console.log('✅ CHART CONFIG EXTRACTED FROM VISUALIZATION_COMPLETE:', {
                configSize: JSON.stringify(event.metadata.chart_config).length,
                hasData: !!event.metadata.chart_config.data,
                hasLayout: !!event.metadata.chart_config.layout,
                configType: event.metadata.chart_config.type,
                configKeys: Object.keys(event.metadata.chart_config)
              });
            }
            
            // Extract chart summary for easy display
            if (event.metadata?.chart_summary) {
              vizData.chart_summary = event.metadata.chart_summary;
              console.log('✅ CHART SUMMARY EXTRACTED:', event.metadata.chart_summary);
            }
            
            // Extract complete visualization data
            if (event.metadata?.visualization_data) {
              vizData.visualization_data = event.metadata.visualization_data;
              console.log('✅ VISUALIZATION DATA EXTRACTED:', {
                dataSize: JSON.stringify(event.metadata.visualization_data).length,
                dataKeys: Object.keys(event.metadata.visualization_data)
              });
            }
            
            // Mark as ready for rendering
            vizData.ready_for_render = event.metadata?.ready_for_render || false;
            vizData.from_consolidated_event = true;
          }

          visualizations.push(vizData);
        });
      } else {
        console.log(`🔍 DEBUGGING: Chain ${blockId} has no events`);
      }
    });
    
    console.log('🔍 DEBUGGING: Total visualizations found:', visualizations.length);
    console.log('🔍 DEBUGGING: Visualizations data:', visualizations);
    
    // ✅ ENHANCED: Log chart config analysis
    const chartConfigItems = visualizations.filter(viz => viz.complete_chart_config);
    console.log('🎨 CHART CONFIG ANALYSIS:', {
      totalVisualizations: visualizations.length,
      itemsWithChartConfig: chartConfigItems.length,
      chartConfigSources: chartConfigItems.map(viz => ({
        blockId: viz.blockId,
        eventType: viz.event.type,
        configType: viz.complete_chart_config?.type,
        hasData: !!viz.complete_chart_config?.data,
        configKeys: viz.complete_chart_config ? Object.keys(viz.complete_chart_config) : []
      }))
    });
    
    return visualizations.sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  };

  // Helper function to filter blocks by view type for DISPLAY ONLY (not functionality restriction)
  const getBlocksForView = (view: string) => {
    const sortedBlocks = [...page.blocks].sort((a, b) => (a.order || 0) - (b.order || 0));
    
    switch (view) {
      case 'analysis':
        // Show text content, headings, quotes, and analysis-related blocks
        return sortedBlocks.filter(block => 
          ['heading1', 'heading2', 'heading3', 'text', 'quote', 'divider', 'code'].includes(block.type)
        );
      case 'data':
        // Show tables, stats, charts, and data-related blocks
        return sortedBlocks.filter(block => 
          ['table', 'stats', 'chart', 'graph', 'code', 'divider'].includes(block.type)
        );
      case 'history':
        // Show all blocks in chronological order
        return sortedBlocks;
      case 'reasoning':
        // Show ONLY blocks that actually have reasoning chains or AI-related content
        return sortedBlocks.filter(block => 
          block.properties?.reasoningChain || 
          block.properties?.canvasData?.reasoningChain
        );
      case 'visualizations':
        // Show visualization-related content
        return sortedBlocks.filter(block => 
          ['chart', 'graph', 'stats', 'code'].includes(block.type)
        );
      default:
        return sortedBlocks;
    }
  };

  // ✅ NEW: Extract visualization data from reasoning chains and populate visualizationData state
  useEffect(() => {
    console.log('🎨🎨🎨 CanvasWorkspace: COMPREHENSIVE VISUALIZATION DATA EXTRACTION 🎨🎨🎨');
    console.log('🔍 STEP 1: Initial State Check');
    console.log('  - reasoningChains.size:', reasoningChains.size);
    console.log('  - reasoningChains keys:', Array.from(reasoningChains.keys()));
    console.log('  - current visualizationData.length:', visualizationData.length);
    
    if (reasoningChains.size === 0) {
      console.log('❌ NO REASONING CHAINS AVAILABLE - Exiting early');
      return;
    }
    
    const newVisualizationData: Array<any> = [];
    let totalEventsProcessed = 0;
    let visualizationEventsFound = 0;
    
    console.log('🔍 STEP 2: Processing Each Reasoning Chain');
    reasoningChains.forEach((chainData, blockId) => {
      console.log(`\n📋 PROCESSING CHAIN: ${blockId}`);
      console.log('  - sessionId:', chainData.sessionId);
      console.log('  - eventsCount:', chainData.events?.length || 0);
      console.log('  - originalQuery:', chainData.originalQuery);
      console.log('  - isComplete:', chainData.isComplete);
      
      if (!chainData.events || chainData.events.length === 0) {
        console.log('  ❌ No events in this chain');
        return;
      }
      
      // Log all event types for debugging
      const eventTypes = chainData.events.map(e => e.type);
      console.log('  - eventTypes:', eventTypes);
      totalEventsProcessed += chainData.events.length;
      
      // Look for ALL visualization-related events with comprehensive logging
      const allVisualizationEvents = chainData.events.filter(event => 
        event.type === 'visualization_complete' ||
        event.type === 'chart_config_json' ||
        event.type === 'hybrid_chart_config_json' ||
        event.type === 'visualization_created' ||
        event.type === 'chart_config' ||
        (event.message && (
          event.message.includes('🎨') ||
          event.message.includes('visualization') ||
          event.message.includes('chart')
        ))
      );
      
      console.log(`  🎨 Found ${allVisualizationEvents.length} visualization-related events:`);
      allVisualizationEvents.forEach((event, idx) => {
        console.log(`    ${idx + 1}. Type: "${event.type}", Message: "${event.message?.substring(0, 50)}..."`);
        console.log(`       HasMetadata: ${!!event.metadata}, MetadataKeys: ${event.metadata ? Object.keys(event.metadata).join(', ') : 'none'}`);
        if (event.metadata) {
          console.log(`       Metadata Deep Inspection:`, {
            hasChartConfig: !!event.metadata.chart_config,
            chartConfigType: event.metadata.chart_config?.type,
            hasVisualizationData: !!event.metadata.visualization_data,
            allMetadataKeys: Object.keys(event.metadata)
          });
        }
      });
      
      visualizationEventsFound += allVisualizationEvents.length;
      
      // Process visualization_complete events specifically
      const visualizationCompleteEvents = chainData.events.filter(event => 
        event.type === 'visualization_complete'
      );
      
      console.log(`  🎯 Processing ${visualizationCompleteEvents.length} visualization_complete events:`);
      
      visualizationCompleteEvents.forEach((event, index) => {
        console.log(`\n    📊 VISUALIZATION_COMPLETE EVENT #${index + 1}:`);
        console.log('       - timestamp:', event.timestamp);
        console.log('       - message:', event.message);
        console.log('       - hasMetadata:', !!event.metadata);
        
        if (event.metadata) {
          console.log('       - metadata keys:', Object.keys(event.metadata));
          console.log('       - hasChartConfig:', !!event.metadata.chart_config);
          console.log('       - hasVisualizationData:', !!event.metadata.visualization_data);
          
          if (event.metadata.chart_config) {
            console.log('       - chartConfig type:', event.metadata.chart_config.type);
            console.log('       - chartConfig keys:', Object.keys(event.metadata.chart_config));
            console.log('       - chartConfig has data:', !!event.metadata.chart_config.data);
            console.log('       - chartConfig has layout:', !!event.metadata.chart_config.layout);
            
            const vizData = {
              sessionId: chainData.sessionId,
              blockId: blockId,
              timestamp: event.timestamp || new Date().toISOString(),
              originalQuery: chainData.originalQuery || 'Unknown query',
              source: 'reasoning_chain_visualization_complete',
              event: event,
              complete_chart_config: event.metadata.chart_config,
              visualization_data: event.metadata.visualization_data || {},
              chart_summary: event.metadata.chart_summary || event.message,
              full_metadata: event.metadata
            };
            
            newVisualizationData.push(vizData);
            console.log('       ✅ SUCCESSFULLY ADDED TO VISUALIZATION DATA');
            console.log('          - vizData sessionId:', vizData.sessionId);
            console.log('          - vizData chartType:', vizData.complete_chart_config?.type);
            console.log('          - vizData source:', vizData.source);
          } else {
            console.log('       ❌ NO CHART CONFIG IN METADATA');
          }
        } else {
          console.log('       ❌ NO METADATA IN EVENT');
        }
      });
      
      // Also check for legacy chart_config_json events
      const legacyChartEvents = chainData.events.filter(event => 
        event.type === 'chart_config_json' || event.type === 'hybrid_chart_config_json'
      );
      
      console.log(`  📜 Processing ${legacyChartEvents.length} legacy chart events:`);
      
      legacyChartEvents.forEach((event, index) => {
        console.log(`\n    📊 LEGACY CHART EVENT #${index + 1} (${event.type}):`);
        console.log('       - hasMetadata:', !!event.metadata);
        
        if (event.metadata?.chart_config) {
          console.log('       - has chart_config: YES');
          const vizData = {
            sessionId: chainData.sessionId,
            blockId: blockId,
            timestamp: event.timestamp || new Date().toISOString(),
            originalQuery: chainData.originalQuery || 'Unknown query',
            source: `reasoning_chain_${event.type}`,
            event: event,
            complete_chart_config: event.metadata.chart_config,
            visualization_data: event.metadata.visualization_data || {},
            chart_summary: event.message,
            full_metadata: event.metadata
          };
          
          newVisualizationData.push(vizData);
          console.log('       ✅ SUCCESSFULLY ADDED LEGACY CHART DATA');
        } else {
          console.log('       ❌ NO CHART CONFIG IN LEGACY EVENT');
        }
      });
    });
    
    // Sort by timestamp (newest first)
    newVisualizationData.sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
    
    console.log('\n🔍 STEP 3: FINAL SUMMARY');
    console.log(`  - Total reasoning chains processed: ${reasoningChains.size}`);
    console.log(`  - Total events processed: ${totalEventsProcessed}`);
    console.log(`  - Total visualization events found: ${visualizationEventsFound}`);
    console.log(`  - Final visualization data items: ${newVisualizationData.length}`);
    console.log(`  - Previous visualizationData length: ${visualizationData.length}`);
    
    if (newVisualizationData.length > 0) {
      console.log('  - Sample visualization data:', newVisualizationData[0]);
      console.log('  - All chart types found:', newVisualizationData.map(v => v.complete_chart_config?.type).filter(Boolean));
    }
    
    console.log('\n🔍 STEP 4: UPDATING STATE');
    // Update the visualizationData state
    setVisualizationData(newVisualizationData);
    console.log('  ✅ STATE UPDATED');
    
    console.log('🎨🎨🎨 VISUALIZATION DATA EXTRACTION COMPLETE 🎨🎨🎨\n');
    
  }, [reasoningChains]); // Re-run when reasoning chains change

  // All block types are always available - no view restrictions
  const getAllAvailableBlockTypes = (): Array<{ type: Block['type']; label: string; icon: any }> => {
    return [
      { type: 'text' as const, label: 'Text', icon: Type },
      { type: 'heading1' as const, label: 'Heading 1', icon: Hash },
      { type: 'heading2' as const, label: 'Heading 2', icon: Hash },
      { type: 'heading3' as const, label: 'Heading 3', icon: Hash },
      { type: 'quote' as const, label: 'Quote', icon: Quote },
      { type: 'code' as const, label: 'Code', icon: Code },
      { type: 'table' as const, label: 'Table', icon: Table },
      { type: 'stats' as const, label: 'Stats', icon: BarChart2 },
      { type: 'divider' as const, label: 'Divider', icon: Minus }
    ];
  };

  // Helper function to handle block focus
  const handleBlockFocus = (blockId: string) => {
    setFocusedBlockId(blockId);
  };

  // Standard block creation - no view restrictions
  const handleAddBlock = (type: Block['type']) => {
    if (onAddBlock) {
      const newBlockId = onAddBlock(undefined, type);
      setFocusedBlockId(newBlockId);
      setShowAddBlockMenu(false);
    }
  };

  // Enhanced initialization to populate with canvas data and load reasoning chains
  useEffect(() => {
    console.log('🎨 CanvasWorkspace: Enhanced initialization starting...');
    console.log('🎨 CanvasWorkspace: Page blocks count:', page.blocks.length);
    
    const initializeCanvasWorkspace = async () => {
      // Prevent repeated loading for the same page
      const initPageKey = `${page.id}_${workspace.pages.length}`;
      if (reasoningChainsLoaded.has(initPageKey)) {
        console.log(`🧠 CanvasWorkspace: Skipping initialization - already loaded for page ${page.id}`);
        return;
      }

      if (isLoadingReasoningChains) {
        console.log(`🧠 CanvasWorkspace: Skipping initialization - already in progress`);
        return;
      }

      setIsLoadingReasoningChains(true);
      
      // Check if page is empty but has canvas data available, and populate it
    const hasOnlyBasicContent = page.blocks.length <= 1 || 
      (page.blocks.length === 1 && page.blocks[0].type === 'heading1');
    
    if (hasOnlyBasicContent) {
      console.log('🎨 CanvasWorkspace: Page appears empty, looking for canvas data...');
      
      // Find the CanvasBlock that references this page
      const canvasBlock = workspace.pages.flatMap(p => p.blocks).find(block => 
        block.type === 'canvas' && 
        block.properties?.canvasPageId === page.id &&
        block.properties?.canvasData
      );
      
      if (canvasBlock?.properties?.canvasData) {
        console.log('🎯 CanvasWorkspace: Found canvas block with data, checking if it still exists...');
        
        // Double-check that the canvas block still exists in its page
        const canvasBlockStillExists = workspace.pages.some(p => 
          p.blocks.some(b => b.id === canvasBlock.id && b.type === 'canvas')
        );
        
        if (canvasBlockStillExists) {
          console.log('✅ CanvasWorkspace: Canvas block still exists, populating page...');
          const canvasData = canvasBlock.properties.canvasData;
          
          // Build blocks from canvas data
          const blocks = [];
          let nextOrder = 0;
          
          // Add main heading (or keep existing if present)
          const existingHeading = page.blocks.find(b => b.type === 'heading1');
          if (existingHeading) {
            blocks.push(existingHeading);
            nextOrder = 1;
          } else {
            blocks.push({
              id: `heading_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'heading1' as const,
              content: page.title || 'Canvas Analysis',
              order: nextOrder++
            });
          }
          
          // Add analysis if available
          if (canvasData.fullAnalysis) {
            blocks.push({
              id: `analysis_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'text' as const,
              content: canvasData.fullAnalysis,
              order: nextOrder++
            });
          }
          
          // Add table if available  
          if (canvasData.fullData && canvasData.fullData.headers && canvasData.fullData.rows) {
            blocks.push({
              id: `table_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'table' as const,
              content: '',
              order: nextOrder++,
              properties: {
                tableData: {
                  headers: canvasData.fullData.headers,
                  data: canvasData.fullData.rows
                }
              }
            });
          }
          
          // Add SQL query if available
          if (canvasData.sqlQuery) {
            blocks.push({
              id: `sql_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              type: 'code' as const,
              content: canvasData.sqlQuery,
              order: nextOrder++
            });
          }
          
          // Add divider for future analyses
          blocks.push({
            id: `divider_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type: 'divider' as const,
            content: '---',
            order: nextOrder++
          });
          
          console.log(`✅ CanvasWorkspace: Populating page with ${blocks.length} blocks from canvas data`);
          
          // Update the page with the populated blocks
          onUpdatePage({ blocks });
          }
        }
      }

      // Load reasoning chains from server API 
      const chains = new Map<string, ReasoningChainData>();
      const incomplete: Array<{ blockId: string; data: ReasoningChainData }> = [];
      
      // Find the original CanvasBlock that references this workspace page
      const originalCanvasBlock = workspace.pages.flatMap(p => p.blocks).find(block => 
        block.type === 'canvas' && 
        block.properties?.canvasPageId === page.id
      );
      
      // Get the original page ID (where the CanvasBlock lives)
      const originalPageId = originalCanvasBlock 
        ? workspace.pages.find(p => p.blocks.some(b => b.id === originalCanvasBlock.id))?.id
        : null;
      
      console.log(`🧠 CanvasWorkspace: Found original canvas block:`, {
        blockId: originalCanvasBlock?.id,
        originalPageId,
        currentPageId: page.id,
        threadId: originalCanvasBlock?.properties?.canvasData?.threadId,
        originalQuery: originalCanvasBlock?.properties?.canvasData?.originalQuery
      });
      
      // Load reasoning chains from both current page and original page
      const pageIdsToCheck = [page.id];
      if (originalPageId && originalPageId !== page.id) {
        pageIdsToCheck.push(originalPageId);
      }
      
      for (const pageId of pageIdsToCheck) {
        try {
          console.log(`🔍 DEBUGGING: Loading reasoning chains from server for page ${pageId}`);
          const serverReasoningChains = await storageManager.getReasoningChainsForPage(pageId);
          console.log(`🔍 DEBUGGING: Found ${serverReasoningChains.length} reasoning chains from server for page ${pageId}`);
          console.log(`🔍 DEBUGGING: Raw server reasoning chains:`, serverReasoningChains);
          
          serverReasoningChains.forEach(chain => {
            console.log(`🔍 DEBUGGING: Processing server chain:`, {
              sessionId: chain.sessionId,
              blockId: chain.blockId,
              originalQuery: chain.originalQuery,
              eventsCount: chain.events?.length || 0,
              events: chain.events?.map(e => ({ type: e.type, message: e.message?.substring(0, 50) })) || [],
              isComplete: chain.isComplete,
              status: chain.status
            });
            
            if (chain.sessionId) {
              const chainKey = chain.blockId || chain.sessionId; // Use blockId if available, otherwise sessionId
              
              // Only add if not already loaded (avoid duplicates)
              if (!chains.has(chainKey)) {
                // Filter reasoning chains to only include ones related to this specific canvas
                const isRelevantChain = isChainRelevantToCanvas(chain, originalCanvasBlock, page.id);
                
                console.log(`🔍 DEBUGGING: Chain relevance check:`, {
                  chainKey,
                  isRelevantChain,
                  originalCanvasBlockId: originalCanvasBlock?.id,
                  pageId: page.id
                });
                
                if (isRelevantChain) {
                  chains.set(chainKey, chain);
                  console.log(`🔍 DEBUGGING: ✅ Added relevant reasoning chain ${chain.sessionId} from page ${pageId}, events: ${chain.events?.length || 0}, complete: ${chain.isComplete}`);
                  
                  // Check if this is an incomplete chain
                  if (!chain.isComplete && chain.status === 'streaming') {
                    incomplete.push({ blockId: chainKey, data: chain });
                  }
                } else {
                  console.log(`🔍 DEBUGGING: ❌ Skipping irrelevant reasoning chain ${chain.sessionId} for this canvas`);
                }
              } else {
                console.log(`🔍 DEBUGGING: ⚠️  Chain ${chainKey} already loaded, skipping duplicate`);
              }
            } else {
              console.log(`🔍 DEBUGGING: ⚠️  Chain has no sessionId, skipping:`, chain);
            }
          });
        } catch (error) {
          console.error(`🔍 DEBUGGING: ❌ Failed to load reasoning chains from server for page ${pageId}:`, error);
        }
      }
      
      // Fallback: Also check for reasoning chains in block properties (legacy support)
      // Check current page blocks
      page.blocks.forEach(block => {
        // Check for reasoning chains in block properties
        if (block.properties?.reasoningChain) {
          const reasoningData = block.properties.reasoningChain as ReasoningChainData;
          console.log(`🧠 CanvasWorkspace: Found legacy reasoning chain in current page block ${block.id}, events: ${reasoningData.events?.length || 0}, complete: ${reasoningData.isComplete}`);
          
          // Only add if not already loaded from server and is relevant to this canvas
          if (!chains.has(block.id)) {
            const isRelevant = isChainRelevantToCanvas(reasoningData, originalCanvasBlock, page.id);
            if (isRelevant) {
              chains.set(block.id, reasoningData);
              
              // Check if this is an incomplete chain
              if (!reasoningData.isComplete && reasoningData.status === 'streaming') {
                incomplete.push({ blockId: block.id, data: reasoningData });
              }
            }
          }
        }
        
        // Also check legacy canvas data format
        if (block.properties?.canvasData?.reasoningChain) {
          const legacyReasoningData = block.properties.canvasData.reasoningChain;
          console.log(`🧠 CanvasWorkspace: Found legacy canvas reasoning chain for current page block ${block.id}`);
          
          // Only add if not already loaded from server and is relevant to this canvas
          if (!chains.has(block.id)) {
            // Convert legacy format to new format
            const convertedData: ReasoningChainData = {
              events: legacyReasoningData || [],
              originalQuery: block.properties.canvasData.originalQuery || 'Legacy Query',
              sessionId: block.properties.canvasData.threadId,
              isComplete: true, // Assume legacy chains are complete
              lastUpdated: new Date().toISOString(),
              status: 'completed',
              progress: 1.0
            };
            
            const isRelevant = isChainRelevantToCanvas(convertedData, originalCanvasBlock, page.id);
            if (isRelevant) {
              chains.set(block.id, convertedData);
            }
          }
        }
      });
      
      // Also check the original canvas block for reasoning chains
      if (originalCanvasBlock?.properties?.canvasData?.reasoningChain) {
        const originalReasoningData = originalCanvasBlock.properties.canvasData.reasoningChain;
        console.log(`🧠 CanvasWorkspace: Found reasoning chain in original canvas block ${originalCanvasBlock.id}`);
        
        // Only add if not already loaded
        if (!chains.has(originalCanvasBlock.id)) {
          // Handle both new object format and old array format
          let convertedData: ReasoningChainData;
          
          if (typeof originalReasoningData === 'object' && originalReasoningData !== null && !Array.isArray(originalReasoningData) && 'events' in originalReasoningData) {
            // New format - use as is
            convertedData = originalReasoningData as ReasoningChainData;
          } else if (Array.isArray(originalReasoningData)) {
            // Old array format - convert
            convertedData = {
              events: originalReasoningData,
              originalQuery: originalCanvasBlock.properties.canvasData.originalQuery || 'Canvas Query',
              sessionId: originalCanvasBlock.properties.canvasData.threadId,
              isComplete: true, // Assume legacy chains are complete
              lastUpdated: new Date().toISOString(),
              status: 'completed',
              progress: 1.0
            };
          } else {
            return; // Skip invalid format
          }
          
          // This should always be relevant since it's from the original canvas block itself
          // But let's still check for consistency
          const isRelevant = isChainRelevantToCanvas(convertedData, originalCanvasBlock, page.id);
          if (isRelevant) {
            chains.set(originalCanvasBlock.id, convertedData);
            
            // Check if this is an incomplete chain
            if (!convertedData.isComplete && convertedData.status === 'streaming') {
              incomplete.push({ blockId: originalCanvasBlock.id, data: convertedData });
            }
          }
        }
      }
      
      console.log(`🧠 CanvasWorkspace: Total loaded ${chains.size} reasoning chains, ${incomplete.length} incomplete`);
      setReasoningChains(chains);
      setIncompleteChains(incomplete);
      
      // Mark this page as loaded
      const loadedPageKey = `${page.id}_${workspace.pages.length}`;
      setReasoningChainsLoaded(prev => {
        const newSet = new Set(prev);
        newSet.add(loadedPageKey);
        return newSet;
      });
      
      setIsLoadingReasoningChains(false);
      
      console.log(`🧠🧠🧠 REASONING CHAINS LOADED 🧠🧠🧠`);
      console.log(`  - Loaded ${chains.size} reasoning chains for page ${page.id}`);
      console.log(`  - Chain sessions:`, Array.from(chains.keys()));
      chains.forEach((chainData, blockId) => {
        console.log(`    Chain ${blockId}:`);
        console.log(`      - sessionId: ${chainData.sessionId}`);
        console.log(`      - eventsCount: ${chainData.events?.length || 0}`);
        console.log(`      - originalQuery: ${chainData.originalQuery}`);
        console.log(`      - isComplete: ${chainData.isComplete}`);
        if (chainData.events) {
          const eventTypes = chainData.events.map(e => e.type);
          console.log(`      - eventTypes: ${eventTypes.join(', ')}`);
          const vizEvents = chainData.events.filter(e => 
            e.type === 'visualization_complete' || 
            e.type === 'chart_config_json' ||
            e.type === 'hybrid_chart_config_json'
          );
          console.log(`      - visualization events: ${vizEvents.length}`);
          vizEvents.forEach((event, idx) => {
            console.log(`        ${idx + 1}. ${event.type} - hasMetadata: ${!!event.metadata} - hasChartConfig: ${!!event.metadata?.chart_config}`);
          });
        }
      });
      console.log(`🧠🧠🧠 END REASONING CHAINS LOADED 🧠🧠🧠\n`);
    };

    // Debounce the initialization to prevent rapid successive calls
    const debounceTimeout = setTimeout(() => {
      initializeCanvasWorkspace();
    }, 300); // 300ms debounce
    
    return () => clearTimeout(debounceTimeout);
  }, [page.id, workspace.pages.length, onUpdatePage, reasoningChainsLoaded, isLoadingReasoningChains]); // Removed page.blocks.length dependency

  // Enhanced query handler with reasoning chain recovery
  const handleRunNewQuery = async (queryText?: string) => {
    const finalQuery = queryText || prompt('Enter your SQL query or natural language question:');
    if (!finalQuery || finalQuery.trim() === '') return;
    
    console.log('🚀 CanvasWorkspace: Executing new query:', finalQuery);
      setIsQueryRunning(true);
      
    try {
      // Add a timestamp heading for this analysis
      const timestamp = new Date().toLocaleString();
      const headingId = onAddBlock ? onAddBlock(undefined, 'heading2') : null;
      if (headingId && onUpdateBlock) {
        onUpdateBlock(headingId, {
          content: `Analysis - ${timestamp}`
        });
      }
      
      // Add loading indicator
      const loadingId = onAddBlock ? onAddBlock(undefined, 'text') : null;
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: '🔄 Running query and analyzing results...'
        });
      }
      
      // ✅ FIXED: Use streaming API to capture visualization data
      console.log('🔍 DEBUGGING: About to call agentClient.queryStream with:', {
        question: finalQuery.trim(),
        analyze: true,
        force_langgraph: true,
        show_captured_data: true
      });
      
      let streamingResponse: any = null;
      
      await agentClient.queryStream({
        question: finalQuery.trim(),
        analyze: true,
        force_langgraph: true,
        show_captured_data: true
      }, {
        onStatus: (message) => {
          console.log('🌊 CanvasWorkspace: Streaming status:', message);
          if (loadingId && onUpdateBlock) {
            onUpdateBlock(loadingId, {
              content: `🔄 ${message}`
            });
          }
        },
        onComplete: (results, sessionId) => {
          console.log('🔍 DEBUGGING: agentClient.queryStream onComplete:', {
            hasRows: !!results.rows,
            rowsLength: results.rows?.length || 0,
            hasAnalysis: !!results.analysis,
            hasSql: !!results.sql,
            hasVisualizationData: !!results.visualization_data,
            visualizationDataLength: results.visualization_data?.length || 0,
            hasCompleteChartConfig: !!results.complete_chart_config,
            chartJsonFilePath: results.chart_json_file_path,
            responseKeys: Object.keys(results),
            sessionId: sessionId
          });
          
          streamingResponse = results;
          
          // ✅ NEW: Extract and store visualization data from streaming response  
          if (results.visualization_data || results.complete_chart_config) {
            console.log('🎨 CanvasWorkspace: Detected visualization data from streaming:', {
              visualization_data: results.visualization_data,
              complete_chart_config: results.complete_chart_config,
              chart_json_file_path: results.chart_json_file_path
            });
            
            setVisualizationData(prev => [
              ...prev,
              {
                sessionId: sessionId || results.captured_data?.execution_summary?.session_id || 'unknown',
                timestamp: new Date().toISOString(),
                originalQuery: finalQuery,
                source: 'agent_streaming_query',
                visualization_events: results.visualization_data || [],
                complete_chart_config: results.complete_chart_config,
                chart_json_file_path: results.chart_json_file_path,
                full_response: results
              }
            ]);
          }
        },
        onError: (error, errorCode, recoverable) => {
          console.error('❌ CanvasWorkspace: Streaming error:', { error, errorCode, recoverable });
          throw new Error(error);
        }
      });
      
      const response = streamingResponse;
      
      console.log('✅ CanvasWorkspace: Query completed successfully');
      console.log('📊 CanvasWorkspace: Response data:', {
        rowsCount: response.rows?.length || 0,
        hasAnalysis: !!response.analysis,
        sql: response.sql?.substring(0, 100) + '...'
      });
      
      // Update loading text with query details
      if (loadingId && onUpdateBlock) {
        onUpdateBlock(loadingId, {
          content: `**Query:** ${response.sql || finalQuery}`
        });
      }
      
      // Add analysis summary
      if (response.analysis) {
        const analysisId = onAddBlock ? onAddBlock(undefined, 'text') : null;
        if (analysisId && onUpdateBlock) {
          onUpdateBlock(analysisId, {
            content: response.analysis
          });
        }
      }
      
      // Add query results as table with proper data conversion
      if (response.rows && response.rows.length > 0) {
        console.log('📊 CanvasWorkspace: Converting query results to table...');
        
        // Convert response data, handling MongoDB objects, Decimal and other special types
        const convertValue = (value: any): string => {
          if (value === null || value === undefined) return '';
          
          // Handle Decimal objects
          if (typeof value === 'object' && value.constructor && value.constructor.name === 'Decimal') {
            return value.toString();
          }
          
          // Handle Date objects
          if (value instanceof Date) return value.toISOString();
          
          // Handle MongoDB ObjectId
          if (typeof value === 'object' && value.constructor && value.constructor.name === 'ObjectId') {
            return value.toString();
          }
          
          // Handle arrays - show as JSON or comma-separated for simple arrays
          if (Array.isArray(value)) {
            if (value.length === 0) return '[]';
            if (value.every(item => typeof item === 'string' || typeof item === 'number')) {
              return value.join(', ');
            }
            return JSON.stringify(value);
          }
          
          // Handle complex objects (MongoDB documents, nested objects)
          if (typeof value === 'object' && value !== null) {
            // For simple key-value objects, show as JSON
            try {
              return JSON.stringify(value);
            } catch (e) {
              // Fallback if JSON.stringify fails
              return Object.prototype.toString.call(value);
            }
          }
          
          // Handle primitives (string, number, boolean)
          return String(value);
        };
        
        // Get headers from first row
        const headers = Object.keys(response.rows[0]);
        console.log('📊 CanvasWorkspace: Table headers:', headers);
        
        // Convert rows to string arrays, handling special types
        const tableData = response.rows.map(row => 
          headers.map(header => convertValue(row[header]))
        );
        
        console.log('📊 CanvasWorkspace: Table data sample:', {
          headers,
          firstRow: tableData[0],
          totalRows: tableData.length
        });
        
        const tableId = onAddBlock ? onAddBlock(undefined, 'table') : null;
        if (tableId && onUpdateBlock) {
          onUpdateBlock(tableId, {
            content: 'Query Results',
                properties: {
              tableData: {
                rows: response.rows.length,
                cols: headers.length,
                headers: headers,
                data: tableData
              }
            }
          });
          
          console.log('✅ CanvasWorkspace: Table block created successfully with ID:', tableId);
        }
      }
      
      // Add divider for next analysis
      onAddBlock?.(undefined, 'divider');
      
    } catch (error) {
      console.error('❌ CanvasWorkspace: Query failed:', error);
      
      // Show error
      const errorId = onAddBlock ? onAddBlock(undefined, 'quote') : null;
      if (errorId && onUpdateBlock) {
        onUpdateBlock(errorId, {
          content: `❌ **Error:** ${error.message || 'Query execution failed'}`
        });
      }
    } finally {
      setIsQueryRunning(false);
    }
  };

  // Recovery handlers
  const handleResumeQuery = async (query: string) => {
    console.log('🔄 CanvasWorkspace: Resuming interrupted query:', query);
    await handleRunNewQuery(query);
  };

  const handleRetryQuery = async (query: string) => {
    console.log('🔄 CanvasWorkspace: Retrying failed query:', query);
    await handleRunNewQuery(query);
  };

  return (
    <div className="flex h-screen w-full bg-white dark:bg-gray-900">
      {/* Main Content Area - Full Width */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onNavigateBack}
                className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
              >
                ← Back to Page
              </Button>
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{page.title}</h1>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => handleRunNewQuery()}
                disabled={isQueryRunning}
              >
                <Play className="h-4 w-4 mr-2" />
                {isQueryRunning ? 'Running...' : 'New Query'}
              </Button>
              <Button size="sm" variant="outline">
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
              <Button size="sm" variant="outline">
                <Share className="h-4 w-4 mr-2" />
                Share
              </Button>
              <Button size="sm" variant="ghost">
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* View Tabs */}
          <div className="flex border-t border-gray-200 dark:border-gray-700">
            {[
              { id: 'analysis', label: 'Analysis', icon: Eye },
              { id: 'data', label: 'Data', icon: Database },
              { id: 'history', label: 'History', icon: Clock },
              { id: 'reasoning', label: 'AI Reasoning', icon: GitBranch },
              { id: 'visualizations', label: 'Visualizations', icon: BarChart2 }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  selectedView === id
                    ? "border-blue-500 dark:border-blue-400 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                )}
                onClick={() => setSelectedView(id as any)}
              >
                <Icon className="h-4 w-4" />
                {label}
                              {/* Show count of relevant blocks for each tab */}
              <span className="ml-1 px-1.5 py-0.5 text-xs bg-gray-500 text-white rounded-full">
                {id === 'visualizations' ? extractVisualizationData().length : getBlocksForView(id).length}
              </span>
              {id === 'reasoning' && incompleteChains && incompleteChains.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-yellow-500 text-white rounded-full">
                  {incompleteChains.length}
                </span>
              )}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-6xl mx-auto">
            {/* View-specific header and add block controls */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {selectedView === 'analysis' && 'Analysis Workspace'}
                  {selectedView === 'data' && 'Data Workspace'}
                  {selectedView === 'history' && 'Complete History'}
                  {selectedView === 'reasoning' && 'AI Reasoning Workspace'}
                  {selectedView === 'visualizations' && 'Visualization Data'}
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {selectedView === 'analysis' && 'View and organize your analysis content'}
                  {selectedView === 'data' && 'View tables, stats, and data visualizations'}
                  {selectedView === 'history' && 'View all content chronologically'}
                  {selectedView === 'reasoning' && 'View AI reasoning chains and thought processes'}
                  {selectedView === 'visualizations' && 'View raw visualization JSON data from LangGraph'}
                </p>
              </div>
              
              {/* Add Block Button */}
              <div className="relative">
                <Button 
                  onClick={() => setShowAddBlockMenu(!showAddBlockMenu)}
                  size="sm"
                  className="gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Add Block
                </Button>
                
                {/* Add Block Dropdown */}
                {showAddBlockMenu && (
                  <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
                    <div className="p-2">
                      <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2 px-2">
                        Add Block
                      </div>
                      {getAllAvailableBlockTypes().map(({ type, label, icon: Icon }) => (
                        <button
                          key={type}
                          onClick={() => handleAddBlock(type)}
                          className="w-full flex items-center gap-2 px-2 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                        >
                          <Icon className="h-4 w-4" />
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>



            {/* Blocks Content */}
            <div className="space-y-4">
              {(() => {
                const blocksForView = getBlocksForView(selectedView);
                
                console.log(`🎯 Rendering ${selectedView} view:`, {
                  selectedView,
                  totalBlocks: page.blocks.length,
                  filteredBlocks: blocksForView.length,
                  blockTypes: blocksForView.map(b => b.type)
                });
                
                // Special content for reasoning view
                const reasoningContent = selectedView === 'reasoning' && (
                  <>
                    {/* Incomplete chains notification */}
                    {incompleteChains && incompleteChains.length > 0 && (
                      <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4 mb-6">
                        <div className="flex items-center gap-2 mb-2">
                          <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                          <h3 className="font-medium text-yellow-900 dark:text-yellow-100">Incomplete Queries Found</h3>
                        </div>
                        <p className="text-sm text-yellow-800 dark:text-yellow-200 mb-3">
                          {incompleteChains.length} query{incompleteChains.length !== 1 ? 'ies were' : ' was'} interrupted. You can resume or retry them.
                        </p>
                      </div>
                    )}

                    {/* Reasoning chains display */}
                    {Array.from(reasoningChains.entries()).length > 0 && (
                      <div className="space-y-4 mb-8">
                        <h3 className="text-md font-medium text-gray-900 dark:text-gray-100">
                          AI Reasoning Chains ({reasoningChains.size})
                        </h3>
                        {Array.from(reasoningChains.entries()).map(([blockId, reasoningData]) => (
                          <ReasoningChain
                            key={blockId}
                            reasoningData={reasoningData}
                            title={`Block ${blockId.substring(0, 8)} - AI Reasoning`}
                            collapsed={false}
                            showRecoveryOptions={!reasoningData.isComplete}
                            onResumeQuery={handleResumeQuery}
                            onRetryQuery={handleRetryQuery}
                          />
                        ))}
                      </div>
                    )}
                  </>
                );

                // Special content for visualizations view
                const visualizationContent = selectedView === 'visualizations' && (
                  <>
                    <div className="space-y-6 mb-8">
                      {/* Chart Configuration JSON from Agent Responses */}
                      <div>
                        <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 mb-4">
                        <BarChart2 className="h-5 w-5" />
                          Chart Configuration JSON ({visualizationData.length})
                      </h3>
                        {(() => {
                          console.log('🖥️🖥️🖥️ RENDERING VISUALIZATION CONTENT 🖥️🖥️🖥️');
                          console.log('  - selectedView:', selectedView);
                          console.log('  - visualizationData.length:', visualizationData.length);
                          console.log('  - visualizationData items:', visualizationData.map(v => ({
                            sessionId: v.sessionId,
                            source: v.source,
                            hasChartConfig: !!v.complete_chart_config,
                            chartType: v.complete_chart_config?.type
                          })));
                          console.log('🖥️🖥️🖥️ END RENDERING VISUALIZATION CONTENT 🖥️🖥️🖥️');
                          return null;
                        })()}
                        {visualizationData.length === 0 ? (
                        <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 text-center">
                          <BarChart2 className="h-8 w-8 text-gray-400 dark:text-gray-500 mx-auto mb-3" />
                            <p className="text-gray-600 dark:text-gray-400">No chart configurations found yet</p>
                          <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
                              Run queries that create visualizations to see complete Plotly chart configurations here
                          </p>
                        </div>
                      ) : (
                          <div className="space-y-4">
                            {visualizationData.map((vizData, index) => (
                              <div key={index} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                                <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 p-4 border-b border-gray-200 dark:border-gray-700">
                                  <div className="flex items-center justify-between mb-2">
                                    <h4 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                                      🎨 {vizData.complete_chart_config?.type || 'Chart'} Chart #{index + 1}
                                      <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-1 rounded">
                                        {vizData.source === 'reasoning_chain_visualization_complete' ? 'Complete Event' : vizData.source}
                                      </span>
                                      {vizData.complete_chart_config?.type && (
                                        <span className="text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-1 rounded capitalize">
                                          {vizData.complete_chart_config.type}
                                        </span>
                                      )}
                              </h4>
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                      {new Date(vizData.timestamp).toLocaleString()}
                              </span>
                            </div>
                                  <div className="text-sm text-gray-600 dark:text-gray-300">
                                    <strong>Query:</strong> <span className="font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded text-xs">{vizData.originalQuery}</span>
                            </div>
                                  {vizData.sessionId && (
                                    <div className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                                      <strong>Session:</strong> <span className="font-mono text-xs">{vizData.sessionId}</span>
                            </div>
                                  )}
                                  {vizData.chart_json_file_path && (
                                    <div className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                                      <strong>Saved to:</strong> <span className="font-mono text-xs">{vizData.chart_json_file_path}</span>
                                    </div>
                                  )}
                                  
                                  {/* ✅ NEW: Display chart summary from consolidated visualization_complete events */}
                                  {vizData.chart_summary && (
                                    <div className="text-sm text-gray-600 dark:text-gray-300 mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-700">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-xs font-medium text-blue-700 dark:text-blue-300">📊 Chart Summary</span>
                                        {vizData.ready_for_render && (
                                          <span className="text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-1 rounded">
                                            Ready to Render
                                          </span>
                                        )}
                                        {vizData.from_consolidated_event && (
                                          <span className="text-xs bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 px-2 py-1 rounded">
                                            Consolidated Event
                                          </span>
                                        )}
                                      </div>
                                      <div className="grid grid-cols-2 gap-2 text-xs">
                                        <div><strong>Type:</strong> {vizData.chart_summary.chart_type || vizData.chart_summary.type}</div>
                                        <div><strong>Data Points:</strong> {vizData.chart_summary.data_points || vizData.chart_summary.dataset_size}</div>
                                        <div><strong>Title:</strong> {vizData.chart_summary.title}</div>
                                        <div><strong>Intent:</strong> {vizData.chart_summary.intent}</div>
                                        {vizData.chart_summary.execution_time && (
                                          <div><strong>Generated in:</strong> {(vizData.chart_summary.execution_time * 1000).toFixed(0)}ms</div>
                                        )}
                                        {vizData.chart_summary.confidence && (
                                          <div><strong>Confidence:</strong> {(vizData.chart_summary.confidence * 100).toFixed(1)}%</div>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                
                                {/* Chart Configuration JSON Display */}
                                {vizData.complete_chart_config && (
                                  <div className="p-4">
                                    <div className="flex items-center gap-2 mb-3">
                                      <Code className="h-4 w-4 text-green-600 dark:text-green-400" />
                                      <span className="text-sm font-medium text-green-700 dark:text-green-300">
                                        Complete Plotly Chart Configuration
                                      </span>
                                      <span className="text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-1 rounded">
                                        {JSON.stringify(vizData.complete_chart_config).length} bytes
                                      </span>
                                    </div>
                                    <div className="bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                                      <div className="bg-gray-100 dark:bg-gray-800 px-3 py-2 border-b border-gray-200 dark:border-gray-700">
                                        <span className="text-xs font-mono text-gray-600 dark:text-gray-400">plotly_chart_config.json</span>
                                      </div>
                                      <div className="p-3 max-h-96 overflow-y-auto">
                                        <pre className="text-xs text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">
                                          {JSON.stringify(vizData.complete_chart_config, null, 2)}
                                        </pre>
                                      </div>
                                    </div>
                                  </div>
                                )}
                                
                                {/* Visualization Events */}
                                {vizData.visualization_events && vizData.visualization_events.length > 0 && (
                                  <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                                    <div className="flex items-center gap-2 mb-3">
                                      <GitBranch className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                      <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                                        Visualization Events ({vizData.visualization_events.length})
                                      </span>
                                    </div>
                                    <div className="space-y-2">
                                      {vizData.visualization_events.map((event, eventIndex) => (
                                        <div key={eventIndex} className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded p-3">
                                          <div className="flex items-center justify-between mb-2">
                                            <span className="text-xs font-mono bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-1 rounded">
                                              {event.type}
                                            </span>
                                            {event.timestamp && (
                                              <span className="text-xs text-blue-600 dark:text-blue-400">
                                                {new Date(event.timestamp).toLocaleTimeString()}
                                              </span>
                                            )}
                                          </div>
                                          <pre className="text-xs text-blue-700 dark:text-blue-300 overflow-x-auto whitespace-pre-wrap">
                                            {JSON.stringify(event, null, 2)}
                                          </pre>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      
                      {/* Legacy Visualization Events from Reasoning Chains */}
                      <div>
                        <h3 className="text-md font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 mb-4">
                          <Eye className="h-5 w-5" />
                          Legacy Visualization Events ({extractVisualizationData().length})
                        </h3>
                        {extractVisualizationData().length === 0 ? (
                          <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
                            <p className="text-sm text-gray-600 dark:text-gray-400">No legacy visualization events found</p>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {extractVisualizationData().map((viz, index) => (
                              <div key={index} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                                <div className="flex items-center justify-between mb-2">
                                  <h5 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                    Legacy Event #{index + 1}
                                  </h5>
                                  <span className="text-xs text-gray-500 dark:text-gray-400">
                                    {new Date(viz.timestamp).toLocaleString()}
                                  </span>
                                </div>
                                <div className="text-xs text-gray-600 dark:text-gray-300 mb-2">
                                  Query: {viz.originalQuery?.substring(0, 80)}...
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-900 rounded p-2">
                              <pre className="text-xs text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap">
                                {JSON.stringify(viz.rawData, null, 2)}
                              </pre>
                            </div>
                          </div>
                            ))}
                          </div>
                      )}
                      </div>
                    </div>
                  </>
                );

                // Show reasoning content first if in reasoning view
                const contentToRender = [
                  ...(reasoningContent ? [<div key="reasoning-content">{reasoningContent}</div>] : []),
                  ...(visualizationContent ? [<div key="visualization-content">{visualizationContent}</div>] : []),
                  ...blocksForView.map((block) => (
                    <div key={block.id} className="group">
                      <BlockEditor
                        block={block}
                        onUpdate={(updates) => onUpdateBlock?.(block.id, updates)}
                        onAddBlock={(type) => onAddBlock?.(block.id, type)}
                        onDeleteBlock={() => onDeleteBlock?.(block.id)}
                        onFocus={() => handleBlockFocus(block.id)}
                        isFocused={focusedBlockId === block.id}
                        onMoveUp={() => {
                          // TODO: Implement move up functionality
                          console.log('Move up block', block.id);
                        }}
                        onMoveDown={() => {
                          // TODO: Implement move down functionality
                          console.log('Move down block', block.id);
                        }}
                        workspace={workspace}
                        page={page}
                        onNavigateToPage={(pageId) => {
                          // TODO: Implement navigation to specific page
                          console.log('Navigate to page:', pageId);
                        }}
                      />
                    </div>
                  ))
                ];

                // Show empty state only if no content at all
                if (contentToRender.length === 0 || (blocksForView.length === 0 && !reasoningContent && !visualizationContent)) {
                  return (
                    <div className="text-center py-12">
                      <Layout className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
                        No {selectedView} content yet
                      </h3>
                      <p className="text-gray-500 dark:text-gray-400 mb-6">
                        {selectedView === 'analysis' && 'This view shows text, headings, quotes, and analysis content'}
                        {selectedView === 'data' && 'This view shows tables, stats, and data visualizations'}
                        {selectedView === 'history' && 'This view shows all content chronologically'}
                        {selectedView === 'reasoning' && 'This view shows AI reasoning and thought processes'}
                        {selectedView === 'visualizations' && 'This view shows raw JSON visualization data from LangGraph'}
                      </p>
                      <Button onClick={() => setShowAddBlockMenu(true)}>
                        <Plus className="h-4 w-4 mr-2" />
                        Add Content
                      </Button>
                    </div>
                  );
                }

                return contentToRender;
              })()}
            </div>

            {/* Quick Actions for New Query */}
            {selectedView === 'analysis' && (
              <div className="mt-8 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Quick Actions</h3>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => handleRunNewQuery()}>
                    <Play className="h-4 w-4 mr-2" />
                    Run New Query
                  </Button>
                  <Button size="sm" variant="outline">
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Refresh Data
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Click outside to close add block menu */}
          {showAddBlockMenu && (
            <div
              className="fixed inset-0 z-40"
              onClick={() => setShowAddBlockMenu(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}; 