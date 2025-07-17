#!/usr/bin/env python3
"""
Test Steps 3 & 4: Configuration and AWS Bedrock Client
"""

import sys
import os
import logging
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_step_3_configuration():
    """Test Step 3: Configuration"""
    try:
        logger.info("🔧 Step 3: Testing Configuration...")
        
        # Test main config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        assert 'langgraph' in config, "LangGraph config missing"
        
        lg_config = config['langgraph']
        assert lg_config['enabled'] == True, "LangGraph not enabled"
        assert lg_config['complexity_threshold'] == 5, "Wrong complexity threshold"
        
        logger.info("✅ Configuration test passed")
        logger.info(f"   - Enabled: {lg_config['enabled']}")
        logger.info(f"   - Threshold: {lg_config['complexity_threshold']}")
        logger.info(f"   - Primary LLM: {lg_config['llm']['primary_provider']}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False

def test_step_4_files():
    """Test Step 4: Files exist"""
    try:
        logger.info("🤖 Step 4: Testing Bedrock Client Files...")
        
        required_files = [
            'server/agent/langgraph/graphs/bedrock_client.py',
            'server/agent/langgraph/compat.py',
            'server/agent/langgraph/integration.py'
        ]
        
        for file_path in required_files:
            assert os.path.exists(file_path), f"Missing: {file_path}"
            logger.info(f"   ✅ {file_path}")
        
        # Test basic import
        sys.path.insert(0, 'server')
        from server.agent.langgraph.compat import create_graph_state
        
        state = create_graph_state("Test")
        assert state.question == "Test"
        
        logger.info("✅ Bedrock client files test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Files test failed: {e}")
        return False

def main():
    logger.info("🚀 Testing Steps 3 & 4")
    logger.info("=" * 50)
    
    test1 = test_step_3_configuration()
    test2 = test_step_4_files()
    
    if test1 and test2:
        logger.info("\n🎉 STEPS 3 & 4 TESTS PASSED!")
        logger.info("✅ Configuration is set up correctly")
        logger.info("✅ Bedrock client and integration files exist")
        logger.info("✅ Basic functionality verified")
        return True
    else:
        logger.error("\n❌ SOME TESTS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
