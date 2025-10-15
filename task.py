import asyncio
from typing import List, Dict, Any
from ai_client import AIClient
from tools import read_file, write_to_file, attempt_completion, search_files

class Task:
    def __init__(self, user_message: str, websocket, config: Dict):
        self.user_message = user_message
        self.websocket = websocket
        self.config = config
        # Let AIClient load configuration from environment
        self.ai_client = AIClient()
        self.conversation_history = []
        self.abort = False
        
        # Available tools
        self.tools = {
            "read_file": read_file,
            "write_to_file": write_to_file,
            "search_files": search_files,
            "attempt_completion": attempt_completion
        }
    
    async def start(self):
        """Main task execution"""
        await self.send_to_ui("status", "Task started")
        
        # Initial user message
        user_content = f"<task>\n{self.user_message}\n</task>"
        
        # Main loop
        await self.task_loop(user_content)
    
    async def task_loop(self, user_content: str):
        """Main execution loop"""
        
        while not self.abort:
            # Build context
            context = self.build_context()
            
            # Add to conversation
            self.conversation_history.append({
                "role": "user",
                "content": f"{user_content}\n\n{context}"
            })
            
            # Make API request
            assistant_message = ""
            tool_results = []
            
            async for chunk in self.ai_client.stream_message(
                self.conversation_history
            ):
                if chunk["type"] == "text":
                    assistant_message += chunk["text"]
                    await self.send_to_ui("text", chunk["text"])
                
                elif chunk["type"] == "tool_use":
                    # Execute tool
                    result = await self.execute_tool(chunk)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": chunk["id"],
                        "content": result
                    })
            
            # Add assistant message
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            # If tools executed, loop back
            if tool_results:
                # Prepare next user content with tool results
                user_content = "\n\n".join([
                    f"[{r['tool_use_id']}] Result: {r['content']}"
                    for r in tool_results
                ])
            else:
                # No tools used
                user_content = "Please use a tool to complete the task, or call attempt_completion."
    
    def build_context(self) -> str:
        """Build environment context"""
        import os
        from datetime import datetime
        
        context_parts = []
        
        # Working directory
        context_parts.append(f"# Working Directory\n{self.config['cwd']}")
        
        # Files in directory
        files = os.listdir(self.config['cwd'])
        context_parts.append(f"\n# Files\n" + "\n".join(files[:20]))
        
        # Current time
        context_parts.append(f"\n# Time\n{datetime.now()}")
        
        return "<environment_details>\n" + "\n".join(context_parts) + "\n</environment_details>"
    
    async def execute_tool(self, tool_block: Dict) -> str:
        """Execute a tool"""
        tool_name = tool_block["name"]
        tool_params = tool_block.get("input", {})
        
        await self.send_to_ui("tool", {
            "name": tool_name,
            "params": tool_params
        })
        
        if tool_name in self.tools:
            try:
                result = await self.tools[tool_name](
                    self.config["cwd"],
                    **tool_params
                )
                
                await self.send_to_ui("tool_result", {
                    "name": tool_name,
                    "result": result
                })
                
                return result
            except Exception as e:
                return f"Error: {str(e)}"
        else:
            return f"Unknown tool: {tool_name}"
    
    async def send_to_ui(self, message_type: str, content: Any):
        """Send message to frontend"""
        try:
            await self.websocket.send_json({
                "type": message_type,
                "content": content
            })
        except:
            pass
