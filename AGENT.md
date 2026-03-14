# System Agent Architecture (Task 3)

## Overview

This agent is a CLI tool that connects to an LLM with **three tools** (`read_file`, `list_files`, `query_api`) and an **agentic loop**. It can read documentation, explore source code, and query the running backend API to answer questions about the system. The agent iteratively calls tools, reasons about results, and provides accurate answers based on actual system state.

## LLM Provider

**Provider:** Groq API

**Model:** `qwen/qwen3-32b`

**Why Groq:**
- Fast inference with LPU™ technology
- OpenAI-compatible API with function calling support
- Free tier available for development
- Strong tool calling capabilities with Qwen models

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────┐     ┌─────────────┐
│  Command Line   │ ──> │  agent.py                            │ ──> │  LLM API    │
│  (question)     │     │  ┌────────────────────────────────┐  │     │  (Groq)     │
└─────────────────┘     │  │  Agentic Loop                  │  │     └─────────────┘
                        │  │  1. Call LLM with tools        │──┼─────────────────┐
                        │  │  2. Execute tool (read/file/   │<─┼─────────────────┘
                        │  │     query_api)                 │  │
                        │  │  3. Feed results back          │  │
                        │  │  4. Repeat until answer        │  │
                        │  └────────────────────────────────┘  │     ┌──────────────┐
                        │            │                         │     │  JSON Output │
                        │            ▼                         │     │  (stdout)    │
                        │  ┌────────────────────────────────┐  │     └──────────────┘
                        │  │  Tools                        │  │
                        │  │  - read_file (wiki/code)      │  │
                        │  │  - list_files (directories)   │  │
                        │  │  - query_api (backend API)    │  │
                        │  └────────────────────────────────┘  │
                        └──────────────────────────────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                             ▼
                  ┌──────────────┐            ┌──────────────┐
                  │ .env.agent.  │            │ .env.docker  │
                  │ secret       │            │ .secret      │
                  │ (LLM config) │            │ (API config) │
                  └──────────────┘            └──────────────┘
```

## Tools

### 1. `read_file(path: str) -> str`

Reads contents of a file from the project repository.

**Use cases:**
- Reading wiki documentation (`wiki/git-workflow.md`)
- Reading source code (`backend/app/main.py`)
- Reading configuration files (`docker-compose.yml`)

**Security:**
- Rejects paths containing `..` (path traversal prevention)
- Validates resolved path is within project directory

### 2. `list_files(path: str) -> str`

Lists files and directories at a given path.

**Use cases:**
- Exploring wiki directory structure
- Finding API router modules in `backend/app/routers/`
- Discovering available documentation files

**Security:**
- Same path validation as `read_file`
- Skips hidden files/directories (starting with `.`)

### 3. `query_api(method: str, path: str, body: str?) -> str`

Calls the backend API with authentication.

**Parameters:**
- `method` — HTTP method (GET, POST, PUT, PATCH, DELETE)
- `path` — API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` — Optional JSON request body for POST/PUT/PATCH

**Returns:**
- JSON string with `status_code` and `body`
- Error message on failure

**Authentication:**
- Uses `LMS_API_KEY` from `.env.docker.secret`
- Sent as `Authorization: Bearer <LMS_API_KEY>` header

**Use cases:**
- Querying database contents (`GET /items/`)
- Checking status codes (request without auth header)
- Discovering API errors (`GET /analytics/completion-rate?lab=lab-99`)

## Agentic Loop

The core reasoning loop that enables the agent to iteratively use tools:

```
Question ──▶ LLM (with 3 tool definitions + system prompt)
                 │
            tool_calls?
            ┌─────┴─────┐
           yes         no
            │           │
            ▼           │
    Execute tools       │
    (read/file/api)     │
            │           │
            ▼           │
    Append results      │
    as tool messages    │
            │           │
            ▼           │
    Back to LLM         │
    (new iteration)     │
            │           │
            └───────────┘
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

## System Prompt Strategy

The system prompt guides the LLM to choose the right tool based on question type:

```
You are a system assistant for a software engineering project.
You have access to three tools:
- list_files: List files and directories at a given path
- read_file: Read the contents of a file
- query_api: Call the backend API to query data or check status codes

Choose the right tool based on the question type:
1. For wiki documentation questions → use list_files and read_file on wiki/ files
2. For source code questions → use read_file on backend/ files
3. For running system questions → use query_api
4. For bug diagnosis → use query_api to reproduce the error, then read_file to examine source code
```

**Key insight:** The LLM needs explicit guidance on when to use each tool. Without clear instructions, it may try to answer from pre-trained knowledge instead of using tools.

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Backend base URL (default: `http://localhost:42002`) | Optional |

**Important:** The autochecker injects its own credentials during evaluation. The agent reads all configuration from environment variables, so it works with any valid credentials.

## Input/Output

### Input

```bash
uv run agent.py "How many items are in the database?"
```

### Output (stdout)

```json
{
  "answer": "There are 44 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | File reference (optional for API questions) |
| `tool_calls` | array | List of all tool calls made during execution |

## Tool Selection Logic

The agent uses different tools for different question types:

| Question Type | Example | Tool(s) Required |
|--------------|---------|------------------|
| Wiki documentation | "According to the wiki, how to protect a branch?" | `read_file` |
| Source code | "What framework does the backend use?" | `read_file` |
| Directory listing | "List all API router modules" | `list_files` |
| Data query | "How many items are in the database?" | `query_api` |
| Status code | "What status code without auth?" | `query_api` |
| Bug diagnosis | "What error does /analytics/completion-rate return?" | `query_api` + `read_file` |
| System reasoning | "Explain the request lifecycle" | `read_file` (multiple files) |

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error to stderr |
| Missing `LMS_API_KEY` | Return error in `query_api` result |
| API timeout (>60s for LLM, >30s for backend) | Exit with error to stderr |
| HTTP error (4xx, 5xx) | Return error in tool result |
| Path traversal attempt | Return error in tool result |
| Max tool calls (10) | Return partial answer |
| Rate limit (429) | Retry with exponential backoff (up to 5 times) |

## Lessons Learned

**1. Tool descriptions matter:** Initially, the LLM would not use `query_api` for data questions. After improving the tool description to explicitly mention "query data, check status codes, discover errors", tool usage improved significantly.

**2. System prompt is critical:** The LLM tends to answer from pre-trained knowledge. The system prompt must explicitly instruct it to use tools and provide clear guidance on which tool to use for each question type.

**3. Retry logic is essential:** Rate limits (429 errors) are common with free-tier APIs. Implemented exponential backoff (10s, 20s, 40s, 80s, 160s) with up to 5 retries.

**4. Path security is non-negotiable:** The `validate_path()` function prevents directory traversal attacks by rejecting paths containing `..` and verifying the resolved path is within the project directory.

**5. Two distinct API keys:** `LLM_API_KEY` authenticates with the LLM provider (Groq), while `LMS_API_KEY` authenticates with the backend API. Mixing them up causes confusing authentication errors.

**6. Null content handling:** When the LLM returns tool calls, the `content` field is often `null` (not missing). Using `(msg.get("content") or "")` instead of `msg.get("content", "")` prevents `AttributeError`.

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

**Tests:**
1. `test_agent_returns_json_with_required_fields` — Basic JSON structure
2. `test_documentation_agent_uses_read_file` — Wiki documentation questions
3. `test_documentation_agent_uses_list_files` — Directory exploration
4. `test_system_agent_uses_read_file_for_framework` — Source code questions
5. `test_system_agent_uses_query_api` — Data queries

## Benchmark Results

**Local evaluation (`run_eval.py`):** Pending valid API key

**Expected performance:**
- Questions 0-3 (wiki/source): Should pass with `read_file` and `list_files`
- Questions 4-5 (API data): Should pass with `query_api`
- Questions 6-7 (bug diagnosis): Should pass with `query_api` + `read_file`
- Questions 8-9 (reasoning): Depends on LLM judge evaluation

## Running the Agent

```bash
# Install dependencies
uv sync

# Start the backend (required for query_api)
docker compose up -d

# Run with a question
uv run agent.py "What framework does the backend use?"
uv run agent.py "How many items are in the database?"
uv run agent.py "What error does /analytics/completion-rate return for lab-99?"
```

## Exit Codes

- `0` — Success
- `1` — Error (configuration, network, API, parsing)

## Dependencies

- `httpx` — HTTP client for API requests (LLM and backend)
- `python-dotenv` — Load environment variables from `.env` files

## Future Extensions

- Add caching for repeated file reads (reduces token usage)
- Support for multi-turn conversations (maintain conversation history)
- Add web search tool for external knowledge
- Implement content truncation for large files
- Add retry logic for backend API calls
