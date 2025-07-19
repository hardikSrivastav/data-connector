import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import anthropic
from anthropic.types import MessageParam

from app.services.workspace_manager import WorkspaceManager
from app.services.template_manager import TemplateManager

class AIAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.workspace_manager = WorkspaceManager()
        self.template_manager = TemplateManager()
        
        # Initialize Anthropic client with error handling
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            print(f"Failed to initialize Anthropic client: {e}")
            raise
        
        self.conversation_history: List[MessageParam] = []
        
        # Initialize system prompt
        self.system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        return """You are an Auth File Editor Agent. Your role is to transform generic authentication templates into production-ready files through intelligent analysis and guided customization.

CORE MISSION: Transform generic auth templates into production-ready files

IMMEDIATE ACTIONS REQUIRED:
1. ALWAYS start by using list_files to see available workspace files
2. ALWAYS read the existing files to understand current configuration
3. THEN provide recommendations based on what you find

ANALYSIS PHASE:
- Use list_files to see all available workspace files
- Use read_file to examine each authentication template
- Identify auth patterns, placeholders, and dependencies
- Understand the current template structure

INFORMATION GATHERING:
- Ask targeted questions based on actual file analysis
- Provide smart defaults when possible
- Explain implications of choices based on what you see in the files

VALIDATION RULES:
- Never hardcode secrets in files
- Ensure all placeholders are filled appropriately
- Validate syntax and security practices
- Check integration compatibility

EDITING CONSTRAINTS:
- Only modify template files provided in workspace
- Preserve existing code structure and comments
- Use available tools for all file operations
- Verify all edits before completion

AVAILABLE TOOLS (USE THESE IMMEDIATELY):
- list_files: List all files in workspace (START WITH THIS)
- read_file: Read file content from workspace
- write_file: Write content to workspace file
- edit_file: Replace old_string with new_string in file
- multi_edit_file: Apply multiple edits to a file
- validate_workspace: Validate files against template schema

WORKFLOW:
1. Use list_files to see what's available
2. Use read_file to examine auth configuration files
3. Analyze user requirements (e.g., "Okta auth")
4. Use edit_file or write_file to customize templates
5. Validate changes and explain what was done

ERROR HANDLING:
- If validation fails, explain issue and ask for correction
- Provide specific guidance on fixes needed
- Never proceed with invalid configurations

CRITICAL: Always use the tools to examine the workspace before making recommendations!
"""
    
    async def process_message(self, message: str) -> str:
        """Process user message and return AI response"""
        try:
            # Check if client is available
            if not hasattr(self, 'client') or self.client is None:
                return "AI Assistant is currently unavailable. Please check the API key configuration."
            
            print(f"Processing message for session {self.session_id}: {message}")
            
            # Add user message to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            
            # Get AI response with tool calling
            response = await self._call_claude_with_tools(message)
            
            # Add assistant response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            print(f"AI response: {response[:200]}...")
            return response
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            print(f"AI Agent Error: {error_msg}")
            return f"Sorry, I encountered an error: {error_msg}"
    
    async def _call_claude_with_tools(self, message: str) -> str:
        """Call Claude with function calling capabilities"""
        
        # Define available tools
        tools = [
            {
                "name": "read_file",
                "description": "Read file content from the workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file to read"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write content to a workspace file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file to write"},
                        "content": {"type": "string", "description": "Content to write to the file"}
                    },
                    "required": ["file_path", "content"]
                }
            },
            {
                "name": "edit_file",
                "description": "Replace old_string with new_string in a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file to edit"},
                        "old_string": {"type": "string", "description": "String to replace"},
                        "new_string": {"type": "string", "description": "String to replace with"}
                    },
                    "required": ["file_path", "old_string", "new_string"]
                }
            },
            {
                "name": "multi_edit_file",
                "description": "Apply multiple edits to a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file to edit"},
                        "edits": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "old_string": {"type": "string"},
                                    "new_string": {"type": "string"},
                                    "replace_all": {"type": "boolean", "default": False}
                                },
                                "required": ["old_string", "new_string"]
                            }
                        }
                    },
                    "required": ["file_path", "edits"]
                }
            },
            {
                "name": "list_files",
                "description": "List all files in the workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "validate_workspace",
                "description": "Validate workspace files against template schema",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
        
        # Create message with system prompt and conversation history
        messages = self.conversation_history + [
            {"role": "user", "content": message}
        ]
        
        # Call Claude with tools
        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4000,
            system=self.system_prompt,
            messages=messages,
            tools=tools
        )
        
        response_text = ""
        
        # Process response and handle tool calls
        tool_results = []
        for content in response.content:
            if content.type == "text":
                response_text += content.text
            elif content.type == "tool_use":
                # Execute tool and get result
                print(f"Executing tool: {content.name} with input: {content.input}")
                tool_result = await self._execute_tool(content.name, content.input)
                print(f"Tool result: {tool_result}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content.id,
                    "content": json.dumps(tool_result)
                })
        
        # If there were tool calls, get a follow-up response
        if tool_results:
            print(f"Making follow-up API call with {len(tool_results)} tool results")
            try:
                tool_response = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    system=self.system_prompt,
                    messages=messages + [
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results}
                    ],
                    tools=tools
                )
                
                print(f"Follow-up response received with {len(tool_response.content)} content blocks")
                
                # Handle nested tool calls in follow-up response
                follow_up_tool_results = []
                for i, follow_up_content in enumerate(tool_response.content):
                    print(f"Content block {i}: type={follow_up_content.type}")
                    if follow_up_content.type == "text":
                        print(f"Adding follow-up text: {follow_up_content.text[:100]}...")
                        response_text += follow_up_content.text
                    elif follow_up_content.type == "tool_use":
                        print(f"Follow-up tool call: {follow_up_content.name} with input: {follow_up_content.input}")
                        # Execute the nested tool call
                        nested_tool_result = await self._execute_tool(follow_up_content.name, follow_up_content.input)
                        print(f"Nested tool result: {nested_tool_result}")
                        follow_up_tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": follow_up_content.id,
                            "content": json.dumps(nested_tool_result)
                        })
                
                # If there were nested tool calls, handle them recursively
                if follow_up_tool_results:
                    print(f"Processing {len(follow_up_tool_results)} nested tool results")
                    # Add the tool results to conversation and continue
                    updated_messages = messages + [
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results},
                        {"role": "assistant", "content": tool_response.content},
                        {"role": "user", "content": follow_up_tool_results}
                    ]
                    
                    final_response = self.client.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=4000,
                        system=self.system_prompt,
                        messages=updated_messages,
                        tools=tools
                    )
                    
                    # Process final response (including any final tool calls)
                    final_tool_results = []
                    for final_content in final_response.content:
                        if final_content.type == "text":
                            print(f"Adding final text: {final_content.text[:100]}...")
                            response_text += final_content.text
                        elif final_content.type == "tool_use":
                            print(f"Executing final tool: {final_content.name} with input: {final_content.input}")
                            # Execute the final tool call (like edit_file or write_file)
                            final_tool_result = await self._execute_tool(final_content.name, final_content.input)
                            print(f"Final tool result: {final_tool_result}")
                            
                            # Add success message to response
                            if final_tool_result.get('success'):
                                response_text += f"\n\n✅ Successfully executed {final_content.name}"
                            else:
                                response_text += f"\n\n❌ Failed to execute {final_content.name}: {final_tool_result.get('error', 'Unknown error')}"
                        
            except Exception as e:
                print(f"Error in follow-up API call: {e}")
                response_text += f"\n\n[Tool execution completed but follow-up response failed: {str(e)}]"
        
        return response_text
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result"""
        try:
            if tool_name == "read_file":
                content = await self.workspace_manager.read_file(self.session_id, tool_input["file_path"])
                return {"success": True, "content": content}
            
            elif tool_name == "write_file":
                success = await self.workspace_manager.write_file(
                    self.session_id, 
                    tool_input["file_path"], 
                    tool_input["content"]
                )
                return {"success": success}
            
            elif tool_name == "edit_file":
                success = await self.workspace_manager.edit_file(
                    self.session_id,
                    tool_input["file_path"],
                    tool_input["old_string"],
                    tool_input["new_string"]
                )
                return {"success": success}
            
            elif tool_name == "multi_edit_file":
                success = await self.workspace_manager.multi_edit_file(
                    self.session_id,
                    tool_input["file_path"],
                    tool_input["edits"]
                )
                return {"success": success}
            
            elif tool_name == "list_files":
                files = await self.workspace_manager.list_files(self.session_id)
                return {"success": True, "files": files}
            
            elif tool_name == "validate_workspace":
                validation_result = await self.workspace_manager.validate_workspace(self.session_id)
                return {"success": True, "validation": validation_result}
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def analyze_workspace(self) -> Dict[str, Any]:
        """Analyze workspace and provide initial recommendations"""
        try:
            # Get workspace files
            workspace_data = await self.workspace_manager.get_workspace_files(self.session_id)
            
            # Get template info
            template_version = workspace_data["metadata"]["template_version"]
            template_info = self.template_manager.get_template_info(template_version)
            
            # Extract placeholders that need filling
            placeholders = workspace_data["metadata"]["placeholders"]
            
            # Analyze current state
            analysis = {
                "template_version": template_version,
                "template_name": template_info["name"],
                "files": [f["path"] for f in workspace_data["files"]],
                "placeholders": placeholders,
                "unfilled_placeholders": [],
                "recommendations": []
            }
            
            # Check for unfilled placeholders
            for file in workspace_data["files"]:
                import re
                remaining_placeholders = re.findall(r'{{([^}]+)}}', file["content"])
                analysis["unfilled_placeholders"].extend(remaining_placeholders)
            
            # Generate recommendations
            analysis["recommendations"] = self._generate_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on workspace analysis"""
        recommendations = []
        
        placeholders = analysis["unfilled_placeholders"]
        
        if "AUTH_METHOD" in placeholders:
            recommendations.append("Choose authentication method: JWT, OAuth, or local authentication")
        
        if "SECRET_KEY" in placeholders:
            recommendations.append("Generate a secure secret key for JWT signing")
        
        if "OAUTH_PROVIDERS" in placeholders:
            recommendations.append("Select OAuth providers (Google, GitHub, Auth0, etc.)")
        
        if "DATABASE_URL" in placeholders:
            recommendations.append("Configure database connection string")
        
        if not recommendations:
            recommendations.append("All placeholders are filled. Ready for validation and export.")
        
        return recommendations