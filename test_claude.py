"""Test Claude Code subprocess execution"""
import asyncio
import json
import os

async def test_claude():
    claude_path = "/opt/homebrew/bin/claude"
    
    # Test basic command
    print(f"Testing: {claude_path} --version")
    
    process = await asyncio.create_subprocess_exec(
        claude_path,
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    print(f"Return code: {process.returncode}")
    print(f"Stdout: {stdout.decode()}")
    print(f"Stderr: {stderr.decode()}")
    
    # Test with minimal message
    print("\n\nTesting minimal Claude message:")
    
    messages = [{"role": "user", "content": "Hello"}]
    
    args = [
        claude_path,
        "--system-prompt", "You are a helpful assistant.",
        "--verbose",
        "--output-format", "stream-json",
        "--max-turns", "1",
        "--model", "claude-4-5-sonnet-20250929",
        "-p"
    ]
    
    print(f"Command: {' '.join(args)}")
    
    env = os.environ.copy()
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "32000"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    # Write messages to stdin
    messages_json = json.dumps(messages)
    process.stdin.write(messages_json.encode())
    await process.stdin.drain()
    process.stdin.close()
    
    # Read a bit of output
    try:
        line = await asyncio.wait_for(process.stdout.readline(), timeout=10.0)
        print(f"First line: {line.decode()}")
    except asyncio.TimeoutError:
        print("Timeout waiting for output")
    
    # Check stderr
    stderr_output = await process.stderr.read()
    if stderr_output:
        print(f"Stderr: {stderr_output.decode()}")
    
    # Wait for process
    returncode = await process.wait()
    print(f"Return code: {returncode}")

if __name__ == "__main__":
    asyncio.run(test_claude())
