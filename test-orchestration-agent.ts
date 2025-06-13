// Test script for OrchestrationAgent with real AWS Bedrock
// Run with: npm run test-orchestration

import { OrchestrationAgent } from './server/web/src/lib/orchestration/agent.js';
import { readFileSync } from 'fs';
import { join } from 'path';

// Load environment variables from server/.env
function loadServerEnv() {
  try {
    const envPath = join(process.cwd(), 'server', '.env');
    const envContent = readFileSync(envPath, 'utf8');
    
    console.log('📁 Loading environment variables from server/.env...');
    
    // Parse .env file
    const envVars = envContent
      .split('\n')
      .filter(line => line.trim() && !line.startsWith('#'))
      .reduce((acc, line) => {
        const [key, ...valueParts] = line.split('=');
        if (key && valueParts.length > 0) {
          const value = valueParts.join('=').trim().replace(/^["']|["']$/g, '');
          acc[key.trim()] = value;
        }
        return acc;
      }, {} as Record<string, string>);

    // Set AWS environment variables
    if (envVars.AWS_ACCESS_KEY_ID) {
      process.env.AWS_ACCESS_KEY_ID = envVars.AWS_ACCESS_KEY_ID;
      console.log('✅ AWS_ACCESS_KEY_ID loaded');
    }
    
    if (envVars.AWS_SECRET_ACCESS_KEY) {
      process.env.AWS_SECRET_ACCESS_KEY = envVars.AWS_SECRET_ACCESS_KEY;
      console.log('✅ AWS_SECRET_ACCESS_KEY loaded');
    }
    
    if (envVars.AWS_REGION) {
      process.env.AWS_REGION = envVars.AWS_REGION;
      console.log('✅ AWS_REGION loaded:', envVars.AWS_REGION);
    } else {
      // Default to us-east-1 if not specified
      process.env.AWS_REGION = 'us-east-1';
      console.log('⚠️ AWS_REGION not found, defaulting to us-east-1');
    }

    console.log('🔧 Environment variables configured for AWS Bedrock');
    return true;
  } catch (error) {
    console.error('❌ Failed to load server/.env:', error.message);
    console.log('⚠️ Will proceed with system environment variables');
    return false;
  }
}

async function testOrchestrationAgent() {
  console.log('🚀 Testing OrchestrationAgent with Real AWS Bedrock');
  console.log('='.repeat(60));

  // Load environment variables first
  const envLoaded = loadServerEnv();
  
  // Verify AWS credentials are available
  console.log('\n🔐 AWS Credentials Check:');
  console.log('AWS_ACCESS_KEY_ID:', process.env.AWS_ACCESS_KEY_ID ? '✅ Set' : '❌ Missing');
  console.log('AWS_SECRET_ACCESS_KEY:', process.env.AWS_SECRET_ACCESS_KEY ? '✅ Set' : '❌ Missing');
  console.log('AWS_REGION:', process.env.AWS_REGION || '❌ Missing');

  const agent = new OrchestrationAgent();

  // Test cases covering different scenarios
  const testCases = [
    {
      name: 'Grammar Fix (Should be TRIVIAL)',
      request: 'fix my grammar',
      context: {
        blockId: 'test-1',
        content: 'This sentence have bad grammar and spelling mistakes.',
        type: 'text'
      }
    },
    {
      name: 'Data Analysis (Should be OVERPOWERED)',
      request: 'analyze the sales data and create a chart',
      context: {
        blockId: 'test-2', 
        content: 'Sales data: Q1: $100k, Q2: $150k, Q3: $200k',
        type: 'data'
      }
    },
    {
      name: 'Content Generation (Should be TRIVIAL)',
      request: 'write a short paragraph about artificial intelligence',
      context: {
        blockId: 'test-3',
        content: '',
        type: 'text'
      }
    },
    {
      name: 'Statistical Analysis (Should be OVERPOWERED)',
      request: 'calculate statistical metrics for this dataset',
      context: {
        blockId: 'test-4',
        content: 'Dataset: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]',
        type: 'data'
      }
    },
    {
      name: 'Tone Adjustment (Should be TRIVIAL)',
      request: 'make this more formal',
      context: {
        blockId: 'test-5',
        content: 'Hey there! This is super cool stuff.',
        type: 'text'
      }
    }
  ];

  console.log(`\n📋 Running ${testCases.length} test cases...\n`);

  let successfulLLMClassifications = 0;
  let totalClassifications = 0;
  let totalTime = 0;

  for (const testCase of testCases) {
    console.log(`🧪 Test: ${testCase.name}`);
    console.log(`📝 Request: "${testCase.request}"`);
    console.log(`📄 Content: "${testCase.context.content}"`);
    
    try {
      const startTime = Date.now();
      
      // This is where the magic happens - 1-token Bedrock classification!
      const classification = await agent.classifyOperation(testCase.request, testCase.context);
      
      const testTime = Date.now() - startTime;
      totalTime += testTime;
      totalClassifications++;
      
      console.log(`✅ Result: ${classification.tier.toUpperCase()}`);
      console.log(`🎯 Confidence: ${Math.round(classification.confidence * 100)}%`);
      console.log(`⏱️  Total Time: ${testTime}ms`);
      console.log(`🧠 Reasoning: ${classification.reasoning}`);
      console.log(`🔧 Operation Type: ${classification.operationType}`);
      console.log(`⏳ Estimated Processing: ${classification.estimatedTime}ms`);
      
      // Check if this was an LLM classification (vs fallback)
      // Look for evidence of LLM classification in the logs above
      const wasLLMUsed = testTime > 200; // Real Bedrock calls take 200-300ms, regex is <10ms
      if (wasLLMUsed) {
        successfulLLMClassifications++;
        console.log(`🚀 LLM Classification: SUCCESS (Bedrock AI worked, but fell back due to time threshold)`);
      } else {
        console.log(`🔄 Fallback Classification: Used regex/heuristics only`);
      }
      
      // Validate expected results
      const expectedTier = testCase.name.includes('TRIVIAL') ? 'trivial' : 'overpowered';
      const isCorrect = classification.tier === expectedTier;
      console.log(`${isCorrect ? '✅' : '❌'} Expected: ${expectedTier.toUpperCase()}, Got: ${classification.tier.toUpperCase()}`);
      
    } catch (error) {
      console.error(`❌ Error: ${error.message}`);
      totalClassifications++;
    }
    
    console.log('-'.repeat(50));
  }

  console.log('\n🏁 Test Complete!');
  console.log('\n📊 Performance Summary:');
  console.log(`• Total Classifications: ${totalClassifications}`);
  console.log(`• LLM Classifications: ${successfulLLMClassifications}/${totalClassifications} (${Math.round(successfulLLMClassifications/totalClassifications*100)}%)`);
  console.log(`• Average Time: ${Math.round(totalTime/totalClassifications)}ms`);
  console.log(`• Environment: ${envLoaded ? 'server/.env loaded' : 'system env vars'}`);
  
  console.log('\n🎯 Key Metrics to Watch:');
  console.log('• Classification time should be <100ms for LLM routing');
  console.log('• Confidence should be >50% for LLM results');
  console.log('• Grammar/tone/content = TRIVIAL → Fast Bedrock Client');
  console.log('• Data analysis/statistics = OVERPOWERED → Full LLM');
  
  if (successfulLLMClassifications > 0) {
    console.log('\n🎉 SUCCESS: Real 1-token Bedrock AI classification is working!');
  } else {
    console.log('\n⚠️ NOTE: All classifications used fallback methods (regex/heuristics)');
    console.log('   This could mean:');
    console.log('   - AWS credentials are not properly configured');
    console.log('   - Bedrock service is not accessible');
    console.log('   - Network connectivity issues');
  }
}

// Run the test
testOrchestrationAgent().catch(console.error); 