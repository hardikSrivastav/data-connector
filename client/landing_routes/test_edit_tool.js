const { EditFileTool, IntrospectFileTool } = require('./src/services/langgraphTools');

async function testEditFileTool() {
  console.log('🧪 Testing EditFileTool...');
  
  try {
    // Initialize tools
    const editTool = new EditFileTool();
    const introspectTool = new IntrospectFileTool();
    
    // Step 1: Introspect the file before edit
    console.log('\n📋 Step 1: Reading current file...');
    const beforeContent = await introspectTool._call('{"filePath": "config.yaml"}');
    console.log('Current file content (first 200 chars):', beforeContent.substring(0, 200));
    
    // Step 2: Make a safe edit - change a comment
    console.log('\n✏️ Step 2: Making safe edit...');
    const editResult = await editTool._call(JSON.stringify({
      filePath: "config.yaml",
      replacements: {
        "# Main configuration for connecting to existing databases": "# Main configuration for connecting to existing databases - EDITED"
      },
      backup: true
    }));
    
    console.log('Edit result:', editResult);
    
    // Step 3: Verify the change
    console.log('\n🔍 Step 3: Verifying changes...');
    const afterContent = await introspectTool._call('{"filePath": "config.yaml"}');
    console.log('Updated file content (first 200 chars):', afterContent.substring(0, 200));
    
    // Step 4: Check if the edit was successful
    const wasEdited = afterContent.includes('- EDITED');
    console.log('\n✅ Edit successful:', wasEdited);
    
    // Step 5: Restore from backup
    console.log('\n🔄 Step 5: Restoring from backup...');
    const restoreResult = await editTool._call(JSON.stringify({
      filePath: "config.yaml",
      replacements: {
        "# Main configuration for connecting to existing databases - EDITED": "# Main configuration for connecting to existing databases"
      },
      backup: false
    }));
    
    console.log('Restore result:', restoreResult);
    
    // Step 6: Final verification
    console.log('\n🏁 Step 6: Final verification...');
    const finalContent = await introspectTool._call('{"filePath": "config.yaml"}');
    const wasRestored = !finalContent.includes('- EDITED');
    console.log('Successfully restored:', wasRestored);
    
    console.log('\n🎉 Test completed successfully!');
    
    return {
      success: true,
      editWorked: wasEdited,
      restoreWorked: wasRestored,
      summary: `Edit tool test: ${wasEdited ? 'PASS' : 'FAIL'}, Restore: ${wasRestored ? 'PASS' : 'FAIL'}`
    };
    
  } catch (error) {
    console.error('❌ Test failed:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Run the test
if (require.main === module) {
  testEditFileTool().then(result => {
    console.log('\n📊 Final Result:', result);
    process.exit(result.success ? 0 : 1);
  });
}

module.exports = testEditFileTool; 