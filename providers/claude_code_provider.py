"""Claude Code CLI provider implementation."""
import asyncio
import json
import re
import os
import tempfile
from typing import AsyncGenerator, Dict, Any, Optional
from .base import AIProvider
from .prompts import get_system_prompt


class ClaudeCodeProvider(AIProvider):
    """Claude Code CLI provider using subprocess."""
    
    # Maximum system prompt length before using file-based input
    MAX_SYSTEM_PROMPT_LENGTH = 65536
    
    # Claude Code environment settings
    CLAUDE_CODE_MAX_OUTPUT_TOKENS = "32000"
    CLAUDE_CODE_TIMEOUT = 600  # 10 minutes
    
    # Tools to disable in Claude Code (we use our own tool format)
    DISABLED_TOOLS = [
        "Task", "Bash", "Glob", "Grep", "LS", "exit_plan_mode",
        "Read", "Edit", "MultiEdit", "Write", "NotebookRead",
        "NotebookEdit", "WebFetch", "TodoRead", "TodoWrite", "WebSearch"
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.claude_path = config.get("claude_code_path", "claude")
        self.model = config.get("model", "claude-4-5-sonnet-20250929")
    
    async def stream_message(
        self, 
        conversation_history: list, 
        working_dir: str = None, 
        mode: str = "ACT"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a message from Claude Code CLI"""
        
        # Get mode-specific system prompt
        system_prompt = self._get_system_prompt(working_dir, mode)
        
        # Format messages
        messages = []
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Handle long system prompts with temp file
        temp_file_path = None
        should_use_file = len(system_prompt) > self.MAX_SYSTEM_PROMPT_LENGTH
        
        if should_use_file:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.txt', 
                delete=False,
                prefix='pyagent-system-prompt-'
            )
            temp_file.write(system_prompt)
            temp_file.close()
            temp_file_path = temp_file.name
            system_prompt_arg = temp_file_path
        else:
            system_prompt_arg = system_prompt
        
        try:
            # Build command arguments
            args = [
                self.claude_path,
                "--system-prompt-file" if should_use_file else "--system-prompt",
                system_prompt_arg,
                "--verbose",
                "--output-format", "stream-json",
                "--disallowedTools", ",".join(self.DISABLED_TOOLS),
                "--max-turns", "1",
                "--model", self.model,
                "-p"
            ]
            
            # Setup environment
            env = os.environ.copy()
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = self.CLAUDE_CODE_MAX_OUTPUT_TOKENS
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
            env["DISABLE_NON_ESSENTIAL_MODEL_CALLS"] = "1"
            
            # Remove ANTHROPIC_API_KEY to let Claude Code handle auth
            if "ANTHROPIC_API_KEY" in env:
                del env["ANTHROPIC_API_KEY"]
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=working_dir or os.getcwd()
            )
            
            # Write messages to stdin
            messages_json = json.dumps(messages)
            process.stdin.write(messages_json.encode())
            await process.stdin.drain()
            process.stdin.close()
            
            # Read stdout line by line
            partial_data = ""
            full_text = ""
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode().strip()
                if not line_str:
                    continue
                
                # Try to parse the line
                chunk = self._parse_chunk(line_str, partial_data)
                
                if chunk is None:
                    # Line is incomplete, accumulate it
                    partial_data += line_str
                    continue
                
                # Successfully parsed
                partial_data = ""
                
                # Process chunk based on type
                if isinstance(chunk, str):
                    # Text chunk
                    full_text += chunk
                    yield {"type": "text", "text": chunk}
                elif isinstance(chunk, dict):
                    # JSON chunk
                    if chunk.get("type") == "assistant" and "message" in chunk:
                        # Assistant message with content
                        message = chunk["message"]
                        for content_block in message.get("content", []):
                            if content_block.get("type") == "text":
                                text = content_block.get("text", "")
                                full_text += text
                                yield {"type": "text", "text": text}
            
            # Wait for process to complete
            await process.wait()
            
            # Check exit code
            if process.returncode != 0:
                stderr_output = await process.stderr.read()
                error_msg = stderr_output.decode().strip()
                
                if "unknown option '--system-prompt-file'" in error_msg:
                    raise Exception(
                        "The Claude Code executable is outdated. "
                        "Please update it to the latest version."
                    )
                elif "ENOENT" in error_msg:
                    raise Exception(
                        f"Failed to find the Claude Code executable at '{self.claude_path}'. "
                        "Make sure it's installed and available in your PATH."
                    )
                elif error_msg:
                    raise Exception(f"Claude Code process exited with code {process.returncode}: {error_msg}")
                # If no error message but non-zero exit, it might have still produced output, so continue
            
            # Parse tool uses from the full text
            tool_pattern = r'<(\w+)>(.*?)</\1>'
            valid_tools = [
                'read_file', 'write_to_file', 'search_files', 
                'attempt_completion', 'plan_mode_respond', 'ask_followup_question'
            ]
            
            for match in re.finditer(tool_pattern, full_text, re.DOTALL):
                tool_name = match.group(1)
                tool_content = match.group(2)
                
                if tool_name not in valid_tools:
                    continue
                
                # Parse parameters
                params = {}
                param_pattern = r'<(\w+)>(.*?)</\1>'
                for param_match in re.finditer(param_pattern, tool_content, re.DOTALL):
                    param_name = param_match.group(1)
                    param_value = param_match.group(2).strip()
                    
                    if param_name == 'options' and param_value.startswith('['):
                        try:
                            params[param_name] = json.loads(param_value)
                        except json.JSONDecodeError:
                            params[param_name] = param_value
                    else:
                        params[param_name] = param_value
                
                yield {
                    "type": "tool_use",
                    "name": tool_name,
                    "id": f"tool_{tool_name}",
                    "input": params
                }
        
        finally:
            # Clean up temp file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
    
    def _parse_chunk(self, data: str, partial_data: str) -> Optional[Any]:
        """
        Parse a chunk from Claude Code output.
        Returns parsed chunk or None if incomplete.
        """
        # Try parsing with accumulated partial data if any
        if partial_data:
            data = partial_data + data
        
        # Try to parse as JSON
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            # Not valid JSON, might be incomplete
            return None
    
    def _get_system_prompt(self, working_dir: str = None, mode: str = "ACT") -> str:
        """Generate mode-specific system prompt"""
        return get_system_prompt(working_dir, mode)
