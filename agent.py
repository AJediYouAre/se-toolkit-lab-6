#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    Debug info to stderr
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10


def load_config() -> dict[str, str]:
    """Load configuration from .env.agent.secret file."""
    env_path = Path(__file__).parent / ".env.agent.secret"

    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        print("Copy .env.agent.example to .env.agent.secret and fill in the values", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_path)

    config = {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model": os.getenv("LLM_MODEL"),
    }

    missing = [k for k, v in config.items() if not v]
    if missing:
        print(f"Error: Missing configuration: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    return config


def validate_path(relative_path: str, project_root: Path) -> Path:
    """
    Validate and resolve a relative path to ensure it's within the project directory.
    
    Raises ValueError if path traversal is detected or path is outside project.
    """
    # Reject path traversal
    if ".." in relative_path:
        raise ValueError("Path traversal not allowed (..)")

    # Resolve to absolute path
    full_path = (project_root / relative_path).resolve()

    # Verify within project root
    project_root_resolved = project_root.resolve()
    try:
        full_path.relative_to(project_root_resolved)
    except ValueError:
        raise ValueError(f"Path outside project directory not allowed: {relative_path}")

    return full_path


def tool_read_file(path: str, project_root: Path) -> str:
    """
    Read a file from the project repository.
    
    Args:
        path: Relative path from project root
        project_root: Project root directory
        
    Returns:
        File contents as string, or error message
    """
    try:
        safe_path = validate_path(path, project_root)
        
        if not safe_path.exists():
            return f"Error: File not found: {path}"
        
        if not safe_path.is_file():
            return f"Error: Not a file: {path}"
        
        return safe_path.read_text(encoding="utf-8")
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def tool_list_files(path: str, project_root: Path) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        project_root: Project root directory
        
    Returns:
        Newline-separated listing of entries, or error message
    """
    try:
        safe_path = validate_path(path, project_root)
        
        if not safe_path.exists():
            return f"Error: Directory not found: {path}"
        
        if not safe_path.is_dir():
            return f"Error: Not a directory: {path}"
        
        entries = []
        for entry in safe_path.iterdir():
            # Skip hidden files/directories
            if entry.name.startswith("."):
                continue
            # Add directory indicator
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        
        return "\n".join(sorted(entries))
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


def get_tool_definitions() -> list[dict]:
    """Return the tool definitions for the LLM API."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the project repository. Use this to read documentation files in the wiki/ directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path. Use this to explore directory structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    ]


def execute_tool_call(tool_name: str, tool_args: dict, project_root: Path) -> str:
    """
    Execute a tool call and return the result.
    
    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool
        project_root: Project root directory
        
    Returns:
        Tool result as string
    """
    if tool_name == "read_file":
        path = tool_args.get("path", "")
        print(f"  Executing read_file('{path}')...", file=sys.stderr)
        return tool_read_file(path, project_root)
    
    elif tool_name == "list_files":
        path = tool_args.get("path", "")
        print(f"  Executing list_files('{path}')...", file=sys.stderr)
        return tool_list_files(path, project_root)
    
    else:
        return f"Error: Unknown tool: {tool_name}"


def call_llm_with_tools(
    messages: list[dict],
    config: dict[str, str],
    tools: list[dict],
) -> dict:
    """
    Call the LLM API with tool definitions.
    
    Args:
        messages: List of message dicts (role, content, etc.)
        config: Configuration dict with api_key, api_base, model
        tools: List of tool definitions
        
    Returns:
        LLM response dict
    """
    api_base = config["api_base"]
    api_key = config["api_key"]
    model = config["model"]

    url = f"{api_base}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    # Retry logic for rate limits
    max_retries = 3
    retry_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                
                # Handle rate limit
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        print(f"Rate limit hit, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})", file=sys.stderr)
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print("Error: Rate limit exceeded after all retries", file=sys.stderr)
                        print(f"Response: {response.text}", file=sys.stderr)
                        sys.exit(1)
                
                response.raise_for_status()
                data = response.json()
                print(f"Got response from LLM", file=sys.stderr)
                return data

        except httpx.TimeoutException:
            print("Error: LLM request timed out (>60s)", file=sys.stderr)
            sys.exit(1)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                print(f"Rate limit hit, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})", file=sys.stderr)
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            print(f"Error: HTTP {e.response.status_code}", file=sys.stderr)
            print(f"Response: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except httpx.RequestError as e:
            print(f"Error: Request failed: {e}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse LLM response: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Should not reach here
    print("Error: Unexpected error in LLM call", file=sys.stderr)
    sys.exit(1)


def run_agentic_loop(
    question: str,
    config: dict[str, str],
    project_root: Path,
) -> tuple[str, str, list[dict]]:
    """
    Run the agentic loop: call LLM, execute tools, repeat until answer.
    
    Args:
        question: User's question
        config: Configuration dict
        project_root: Project root directory
        
    Returns:
        Tuple of (answer, source, tool_calls_list)
    """
    # System prompt for documentation assistant
    system_prompt = """You are a documentation assistant for a software engineering project.
You have access to two tools:
- list_files: List files and directories at a given path
- read_file: Read the contents of a file

IMPORTANT: You must use tools to answer questions. Do NOT answer from your own knowledge.
Always follow this process:
1. First use list_files to explore the wiki/ directory to find relevant files
2. Use read_file to read the contents of relevant files
3. Extract the answer from the file contents you read
4. Include a source reference in format: wiki/filename.md#section-anchor

Rules:
- NEVER answer from your pre-trained knowledge - only use information from files you read
- Always start by exploring the directory structure with list_files
- Only answer after you have read relevant files with read_file
- If you cannot find the answer in the wiki after exploring, say so honestly

When providing your final answer, include:
- The answer text based on what you read from files
- The source as a reference in format: wiki/filename.md#section-anchor"""

    # Initialize messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    tool_definitions = get_tool_definitions()
    tool_calls_log: list[dict] = []
    total_tool_calls = 0

    while total_tool_calls < MAX_TOOL_CALLS:
        print(f"\n--- Iteration {len(tool_calls_log) + 1} ---", file=sys.stderr)

        # Call LLM
        response = call_llm_with_tools(messages, config, tool_definitions)

        # Get the assistant message
        choice = response["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - this is the final answer
            answer = message.get("content", "")
            print(f"\nFinal answer received", file=sys.stderr)

            # Extract source from answer (look for wiki/... pattern)
            source = extract_source(answer, tool_calls_log)

            return answer, source, tool_calls_log

        # Execute tool calls
        for tool_call in tool_calls:
            if total_tool_calls >= MAX_TOOL_CALLS:
                print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
                break

            tool_id = tool_call["id"]
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]

            try:
                tool_args = json.loads(tool_args_str) if tool_args_str else {}
            except json.JSONDecodeError:
                tool_args = {}

            print(f"Tool call: {tool_name}({tool_args})", file=sys.stderr)

            # Execute the tool
            result = execute_tool_call(tool_name, tool_args, project_root)

            # Log the tool call
            tool_calls_log.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })

            total_tool_calls += 1

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result,
            })

        # Add assistant message to conversation
        messages.append({
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": tool_calls,
        })

    # Max iterations reached
    print(f"Max tool calls ({MAX_TOOL_CALLS}) reached, returning partial answer", file=sys.stderr)

    # Try to extract an answer from the conversation
    answer = "Unable to complete the request within the tool call limit."
    source = ""

    # Look for any answer in the last assistant message
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            answer = msg["content"]
            source = extract_source(answer, tool_calls_log)
            break

    return answer, source, tool_calls_log


def extract_source(answer: str, tool_calls_log: list[dict]) -> str:
    """
    Extract or generate a source reference from the answer and tool calls.
    
    Args:
        answer: The answer text
        tool_calls_log: List of tool calls made
        
    Returns:
        Source reference string (e.g., "wiki/git-workflow.md#section")
    """
    # Look for wiki/... pattern in the answer
    import re
    match = re.search(r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)', answer)
    if match:
        return match.group(1)

    # Look at the last read_file call
    for call in reversed(tool_calls_log):
        if call["tool"] == "read_file":
            path = call["args"].get("path", "")
            if path.startswith("wiki/") and path.endswith(".md"):
                return path

    return ""


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    print(f"Question: {question}", file=sys.stderr)

    config = load_config()
    project_root = Path(__file__).parent

    answer, source, tool_calls = run_agentic_loop(question, config, project_root)

    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
