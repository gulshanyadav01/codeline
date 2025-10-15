"""OpenAI provider implementation."""
from openai import AsyncOpenAI
import json
import re
import httpx
from typing import AsyncGenerator, Dict, Any
from .base import AIProvider
from .prompts import get_system_prompt


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gpt-4o")
    
    async def stream_message(
        self, 
        conversation_history: list, 
        working_dir: str = None, 
        mode: str = "ACT"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a message from OpenAI"""
        
        # Get mode-specific system prompt
        system_prompt = self._get_system_prompt(working_dir, mode)
        
        # Format messages for OpenAI
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Create a fresh client with custom httpx client to avoid lifecycle issues
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            client = AsyncOpenAI(
                api_key=self.api_key,
                http_client=http_client
            )
            
            # Stream response
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                max_tokens=4096
            )
            
            full_text = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_text += text
                    yield {"type": "text", "text": text}
            
            # Parse tool uses after streaming completes
            tool_pattern = r'<(\w+)>(.*?)</\1>'
            
            # Valid tool names (for filtering)
            valid_tools = [
                'read_file', 'write_to_file', 'search_files', 
                'attempt_completion', 'plan_mode_respond', 'ask_followup_question'
            ]
            
            for match in re.finditer(tool_pattern, full_text, re.DOTALL):
                tool_name = match.group(1)
                tool_content = match.group(2)
                
                # Only process valid tool names (not parameters)
                if tool_name not in valid_tools:
                    continue
                
                # Parse parameters
                params = {}
                param_pattern = r'<(\w+)>(.*?)</\1>'
                for param_match in re.finditer(param_pattern, tool_content, re.DOTALL):
                    param_name = param_match.group(1)
                    param_value = param_match.group(2).strip()
                    
                    # Try to parse as JSON for array parameters (like options)
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
    
    def _get_system_prompt(self, working_dir: str = None, mode: str = "ACT") -> str:
        """Generate mode-specific system prompt"""
        return get_system_prompt(working_dir, mode)
