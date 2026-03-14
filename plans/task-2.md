# Plan for Task 2: The Documentation Agent

## Overview

Extend the agent from Task 1 with tools and an agentic loop. The agent will be able to read files and list directories to answer questions about the project wiki.

## Tool Definitions

### 1. `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required) — relative path from project root

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:**
- Validate path does not contain `../` traversal
- Ensure resolved path is within project directory

**Schema (OpenAI function calling):**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative path from project root"}
    },
    "required": ["path"]
  }
}
```

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required) — relative directory path from project root

**Returns:** Newline-separated listing of entries.

**Security:**
- Validate path does not contain `../` traversal
- Ensure resolved path is within project directory
- Only list directories, not files

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories at a given path",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative directory path from project root"}
    },
    "required": ["path"]
  }
}
```

## Agentic Loop

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
3. Append tool results as messages with role="tool"
4. Repeat from step 1
5. **Max iterations:** 10 tool calls total (prevents infinite loops)

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to read relevant files
3. Find the answer and include source reference (file path + section anchor)
4. Format the final answer with the source

Example:
```
You are a documentation assistant. You have access to two tools:
- list_files: List files in a directory
- read_file: Read contents of a file

To answer questions about the project:
1. First use list_files to explore the wiki/ directory
2. Use read_file to read relevant files
3. Find the answer and include the source reference

Always include the source as: wiki/filename.md#section-anchor
```

## Path Security

**Threat:** User might try to read files outside project directory (e.g., `../../etc/passwd`)

**Mitigation:**
1. Reject paths containing `..`
2. Use `Path.resolve()` to get absolute path
3. Verify resolved path starts with project root
4. Return error message if path is invalid

```python
def validate_path(relative_path: str, project_root: Path) -> Path:
    # Reject path traversal
    if ".." in relative_path:
        raise ValueError("Path traversal not allowed")
    
    # Resolve to absolute path
    full_path = (project_root / relative_path).resolve()
    
    # Verify within project root
    if not str(full_path).startswith(str(project_root.resolve())):
        raise ValueError("Path outside project not allowed")
    
    return full_path
```

## Output Format

```json
{
  "answer": "The answer text from LLM",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "file contents..."
    }
  ]
}
```

## Implementation Steps

1. **Define tool schemas** — JSON schemas for function calling
2. **Implement tool functions** — `read_file()`, `list_files()` with security
3. **Update LLM call** — pass tools parameter to API
4. **Implement agentic loop** — iterate until answer or max calls
5. **Parse tool calls** — extract from LLM response
6. **Format output** — include answer, source, tool_calls

## Files to Modify

| File | Changes |
|------|---------|
| `plans/task-2.md` | Create (this plan) |
| `agent.py` | Add tools, agentic loop, update output format |
| `AGENT.md` | Document tools and agentic loop |
| `tests/test_agent.py` | Add 2 tool-calling tests |

## Dependencies

No new dependencies needed — using existing `httpx` and `python-dotenv`.

## Testing Strategy

**Test 1:** Question about merge conflicts
- Input: `"How do you resolve a merge conflict?"`
- Expect: `read_file` in tool_calls, `wiki/git-workflow.md` in source

**Test 2:** Question about wiki files
- Input: `"What files are in the wiki?"`
- Expect: `list_files` in tool_calls
