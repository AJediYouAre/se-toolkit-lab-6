# Plan for Task 3: The System Agent

## Overview

Extend the agent from Task 2 with a new `query_api` tool that can call the deployed backend API. This enables the agent to answer questions about the running system (framework, ports, status codes) and data-dependent queries (item count, scores).

## New Tool: `query_api`

### Purpose

Call the deployed backend API to:
- Query data (e.g., `/items/` to count items)
- Check status codes (e.g., request without auth header)
- Discover errors (e.g., `/analytics/completion-rate?lab=lab-99`)

### Parameters

```json
{
  "name": "query_api",
  "description": "Call the backend API...",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, etc.)",
        "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]
      },
      "path": {
        "type": "string",
        "description": "API path (e.g., '/items/', '/analytics/top-learners')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT/PATCH"
      }
    },
    "required": ["method", "path"]
  }
}
```

### Implementation

```python
def query_api(method: str, path: str, body: Optional[str] = None) -> str:
    """
    Call the backend API with authentication.
    
    Returns JSON string with status_code and body.
    """
    api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    url = f"{base_url}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Make request with httpx
    # Return JSON string with status_code and response body
```

### Authentication

- Uses `LMS_API_KEY` from `.env.docker.secret` (backend API key)
- **Not** the same as `LLM_API_KEY` (LLM provider key)
- Sent as `Authorization: Bearer <LMS_API_KEY>` header

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Backend base URL (default: `http://localhost:42002`) | Optional |

## System Prompt Update

The system prompt needs to guide the LLM to choose the right tool:

```
You have access to three tools:
1. list_files - List files in a directory
2. read_file - Read contents of a file
3. query_api - Call the backend API

Use these tools based on the question type:
- For wiki documentation questions → use list_files and read_file
- For source code questions → use read_file on backend/ files
- For running system questions (data, status codes, errors) → use query_api
- For bug diagnosis → use query_api to find the error, then read_file to examine source code
```

## Agentic Loop

The loop remains the same as Task 2:
1. Send question + tools to LLM
2. If tool_calls → execute tools, feed results back
3. If no tool_calls → extract answer, done
4. Max 10 tool calls

## Benchmark Questions

| # | Question | Tool(s) Required | Expected Answer |
|---|----------|------------------|-----------------|
| 0 | Branch protection steps (wiki) | read_file | branch, protect |
| 1 | SSH connection steps (wiki) | read_file | ssh, key, connect |
| 2 | Python web framework (source) | read_file | FastAPI |
| 3 | API router modules (source) | list_files | items, interactions, analytics, pipeline |
| 4 | Items in database (data) | query_api | number > 0 |
| 5 | Status code without auth (system) | query_api | 401 or 403 |
| 6 | Completion-rate error (bug) | query_api, read_file | ZeroDivisionError |
| 7 | Top-learners error (bug) | query_api, read_file | TypeError / None |
| 8 | Request lifecycle (reasoning) | read_file | Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency (reasoning) | read_file | external_id check, duplicates skipped |

## Implementation Steps

1. **Add environment variable loading** for `LMS_API_KEY` and `AGENT_API_BASE_URL`
2. **Implement `query_api` function** with authentication
3. **Add tool schema** to `get_tool_definitions()`
4. **Update system prompt** to guide tool selection
5. **Run `run_eval.py`** and iterate on failures
6. **Add 2 regression tests** for query_api usage
7. **Update AGENT.md** with lessons learned (200+ words)

## Files to Modify

| File | Changes |
|------|---------|
| `plans/task-3.md` | Create (this plan) |
| `agent.py` | Add query_api tool, update config loading, update system prompt |
| `AGENT.md` | Document query_api, benchmark results, lessons learned |
| `tests/test_agent.py` | Add 2 query_api regression tests |
| `.env.docker.secret` | Ensure LMS_API_KEY is set |

## Testing Strategy

**Test 1:** Framework question
- Input: `"What framework does the backend use?"`
- Expect: `read_file` in tool_calls, `FastAPI` in answer

**Test 2:** Database query question
- Input: `"How many items are in the database?"`
- Expect: `query_api` in tool_calls, number in answer

## Benchmark Iteration Workflow

1. Run `uv run run_eval.py`
2. On failure, read the feedback hint
3. Fix the issue (tool description, system prompt, tool implementation)
4. Re-run until all 10 pass
5. Document lessons learned in AGENT.md

## Current Status

**Implementation complete:**
- ✅ `query_api` tool implemented with authentication
- ✅ Tool schema registered with function calling
- ✅ System prompt updated for tool selection
- ✅ Environment variables loaded (`LMS_API_KEY`, `AGENT_API_BASE_URL`)
- ✅ 2 regression tests added

**Pending:**
- ⏳ Need valid Groq API key for local testing
- ⏳ Run `run_eval.py` benchmark after obtaining API key
- ⏳ Iterate on failures and document results

**Note:** The autochecker injects its own LLM credentials during evaluation. The agent reads all configuration from environment variables, so it will work with the autochecker's credentials.
