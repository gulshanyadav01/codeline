import aiofiles
import os
import re
import subprocess
import json
from pathlib import Path

async def search_files(cwd: str, pattern: str, file_pattern: str = "*") -> str:
    """Search for pattern across files in the project"""
    try:
        # Try ripgrep first (faster)
        try:
            return await search_with_ripgrep(cwd, pattern, file_pattern)
        except FileNotFoundError:
            # Fall back to pure Python search
            return await search_with_python(cwd, pattern, file_pattern)
    
    except Exception as e:
        return f"Error searching files: {str(e)}"

async def search_with_ripgrep(cwd: str, pattern: str, file_pattern: str) -> str:
    """Search using ripgrep (fast)"""
    cmd = [
        "rg",
        "--json",
        "-e", pattern,
        "--glob", file_pattern,
        "--context", "1",
        "--max-count", "300",
        cwd
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode not in [0, 1]:
        raise Exception(result.stderr)
    
    # Parse JSON output
    matches = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        try:
            data = json.loads(line)
            if data['type'] == 'match':
                rel_path = str(Path(data['data']['path']['text']).relative_to(cwd))
                matches.append({
                    'file': rel_path,
                    'line': data['data']['line_number'],
                    'text': data['data']['lines']['text'].rstrip()
                })
        except:
            continue
    
    return format_search_results(matches)

async def search_with_python(cwd: str, pattern: str, file_pattern: str) -> str:
    """Pure Python search (slower but no dependencies)"""
    results = []
    regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    
    # Determine file extensions to search
    if file_pattern == "*":
        extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.txt', '.md', '.json']
    else:
        extensions = [file_pattern.replace("*", "")]
    
    # Walk directory
    for root, dirs, files in os.walk(cwd):
        # Skip common directories
        dirs[:] = [d for d in dirs if d not in [
            'node_modules', '.git', '__pycache__', 'venv',
            '.venv', 'dist', 'build', '.next', 'target'
        ]]
        
        for file in files:
            # Check file extension
            if not any(file.endswith(ext) for ext in extensions):
                continue
            
            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    if regex.search(line):
                        rel_path = str(file_path.relative_to(cwd))
                        results.append({
                            'file': rel_path,
                            'line': line_num,
                            'text': line.strip()
                        })
                        
                        # Limit results
                        if len(results) >= 300:
                            break
            except:
                continue
            
            if len(results) >= 300:
                break
    
    return format_search_results(results)

def format_search_results(matches: list) -> str:
    """Format search results like Cline"""
    if not matches:
        return "No matches found."
    
    output = [f"Found {len(matches)} result{'s' if len(matches) != 1 else ''}.\\n"]
    
    # Group by file
    by_file = {}
    for m in matches:
        if m['file'] not in by_file:
            by_file[m['file']] = []
        by_file[m['file']].append(m)
    
    # Format each file
    for file_path, file_matches in list(by_file.items())[:20]:  # Limit to 20 files
        output.append(f"{file_path}")
        output.append("│----")
        for match in file_matches[:10]:  # Limit to 10 matches per file
            output.append(f"│{match['text']}")
        if len(file_matches) > 10:
            output.append(f"│... and {len(file_matches) - 10} more matches in this file")
        output.append("│----")
        output.append("")
    
    if len(by_file) > 20:
        output.append(f"... and {len(by_file) - 20} more files with matches")
    
    return '\\n'.join(output)

async def read_file(cwd: str, path: str) -> str:
    """Read a file"""
    try:
        file_path = Path(cwd) / path
        
        if not file_path.exists():
            return f"Error: File not found: {path}"
        
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
        
        return f"File content:\n{content}"
    
    except Exception as e:
        return f"Error reading file: {str(e)}"

async def write_to_file(cwd: str, path: str, content: str) -> str:
    """Write to a file"""
    try:
        file_path = Path(cwd) / path
        
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(content)
        
        return f"Successfully wrote to {path}"
    
    except Exception as e:
        return f"Error writing file: {str(e)}"

async def attempt_completion(cwd: str, result: str) -> str:
    """Mark task as complete"""
    # Just return the result - the calling code handles marking as complete
    return result

async def plan_mode_respond(cwd: str, response: str) -> str:
    """
    Respond to user in Plan mode - for planning and discussion only.
    This tool should ONLY be used when you have already explored relevant 
    files and are ready to present a concrete plan.
    """
    return f"PLAN_RESPONSE: {response}"

async def ask_followup_question(cwd: str, question: str, options: list = None) -> str:
    """
    Ask the user a clarifying question.
    Use this when you need additional details to complete a task.
    
    Args:
        question: The question to ask
        options: Optional list of 2-5 choices for the user to select from
    """
    # Enhanced visual formatting
    print("\n" + "=" * 60)
    print("❓ CLARIFICATION NEEDED")
    print("=" * 60)
    print(f"\n{question}\n")
    
    if options and isinstance(options, list) and len(options) >= 2:
        print("📋 Please choose from the following options:")
        print("-" * 60)
        for i, option in enumerate(options, 1):
            print(f"  [{i}] {option}")
        print("-" * 60)
        print(f"\n💡 Enter choice number (1-{len(options)}) or type your custom answer")
        print("➤ ", end="", flush=True)
        
        # Get user input with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            answer = input().strip()
            
            if not answer:
                if attempt < max_retries - 1:
                    print(f"⚠️  Please provide an answer (attempt {attempt + 2}/{max_retries})")
                    print("➤ ", end="", flush=True)
                    continue
                else:
                    return "User did not provide an answer after multiple prompts."
            
            # Check if user entered a number
            try:
                choice_num = int(answer)
                if 1 <= choice_num <= len(options):
                    selected = options[choice_num - 1]
                    print(f"\n✅ Selected: {selected}\n")
                    return f"User chose option {choice_num}: {selected}"
                else:
                    if attempt < max_retries - 1:
                        print(f"⚠️  Invalid choice. Please enter 1-{len(options)} (attempt {attempt + 2}/{max_retries})")
                        print("➤ ", end="", flush=True)
                        continue
            except ValueError:
                # User provided custom text answer
                print(f"\n✅ Answer received: {answer}\n")
                return f"User answered: {answer}"
            
            # If we got here, the choice was out of range and it's the last attempt
            print(f"\n✅ Answer received: {answer}\n")
            return f"User answered: {answer}"
        
        return f"User answered: {answer}"
    else:
        print("💭 Please provide your answer:")
        print("➤ ", end="", flush=True)
        
        # Get user input with retry for empty responses
        max_retries = 3
        for attempt in range(max_retries):
            answer = input().strip()
            
            if not answer:
                if attempt < max_retries - 1:
                    print(f"⚠️  Please provide an answer (attempt {attempt + 2}/{max_retries})")
                    print("➤ ", end="", flush=True)
                    continue
                else:
                    return "User did not provide an answer after multiple prompts."
            
            print(f"\n✅ Answer received: {answer}\n")
            return f"User answered: {answer}"
        
        return f"User answered: {answer}"

# Export tools dictionary
TOOLS = {
    "read_file": read_file,
    "write_to_file": write_to_file,
    "search_files": search_files,
    "attempt_completion": attempt_completion,
    "plan_mode_respond": plan_mode_respond,
    "ask_followup_question": ask_followup_question
}
