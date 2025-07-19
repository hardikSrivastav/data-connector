import os
import json
import shutil
import hashlib
import aiofiles
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from app.services.template_manager import TemplateManager

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
        """Validate workspace files against template schema"""
        workspace_data = await self.get_workspace_files(session_id)
        metadata = workspace_data["metadata"]
        schema = metadata.get("schema")
        
        if not schema:
            return {"valid": True, "errors": [], "warnings": []}
        
        errors = []
        warnings = []
        
        # Check for unfilled placeholders
        for file in workspace_data["files"]:
            import re
            remaining_placeholders = re.findall(r'{{([^}]+)}}', file["content"])
            if remaining_placeholders:
                errors.append(f"Unfilled placeholders in {file['path']}: {', '.join(remaining_placeholders)}")
        
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