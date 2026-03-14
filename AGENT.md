# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM with **tools** and an **agentic loop**. It can read files and list directories to answer questions about the project wiki. The agent iteratively calls tools, reasons about results, and provides sourced answers.

## LLM Provider

**Provider:** Qwen Code API (DashScope)

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Available in Russia
- OpenAI-compatible API with function calling support
- Strong tool calling capabilities

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌─────────────┐
│  Command Line   │ ──> │  agent.py                    │ ──> │  LLM API    │
│  (question)     │     │  ┌────────────────────────┐  │     │  (Qwen)     │
└─────────────────┘     │  │  Agentic Loop          │  │     └─────────────┘
                        │  │  1. Call LLM           │──┼─────────────────┐
                        │  │  2. Execute tools      │<─┼─────────────────┘
                        │  │  3. Feed results back  │  │
                        │  │  4. Repeat until done  │  │
                        │  └────────────────────────┘  │     ┌──────────────┐
                        │            │                 │     │  JSON Output │
                        │            ▼                 │     │  (stdout)    │
                        │  ┌────────────────────────┐  │     └──────────────┘
                        │  │  Tools                 │  │
                        │  │  - read_file           │  │
                        │  │  - list_files          │  │
                        │  └────────────────────────┘  │
                        └──────────────────────────────┘
                                       │
                                       ▼
                                 ┌──────────────┐
                                 │ .env.agent.  │
                                 │ secret       │
                                 └──────────────┘
```

## Components

### 1. Configuration Loader (`load_config()`)

- Reads environment variables from `.env.agent.secret`
- Required variables:
  - `LLM_API_KEY` — API key for authentication
  - `LLM_API_BASE` — Base URL of the LLM API endpoint
  - `LLM_MODEL` — Model name to use
- Exits with error if any variable is missing

### 2. Tools

#### `read_file(path: str) -> str`

Reads contents of a file from the project repository.

**Parameters:**
- `path` — Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:**
- File contents as string on success
- Error message if file doesn't exist or path is invalid

**Security:**
- Rejects paths containing `..` (path traversal prevention)
- Validates resolved path is within project directory
- Returns error message instead of raising exceptions

**Example:**
```python
read_file("wiki/git-workflow.md", project_root)
# Returns: "# Git Workflow\n\n## Resolving Merge Conflicts\n..."
```

#### `list_files(path: str) -> str`

Lists files and directories at a given path.

**Parameters:**
- `path` — Relative directory path from project root (e.g., `wiki`)

**Returns:**
- Newline-separated listing of entries (directories end with `/`)
- Error message if directory doesn't exist or path is invalid

**Security:**
- Same path validation as `read_file`
- Skips hidden files/directories (starting with `.`)

**Example:**
```python
list_files("wiki", project_root)
# Returns: "git-workflow.md\nllm.md\nqwen.md\n..."
```

### 3. Tool Definitions (`get_tool_definitions()`)

Returns OpenAI-compatible function calling schemas:

```json
[
  {
    "type": "function",
    "function": {
      "name": "read_file",
      "description": "Read the contents of a file...",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string"}
        },
        "required": ["path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "list_files",
      "description": "List files and directories...",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string"}
        },
        "required": ["path"]
      }
    }
  }
]
```

### 4. Agentic Loop (`run_agentic_loop()`)

The core reasoning loop that enables the agent to iteratively use tools:

```
Question ──▶ LLM (with tool definitions) ──▶ tool_calls?
                         │
                    yes  │
                         ▼
              Execute tools (read_file, list_files)
                         │
                         ▼
              Append results as tool messages
                         │
                         ▼
              Back to LLM (new iteration)
                         │
                    no   │
                         ▼
              Final answer → JSON output
```

**Loop logic:**
1. Send user question + system prompt + tool definitions to LLM
2. Parse response:
   - If `tool_calls` present → execute each tool, collect results
   - If no tool calls → extract answer, done
3. Append tool results as messages with `role="tool"`
4. Repeat from step 1
5. **Max iterations:** 10 tool calls total (prevents infinite loops)

**System prompt:**
```
You are a documentation assistant for a software engineering project.
You have access to two tools:
- list_files: List files and directories at a given path
- read_file: Read the contents of a file

To answer questions about the project:
1. Use list_files to explore the wiki/ directory structure
2. Use read_file to read relevant documentation files
3. Find the answer and include a source reference
```

### 5. Path Security (`validate_path()`)

Protects against directory traversal attacks:

```python
def validate_path(relative_path: str, project_root: Path) -> Path:
    # Reject path traversal
    if ".." in relative_path:
        raise ValueError("Path traversal not allowed (..)")

    # Resolve to absolute path
    full_path = (project_root / relative_path).resolve()

    # Verify within project root
    project_root_resolved = project_root.resolve()
    full_path.relative_to(project_root_resolved)  # Raises if outside

    return full_path
```

### 6. CLI Interface (`main()`)

- Parses command-line argument (the question)
- Runs the agentic loop
- Outputs JSON to stdout
- Outputs debug/progress info to stderr

## Input/Output

### Input

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output (stdout)

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\nllm.md\nqwen.md"
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git Workflow\n\n## Resolving Merge Conflicts\n..."
    }
  ]
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Wiki reference (e.g., `wiki/file.md#section`) |
| `tool_calls` | array | List of all tool calls made during execution |

### Debug Output (stderr)

```
Question: How do you resolve a merge conflict?

--- Iteration 1 ---
Calling LLM at https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions...
Got response from LLM
Tool call: list_files({'path': 'wiki'})
  Executing list_files('wiki')...

--- Iteration 2 ---
Calling LLM...
Tool call: read_file({'path': 'wiki/git-workflow.md'})
  Executing read_file('wiki/git-workflow.md')...

--- Iteration 3 ---
Calling LLM...
Final answer received
```

## Configuration

### Environment File: `.env.agent.secret`

```ini
# API key for Qwen Code
LLM_API_KEY=your-api-key-here

# Qwen Code API endpoint (DashScope)
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

### Setup Instructions

1. Copy the example file:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Get your API key from Qwen Code or DashScope

3. Edit `.env.agent.secret` and fill in the values

## Running the Agent

```bash
# Install dependencies
uv sync

# Run with a question
uv run agent.py "What files are in the wiki?"
uv run agent.py "How do you resolve a merge conflict?"
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error to stderr |
| Missing environment variables | Exit with error to stderr |
| API timeout (>60s) | Exit with error to stderr |
| HTTP error (4xx, 5xx) | Exit with error to stderr |
| Path traversal attempt | Return error in tool result |
| Max tool calls (10) | Return partial answer |

## Exit Codes

- `0` — Success
- `1` — Error (configuration, network, API, parsing)

## Dependencies

- `httpx` — HTTP client for API requests
- `python-dotenv` — Load environment variables from `.env` file

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

**Tests:**
1. `test_agent_returns_json_with_required_fields` — Basic JSON structure (Task 1)
2. `test_documentation_agent_read_file` — Verifies `read_file` tool usage
3. `test_documentation_agent_list_files` — Verifies `list_files` tool usage

## Future Extensions (Task 3)

- Add more tools (API queries, web search, etc.)
- Improve source extraction with section anchors
- Add caching for repeated file reads
- Support for multi-turn conversations
