#!/usr/bin/env python3
"""
test_agent.py - Simple test of the complete backend flow (no WebSockets)

This script demonstrates:
1. Context building
2. AI streaming
3. Tool parsing
4. Tool execution
5. Task loop

Usage:
    python3 test_agent.py "Create a file hello.txt with Hello World"
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ai_client import AIClient
from tools import read_file, write_to_file, attempt_completion, search_files
from datetime import datetime


class SimpleAgent:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.ai_client = AIClient()  # Load from environment
        self.conversation_history = []
        self.mode = "PLAN"  # Default mode
        self.tools = {
            "read_file": read_file,
            "write_to_file": write_to_file,
            "search_files": search_files,
            "attempt_completion": attempt_completion
        }
    
    def build_context(self) -> str:
        """Build environment context"""
        context_parts = []
        
        # Working directory
        context_parts.append(f"# Working Directory\n{self.working_dir}")
        
        # Files in directory
        try:
            files = os.listdir(self.working_dir)
            context_parts.append(f"\n# Files\n" + "\n".join(files[:20]))
        except:
            pass
        
        # Current time
        context_parts.append(f"\n# Time\n{datetime.now()}")
        
        return "<environment_details>\n" + "\n".join(context_parts) + "\n</environment_details>"
    
    async def run(self, task: str):
        """Run the agent with a task"""
        print("=" * 60)
        print("🤖 PyAgent Test Agent")
        print("=" * 60)
        print(f"📁 Working Directory: {self.working_dir}")
        print(f"📝 Task: {task}")
        print("=" * 60)
        print()
        
        # Ask user which mode to start in
        print("\n🎯 Choose starting mode:")
        print("1. PLAN mode - Discuss and plan approach (default)")
        print("2. ACT mode - Execute immediately")
        choice = input("Enter choice (1 or 2) [default: 1]: ").strip()
        
        if choice == "2":
            self.mode = "ACT"
            print(f"\n⚡ Starting in ACT mode\n")
        else:
            self.mode = "PLAN"
            print(f"\n📋 Starting in PLAN mode\n")
        
        # Build initial user content
        user_content = f"<task>\n{task}\n</task>"
        
        # Start the task loop
        await self.task_loop(user_content)
    
    async def task_loop(self, user_content: str):
        """Main task loop - keeps running until completion"""
        iteration = 0
        
        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"🔄 Iteration {iteration}")
            print(f"{'='*60}\n")
            
            # Build context
            context = self.build_context()
            
            print(f"📦 [Context] Built environment context")
            
            # Add to conversation
            full_user_content = f"{user_content}\n\n{context}"
            self.conversation_history.append({
                "role": "user",
                "content": full_user_content
            })
            
            # Make API request
            print(f"🤖 [AI] Streaming response...\n")
            
            assistant_message = ""
            tool_uses = []
            
            try:
                async for chunk in self.ai_client.stream_message(
                    self.conversation_history,
                    self.working_dir,
                    self.mode
                ):
                    if chunk["type"] == "text":
                        text = chunk["text"]
                        assistant_message += text
                        # Print without newline
                        print(text, end="", flush=True)
                    
                    elif chunk["type"] == "tool_use":
                        tool_uses.append(chunk)
                
                print("\n")  # Newline after streaming
                
            except Exception as e:
                print(f"\n❌ [Error] API request failed: {str(e)}")
                return
            
            # Add assistant message to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            # Execute tools
            if not tool_uses:
                print("⚠️  [Warning] No tools used, prompting AI to continue...\n")
                user_content = "Please use a tool to complete the task, or call attempt_completion when done."
                continue
            
            # Execute each tool
            tool_results = []
            did_complete = False
            user_feedback = None
            
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_params = tool_use.get("input", {})
                tool_id = tool_use["id"]
                
                print(f"🔧 [Tool] {tool_name}({', '.join([f'{k}={repr(v[:50])}...' if len(str(v)) > 50 else f'{k}={repr(v)}' for k, v in tool_params.items()])})")
                
                # Ask for human interruption (skip for certain tools)
                if tool_name not in ["attempt_completion", "ask_followup_question", "plan_mode_respond"]:
                    print(f"\n💭 [Interrupt?] Press Enter to execute, or type feedback to provide guidance: ", end="", flush=True)
                    feedback = input().strip()
                    
                    if feedback:
                        print(f"✍️  [Feedback Received] {feedback}\n")
                        user_feedback = feedback
                        # Don't execute this tool, stop and incorporate feedback
                        break
                
                # Check mode restrictions
                plan_only_tools = ["read_file", "search_files", "plan_mode_respond", "ask_followup_question"]
                act_only_tools = ["write_to_file", "attempt_completion"]
                
                if self.mode == "PLAN" and tool_name in act_only_tools:
                    result = f"Error: {tool_name} is not available in PLAN mode. Use plan_mode_respond to present your plan first."
                    print(f"❌ [Mode Error] {result}\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result
                    })
                    continue
                
                # Check if it's plan_mode_respond - special handling
                if tool_name == "plan_mode_respond":
                    result = tool_params.get("response", "")
                    print(f"📋 [Plan Response]\n{result}\n")
                    print("\n💡 To implement this plan, switch to ACT mode")
                    print("Enter 'switch' to change modes, or press Enter to continue planning: ", end="", flush=True)
                    switch_input = input().strip().lower()
                    
                    if switch_input == "switch":
                        self.mode = "ACT"
                        print(f"\n🔄 Switched to ACT mode\n")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"User switched to ACT mode. You can now execute actions."
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Plan acknowledged. Continue in PLAN mode."
                        })
                    continue
                
                # Execute tool
                if tool_name in self.tools:
                    try:
                        result = await self.tools[tool_name](
                            self.working_dir,
                            **tool_params
                        )
                        
                        print(f"✅ [Tool Result] {result[:100]}{'...' if len(result) > 100 else ''}\n")
                        
                        # Check if it's attempt_completion
                        if tool_name == "attempt_completion":
                            print("=" * 60)
                            print("✅ [Complete] Task finished!")
                            print("=" * 60)
                            print(f"\n📊 Final Result:\n{result}\n")
                            did_complete = True
                            return
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })
                    
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        print(f"❌ [Tool Error] {error_msg}\n")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": error_msg
                        })
                else:
                    error_msg = f"Unknown tool: {tool_name}"
                    print(f"❌ [Error] {error_msg}\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": error_msg
                    })
            
            # Handle user feedback or tool results
            if user_feedback:
                # User provided feedback, incorporate it into next iteration
                print(f"📝 [Continuing with user feedback...]\n")
                user_content = f"<feedback>\n{user_feedback}\n</feedback>"
            elif tool_results:
                # Normal tool execution, feed results back
                user_content = "\n\n".join([
                    f"[{r['tool_use_id']}] Result: {r['content']}"
                    for r in tool_results
                ])


async def main():
    """Main entry point"""
    # Get task from command line or use default
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "do you understand this codebase?"
    
    # Get API key
    # api_key = os.getenv("OPENAI_API_KEY")
    api_key="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"
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        print("   Set it with: export OPENAI_API_KEY=sk-...")
        sys.exit(1)
    
    # Get working directory
    working_dir = "/Users/sudharshanyadav/Desktop/mazik"
    # working_dir = os.getenv("WORKING_DIRECTORY", os.getcwd())
    
    # Run agent
    agent = SimpleAgent(working_dir)
    await agent.run(task)


if __name__ == "__main__":
    asyncio.run(main())
