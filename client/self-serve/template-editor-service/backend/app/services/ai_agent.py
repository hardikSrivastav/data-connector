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
        return """You are an AI Deployment Configuration Agent. Your role is to transform deployment templates into production-ready configurations through intelligent analysis and cross-file coordination.

CORE MISSION: Transform deployment scenarios into production-ready configurations with cross-file consistency

IMMEDIATE ACTIONS REQUIRED:
1. ALWAYS start by using get_session_context to understand if this is a scenario-based session
2. Use list_files to see all available workspace files
3. Read existing files to understand current configuration and dependencies
4. Use analyze_cross_file_dependencies to understand relationships between files
5. Provide coordinated recommendations across all related files

SCENARIO AWARENESS:
- Detect if this is a multi-template deployment scenario or single template session
- For scenarios: coordinate changes across ALL related files (auth, infrastructure, deployment)
- For single templates: focus on individual file customization
- Always consider cross-file variable dependencies and consistency

CROSS-FILE COORDINATION:
- Use analyze_cross_file_dependencies to understand file relationships
- When making changes, consider impact on related files
- Use apply_cross_file_changes for coordinated updates across multiple files
- Ensure shared variables (like DOMAIN_NAME, DATABASE_URL) are consistent
- Validate that authentication flows work across auth configs and nginx
- Check that Docker services match database configurations

ANALYSIS PHASE:
- Use get_session_context to understand deployment scenario
- Use list_files to see all available workspace files
- Use read_file to examine each configuration file
- Use analyze_cross_file_dependencies to map relationships
- Identify shared variables, integration points, and dependencies

INFORMATION GATHERING:
- Ask targeted questions based on actual file analysis and scenario context
- Provide smart defaults that work across the entire deployment
- Explain implications of choices on the complete system
- Consider security, scalability, and operational requirements

VALIDATION RULES:
- Never hardcode secrets in any files
- Ensure shared variables are consistent across all files
- Validate integration compatibility (auth → nginx → services)
- Check Docker service dependencies and networking
- Verify SSL/TLS configuration consistency
- Ensure database connections work across services

EDITING CONSTRAINTS:
- Only modify template files provided in workspace
- Preserve existing code structure and comments
- Use available tools for all file operations
- For multi-file changes, use apply_cross_file_changes
- Always verify edits maintain cross-file consistency

AVAILABLE TOOLS (USE THESE IMMEDIATELY):
- get_session_context: Understand deployment scenario and session type
- list_files: List all files in workspace
- read_file: Read file content from workspace
- analyze_cross_file_dependencies: Analyze relationships between files
- write_file: Write content to workspace file
- edit_file: Replace old_string with new_string in file
- multi_edit_file: Apply multiple edits to a file
- apply_cross_file_changes: Apply coordinated changes across multiple files
- validate_workspace: Validate files against template schema

WORKFLOW:
1. Use get_session_context to understand scenario
2. Use list_files to see what's available
3. Use analyze_cross_file_dependencies to understand relationships
4. Read relevant files to understand current state
5. Analyze user requirements considering cross-file impact
6. Use apply_cross_file_changes for coordinated updates
7. Validate changes maintain system consistency

ERROR HANDLING:
- If validation fails, explain issue and provide coordinated fix
- Consider cross-file impact when suggesting corrections
- Never proceed with configurations that break integration

CRITICAL: Always use the tools to examine the workspace and understand cross-file dependencies before making recommendations!
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
            },
            {
                "name": "get_session_context",
                "description": "Get session context to understand deployment scenario and file structure",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "analyze_cross_file_dependencies",
                "description": "Analyze relationships and dependencies between files in the workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "apply_cross_file_changes",
                "description": "Apply coordinated changes across multiple files with shared variables",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "changes": {
                            "type": "object",
                            "description": "Map of file_path to list of edits",
                            "additionalProperties": {
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
                        "description": {
                            "type": "string", 
                            "description": "Description of the coordinated changes"
                        }
                    },
                    "required": ["changes"]
                }
            }
        ]
        
        # Create message with system prompt and conversation history
        messages = self.conversation_history + [
            {"role": "user", "content": message}
        ]
        
        # Call Claude with tools
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
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
                    model="claude-3-5-sonnet-20241022",
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
                        model="claude-3-5-sonnet-20241022",
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
            
            elif tool_name == "get_session_context":
                session_context = await self._get_session_context()
                return {"success": True, "context": session_context}
            
            elif tool_name == "analyze_cross_file_dependencies":
                dependencies = await self._analyze_cross_file_dependencies()
                return {"success": True, "dependencies": dependencies}
            
            elif tool_name == "apply_cross_file_changes":
                success = await self._apply_cross_file_changes(tool_input["changes"], tool_input.get("description", ""))
                return {"success": success}
            
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
    
    async def _get_session_context(self) -> Dict[str, Any]:
        """Get session context to understand deployment scenario and file structure"""
        try:
            # Import here to avoid circular imports
            from app.database.database import get_db, Session as SessionModel, SessionTemplate
            from app.services.scenario_manager import ScenarioManager
            from sqlalchemy.orm import Session as SQLSession
            
            # Get database session
            db_gen = get_db()
            db: SQLSession = next(db_gen)
            
            try:
                # Get session details
                session = db.query(SessionModel).filter(SessionModel.id == self.session_id).first()
                if not session:
                    return {"error": "Session not found"}
                
                context = {
                    "session_id": self.session_id,
                    "user_id": session.user_id,
                    "status": session.status,
                    "created_at": session.created_at.isoformat(),
                    "session_type": "scenario" if session.template_version.startswith("scenario:") else "individual_template"
                }
                
                if session.template_version.startswith("scenario:"):
                    # This is a scenario-based session
                    scenario_id = session.template_version.replace("scenario:", "")
                    scenario_manager = ScenarioManager()
                    scenario = scenario_manager.get_scenario_by_id(scenario_id)
                    session_templates = db.query(SessionTemplate).filter(SessionTemplate.session_id == self.session_id).all()
                    
                    context.update({
                        "scenario_id": scenario_id,
                        "scenario_name": scenario["name"] if scenario else "Unknown",
                        "scenario_category": scenario["category"] if scenario else "Unknown", 
                        "scenario_description": scenario["description"] if scenario else "",
                        "template_count": len(session_templates),
                        "template_versions": [st.template_version for st in session_templates],
                        "shared_variables": scenario["variable_mappings"].get("shared_variables", []) if scenario else [],
                        "cross_file_variables": scenario["dependencies"].get("cross_file_variables", {}) if scenario else {}
                    })
                else:
                    # This is an individual template session
                    context.update({
                        "template_version": session.template_version,
                        "template_hash": session.template_hash
                    })
                
                # Add workspace file information
                workspace_data = await self.workspace_manager.get_workspace_files(self.session_id)
                context["files"] = [{"path": f["path"], "category": self._categorize_file(f["path"])} for f in workspace_data["files"]]
                
                return context
                
            finally:
                db.close()
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _analyze_cross_file_dependencies(self) -> Dict[str, Any]:
        """Analyze relationships and dependencies between files in the workspace"""
        try:
            workspace_data = await self.workspace_manager.get_workspace_files(self.session_id)
            session_context = await self._get_session_context()
            
            dependencies = {
                "shared_variables": {},
                "file_relationships": {},
                "variable_usage": {},
                "integration_points": []
            }
            
            # Extract variables from each file
            import re
            variable_pattern = r'{{([^}]+)}}'
            
            for file in workspace_data["files"]:
                file_path = file["path"]
                file_content = file["content"]
                
                # Find all variables in this file
                variables = re.findall(variable_pattern, file_content)
                dependencies["variable_usage"][file_path] = list(set(variables))
                
                # Categorize file and identify relationships
                file_category = self._categorize_file(file_path)
                dependencies["file_relationships"][file_path] = {
                    "category": file_category,
                    "depends_on": [],
                    "depended_by": []
                }
                
                # Identify specific integration points
                if "nginx" in file_path.lower():
                    dependencies["integration_points"].append({
                        "type": "reverse_proxy",
                        "file": file_path,
                        "description": "NGINX reverse proxy configuration"
                    })
                elif "docker-compose" in file_path.lower():
                    dependencies["integration_points"].append({
                        "type": "container_orchestration",
                        "file": file_path,
                        "description": "Docker container definitions and networking"
                    })
                elif "auth" in file_path.lower():
                    dependencies["integration_points"].append({
                        "type": "authentication",
                        "file": file_path,
                        "description": "Authentication and authorization configuration"
                    })
            
            # Find shared variables across files
            all_variables = {}
            for file_path, variables in dependencies["variable_usage"].items():
                for var in variables:
                    if var not in all_variables:
                        all_variables[var] = []
                    all_variables[var].append(file_path)
            
            # Identify truly shared variables (used in multiple files)
            dependencies["shared_variables"] = {var: files for var, files in all_variables.items() if len(files) > 1}
            
            # Add scenario-specific shared variables if available
            if session_context.get("shared_variables"):
                for var in session_context["shared_variables"]:
                    if var not in dependencies["shared_variables"]:
                        dependencies["shared_variables"][var] = []
            
            return dependencies
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _apply_cross_file_changes(self, changes: Dict[str, List[Dict]], description: str = "") -> bool:
        """Apply coordinated changes across multiple files with shared variables"""
        try:
            print(f"Applying cross-file changes: {description}")
            
            # Apply changes to each file
            for file_path, edits in changes.items():
                print(f"Applying {len(edits)} edits to {file_path}")
                
                success = await self.workspace_manager.multi_edit_file(
                    self.session_id,
                    file_path,
                    edits
                )
                
                if not success:
                    print(f"Failed to apply edits to {file_path}")
                    return False
            
            # Validate workspace after changes
            validation_result = await self.workspace_manager.validate_workspace(self.session_id)
            if not validation_result.get("valid", True):
                print(f"Workspace validation failed: {validation_result}")
                # Note: We don't rollback here, but we report the validation issue
            
            return True
            
        except Exception as e:
            print(f"Error applying cross-file changes: {e}")
            return False
    
    def _categorize_file(self, file_path: str) -> str:
        """Categorize a file based on its path and content"""
        file_path_lower = file_path.lower()
        
        if "docker-compose" in file_path_lower or "compose" in file_path_lower:
            return "deployment"
        elif "nginx" in file_path_lower:
            return "infrastructure"
        elif "auth" in file_path_lower:
            return "authentication"
        elif "config" in file_path_lower:
            return "configuration"
        elif file_path_lower.endswith(('.yaml', '.yml')):
            return "configuration"
        elif file_path_lower.endswith('.conf'):
            return "infrastructure"
        else:
            return "other"