"""
context_builder.py - Build context for AI without WebSockets
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

class ContextBuilder:
    def __init__(self, cwd: str):
        """Initialize with a working directory"""
        self.cwd = Path(cwd)
    
    def get_file_tree(self, max_files: int = 5000000) -> str:
        """Get a tree of files in the working directory (recursive)"""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.cwd):
                # Skip common directories (modifying dirs in-place affects os.walk)
                dirs[:] = [d for d in dirs if d not in [
                    'node_modules', '.git', '__pycache__', 
                    'venv', '.venv', 'dist', 'build', '.pytest_cache',
                    '__pycache__', '.mypy_cache', '.tox', 'node_modules'
                ]]
                
                for filename in filenames:
                    # Skip hidden files
                    if filename.startswith('.'):
                        continue
                    
                    file_path = Path(root) / filename
                    rel_path = file_path.relative_to(self.cwd)
                    files.append(str(rel_path))
                    print("directory", self.cwd)
                    
                    if len(files) >= max_files:
                        break
                
                if len(files) >= max_files:
                    break
            
            if not files:
                return "(No files found)"
            
            result = "\n".join(files[:max_files])
            if len(files) > max_files:
                result += f"\n... and {len(files) - max_files} more files"
            
            return result
        except Exception as e:
            return f"Error listing files: {str(e)}"
    
    def get_current_time(self) -> str:
        """Get current time with timezone"""
        now = datetime.now()
        return now.strftime("%d/%m/%Y, %I:%M:%S %p")
    
    def get_directory_info(self) -> Dict[str, str]:
        """Get info about the current directory"""
        return {
            "path": str(self.cwd),
            "name": self.cwd.name,
            "exists": str(self.cwd.exists()),
            "is_dir": str(self.cwd.is_dir())
        }
    
    def build_context(self, include_files: bool = True) -> str:
        """
        Build the complete context string for the AI
        This is what gets sent to the AI with each request
        """
        context_parts = []
        
        # 1. Working Directory
        dir_info = self.get_directory_info()
        context_parts.append(f"# Current Working Directory\n{dir_info['path']}")
        
        # 2. File Tree (optional)
        if include_files:
            context_parts.append(f"\n# Project Files")
            file_tree = self.get_file_tree()
            context_parts.append(file_tree)
        
        # 3. Current Time
        context_parts.append(f"\n# Current Time\n{self.get_current_time()}")
        
        # Wrap in XML-like tags (like Cline does)
        context = "\n".join(context_parts)
        return f"<environment_details>\n{context}\n</environment_details>"


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Example 1: Basic usage
    builder = ContextBuilder("/Users/sudharshanyadav/Development/cline")
    context = builder.build_context()
    print(context)
    print("\n" + "="*60 + "\n")
    
    # Example 2: Without file listing
    context_minimal = builder.build_context(include_files=False)
    print(context_minimal)
    print("\n" + "="*60 + "\n")
    
    # Example 3: Get individual components
    print("File tree only:")
    print(builder.get_file_tree(max_files=10))
