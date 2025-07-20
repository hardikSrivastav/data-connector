import os
import json
import shutil
import hashlib
import aiofiles
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from app.services.template_manager import TemplateManager
from app.services.scenario_manager import ScenarioManager

class WorkspaceManager:
    def __init__(self):
        self.workspaces_dir = Path("workspaces")
        self.workspaces_dir.mkdir(exist_ok=True)
        self.template_manager = TemplateManager()
    
    async def create_workspace(self, session_id: str, template_version: str) -> Dict:
        """Create isolated workspace for a session"""
        workspace_dir = self.workspaces_dir / session_id
        workspace_dir.mkdir(exist_ok=True)
        
        # Get template files
        template_files = self.template_manager.get_template_files(template_version)
        if not template_files:
            raise ValueError(f"Template version {template_version} not found")
        
        # Copy template files to workspace (remove .template extension)
        workspace_files = []
        for template_file in template_files:
            # Remove .template extension
            filename = template_file["path"].replace(".template", "")
            if filename == ".env":
                filename = ".env.example"  # Rename .env to .env.example
            
            workspace_file_path = workspace_dir / filename
            
            # Write file content
            async with aiofiles.open(workspace_file_path, 'w') as f:
                await f.write(template_file["content"])
            
            workspace_files.append({
                "path": filename,
                "content": template_file["content"],
                "hash": template_file["hash"],
                "original_template": template_file["path"]
            })
        
        # Create workspace metadata
        template_info = self.template_manager.get_template_info(template_version)
        metadata = {
            "session_id": session_id,
            "template_version": template_version,
            "template_hash": template_info["hash"],
            "created_at": datetime.utcnow().isoformat(),
            "files": workspace_files,
            "placeholders": self._extract_placeholders(workspace_files),
            "schema": template_info.get("schema")
        }
        
        # Save metadata
        metadata_file = workspace_dir / "metadata.json"
        async with aiofiles.open(metadata_file, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        return metadata
    
    async def create_scenario_workspace(self, session_id: str, scenario_id: str, template_versions: List[str], variables: Dict[str, str] = None) -> Dict:
        """Create workspace for a deployment scenario with multiple templates"""
        workspace_dir = self.workspaces_dir / session_id
        workspace_dir.mkdir(exist_ok=True)
        
        scenario_manager = ScenarioManager()
        scenario = scenario_manager.get_scenario_by_id(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Collect all files from all templates
        all_workspace_files = []
        template_metadata = {}
        shared_variables = variables or {}
        
        for template_version in template_versions:
            # Get template files
            template_files = self.template_manager.get_template_files(template_version)
            if not template_files:
                continue
            
            template_info = self.template_manager.get_template_info(template_version)
            template_metadata[template_version] = {
                "name": template_info["name"],
                "category": template_info.get("category"),
                "format": template_info.get("format"),
                "hash": template_info["hash"]
            }
            
            # Process template files
            for template_file in template_files:
                # Determine output filename based on template format
                filename = self._get_scenario_filename(template_file["path"], template_info)
                workspace_file_path = workspace_dir / filename
                
                # Apply variable substitutions if provided
                content = template_file["content"]
                if shared_variables:
                    content = self._substitute_variables(content, shared_variables)
                
                # Ensure directory exists for nested paths
                workspace_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write file content  
                async with aiofiles.open(workspace_file_path, 'w') as f:
                    await f.write(content)
                
                all_workspace_files.append({
                    "path": filename,
                    "content": content,
                    "hash": hashlib.sha256(content.encode()).hexdigest(),
                    "original_template": template_file["path"],
                    "template_version": template_version,
                    "template_category": template_info.get("category"),
                    "template_format": template_info.get("format")
                })
        
        # Create scenario workspace metadata
        metadata = {
            "session_id": session_id,
            "scenario_id": scenario_id,
            "scenario_name": scenario["name"],
            "scenario_category": scenario["category"],
            "template_versions": template_versions,
            "template_metadata": template_metadata,
            "created_at": datetime.utcnow().isoformat(),
            "files": all_workspace_files,
            "placeholders": self._extract_placeholders(all_workspace_files),
            "shared_variables": shared_variables,
            "dependencies": scenario.get("dependencies", {}),
            "variable_mappings": scenario.get("variable_mappings", {})
        }
        
        # Save metadata
        metadata_file = workspace_dir / "metadata.json"
        async with aiofiles.open(metadata_file, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        return metadata
    
    def _get_scenario_filename(self, template_path: str, template_info: Dict) -> str:
        """Generate appropriate filename for scenario files based on template format"""
        # Remove .template extension
        filename = template_path.replace(".template", "")
        
        # Handle special cases based on template category and format
        category = template_info.get("category")
        format_type = template_info.get("format")
        
        if category == "deployment" and format_type == "docker-compose":
            if "enterprise" in template_info.get("name", "").lower():
                return "docker-compose-enterprise.yml"
            else:
                return "docker-compose.yml"
        elif category == "infrastructure" and format_type == "nginx":
            return "nginx/nginx.conf"
        elif category == "authentication" and format_type == "yaml":
            return "auth-config.yaml"
        elif category == "configuration" and format_type == "yaml":
            return "config.yaml"
        
        # Default: use filename as-is
        return filename
    
    def _substitute_variables(self, content: str, variables: Dict[str, str]) -> str:
        """Substitute {{ VARIABLE }} patterns with actual values"""
        import re
        
        def replace_var(match):
            var_name = match.group(1).strip()
            return variables.get(var_name, match.group(0))  # Return original if not found
        
        return re.sub(r'{{\s*([^}]+)\s*}}', replace_var, content)
    
    def _extract_placeholders(self, files: List[Dict]) -> List[str]:
        """Extract all {{PLACEHOLDER}} patterns from files"""
        import re
        placeholders = set()
        
        for file in files:
            content = file["content"]
            matches = re.findall(r'{{([^}]+)}}', content)
            placeholders.update(matches)
        
        return sorted(list(placeholders))
    
    async def get_workspace_files(self, session_id: str) -> Dict:
        """Get current workspace files and metadata"""
        workspace_dir = self.workspaces_dir / session_id
        
        if not workspace_dir.exists():
            raise ValueError(f"Workspace {session_id} not found")
        
        # Load metadata
        metadata_file = workspace_dir / "metadata.json"
        async with aiofiles.open(metadata_file, 'r') as f:
            metadata = json.loads(await f.read())
        
        # Get current file contents
        current_files = []
        for file_info in metadata["files"]:
            file_path = workspace_dir / file_info["path"]
            if file_path.exists():
                async with aiofiles.open(file_path, 'r') as f:
                    current_content = await f.read()
                
                current_files.append({
                    "path": file_info["path"],
                    "content": current_content,
                    "hash": hashlib.sha256(current_content.encode()).hexdigest(),
                    "original_template": file_info["original_template"],
                    "modified": current_content != file_info["content"]
                })
        
        return {
            "session_id": session_id,
            "files": current_files,
            "metadata": metadata
        }
    
    async def read_file(self, session_id: str, file_path: str) -> Optional[str]:
        """Read file content from workspace"""
        workspace_dir = self.workspaces_dir / session_id
        full_path = workspace_dir / file_path
        
        if not full_path.exists() or not self._is_safe_path(workspace_dir, full_path):
            return None
        
        async with aiofiles.open(full_path, 'r') as f:
            return await f.read()
    
    async def write_file(self, session_id: str, file_path: str, content: str) -> bool:
        """Write file content to workspace"""
        workspace_dir = self.workspaces_dir / session_id
        full_path = workspace_dir / file_path
        
        if not self._is_safe_path(workspace_dir, full_path):
            return False
        
        try:
            async with aiofiles.open(full_path, 'w') as f:
                await f.write(content)
            return True
        except Exception:
            return False
    
    async def edit_file(self, session_id: str, file_path: str, old_string: str, new_string: str) -> bool:
        """Edit file by replacing old_string with new_string"""
        current_content = await self.read_file(session_id, file_path)
        if current_content is None:
            return False
        
        if old_string not in current_content:
            return False
        
        new_content = current_content.replace(old_string, new_string)
        return await self.write_file(session_id, file_path, new_content)
    
    async def multi_edit_file(self, session_id: str, file_path: str, edits: List[Dict]) -> bool:
        """Apply multiple edits to a file"""
        current_content = await self.read_file(session_id, file_path)
        if current_content is None:
            return False
        
        new_content = current_content
        for edit in edits:
            old_string = edit["old_string"]
            new_string = edit["new_string"]
            replace_all = edit.get("replace_all", False)
            
            if old_string not in new_content:
                return False
            
            if replace_all:
                new_content = new_content.replace(old_string, new_string)
            else:
                new_content = new_content.replace(old_string, new_string, 1)
        
        return await self.write_file(session_id, file_path, new_content)
    
    def _is_safe_path(self, workspace_dir: Path, file_path: Path) -> bool:
        """Check if file path is within workspace directory"""
        try:
            file_path.resolve().relative_to(workspace_dir.resolve())
            return True
        except ValueError:
            return False
    
    async def list_files(self, session_id: str) -> List[str]:
        """List all files in workspace"""
        workspace_dir = self.workspaces_dir / session_id
        
        if not workspace_dir.exists():
            return []
        
        files = []
        for file_path in workspace_dir.rglob("*"):
            if file_path.is_file() and file_path.name != "metadata.json":
                relative_path = file_path.relative_to(workspace_dir)
                files.append(str(relative_path))
        
        return sorted(files)
    
    async def validate_workspace(self, session_id: str) -> Dict:
        """Validate workspace files against template schema or scenario dependencies"""
        workspace_data = await self.get_workspace_files(session_id)
        metadata = workspace_data["metadata"]
        
        errors = []
        warnings = []
        
        # Check for unfilled placeholders
        for file in workspace_data["files"]:
            import re
            remaining_placeholders = re.findall(r'{{([^}]+)}}', file["content"])
            if remaining_placeholders:
                errors.append(f"Unfilled placeholders in {file['path']}: {', '.join(remaining_placeholders)}")
        
        # For scenario-based workspaces, validate dependencies
        if "scenario_id" in metadata:
            scenario_errors = self._validate_scenario_dependencies(workspace_data)
            errors.extend(scenario_errors)
        
        # Calculate similarity score
        similarity_score = self._calculate_similarity_score(workspace_data["files"], metadata["files"])
        
        if similarity_score < 0.7:
            warnings.append(f"Files have significantly deviated from template (similarity: {similarity_score:.2%})")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "similarity_score": similarity_score
        }
    
    def _validate_scenario_dependencies(self, workspace_data: Dict) -> List[str]:
        """Validate cross-file dependencies for scenario-based workspaces"""
        errors = []
        metadata = workspace_data["metadata"]
        dependencies = metadata.get("dependencies", {})
        files = workspace_data["files"]
        
        # Check cross-file variable consistency
        cross_file_vars = dependencies.get("cross_file_variables", {})
        for var_name, expected_templates in cross_file_vars.items():
            values_found = set()
            files_with_var = []
            
            for file in files:
                import re
                # Look for the variable in the file content
                var_pattern = f'{var_name}:\s*([^\n]+)' # YAML format
                matches = re.findall(var_pattern, file["content"])
                if matches:
                    values_found.update(matches)
                    files_with_var.append(file["path"])
            
            # Check if all files that should have this variable actually have it
            if len(values_found) > 1:
                errors.append(f"Inconsistent values for {var_name} across files: {list(values_found)}")
        
        return errors
    
    def _calculate_similarity_score(self, current_files: List[Dict], original_files: List[Dict]) -> float:
        """Calculate similarity score between current and original files"""
        if not current_files or not original_files:
            return 0.0
        
        total_score = 0.0
        file_count = 0
        
        for current_file in current_files:
            original_file = next((f for f in original_files if f["path"] == current_file["path"]), None)
            if original_file:
                # Simple similarity based on character differences
                current_content = current_file["content"]
                original_content = original_file["content"]
                
                if len(original_content) == 0:
                    similarity = 1.0 if len(current_content) == 0 else 0.0
                else:
                    # Calculate edit distance ratio
                    import difflib
                    similarity = difflib.SequenceMatcher(None, original_content, current_content).ratio()
                
                total_score += similarity
                file_count += 1
        
        return total_score / file_count if file_count > 0 else 0.0
    
    async def cleanup_workspace(self, session_id: str) -> bool:
        """Clean up workspace directory"""
        workspace_dir = self.workspaces_dir / session_id
        
        if workspace_dir.exists():
            try:
                shutil.rmtree(workspace_dir)
                return True
            except Exception:
                return False
        
        return True
    
    async def export_workspace(self, session_id: str) -> Optional[Dict]:
        """Export workspace as downloadable files"""
        workspace_data = await self.get_workspace_files(session_id)
        
        if not workspace_data:
            return None
        
        return {
            "session_id": session_id,
            "export_date": datetime.utcnow().isoformat(),
            "files": workspace_data["files"],
            "metadata": workspace_data["metadata"]
        }