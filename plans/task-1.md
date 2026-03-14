# Plan for Task 1: Call an LLM from Code

## LLM Provider

**Provider:** Qwen Code API (DashScope)

**Model:** `qwen3-coder-plus`

**Reason:** 
- 1000 free requests per day
- Available in Russia
- OpenAI-compatible API
- Strong tool calling capabilities (needed for Task 2-3)

## Architecture

The agent will have the following components:

### 1. Configuration Loader
- Read environment variables from `.env.agent.secret`
- Variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
- Use `python-dotenv` to load `.env` files

### 2. LLM Client
- Use `openai` Python package (Qwen API is OpenAI-compatible)
- Send chat completion request with user question
- Parse the response to extract the answer

### 3. CLI Interface
- Parse command-line argument (the question)
- Call LLM client
- Output JSON to stdout
- Output debug info to stderr

### 4. Output Format
```json
{"answer": "<LLM response>", "tool_calls": []}
```

## Data Flow

```
Command line argument (question)
    ↓
agent.py reads .env.agent.secret
    ↓
Create OpenAI client with Qwen endpoint
    ↓
Send chat completion request
    ↓
Parse LLM response
    ↓
Format JSON output
    ↓
Print to stdout
```

## Error Handling

- Missing environment variables → exit with error to stderr
- API request failure → exit with error to stderr
- Timeout (>60s) → exit with error to stderr
- Invalid JSON → exit with error to stderr

## Testing Strategy

Create `tests/test_agent.py`:
- Run `agent.py` as subprocess with a test question
- Parse stdout as JSON
- Verify `answer` field exists and is non-empty
- Verify `tool_calls` field exists and is an array

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `.env.agent.secret` | Create | LLM configuration |
| `plans/task-1.md` | Create | This plan |
| `agent.py` | Create | Main agent CLI |
| `AGENT.md` | Create | Documentation |
| `tests/test_agent.py` | Create | Regression test |

## Dependencies

Add to `pyproject.toml`:
- `openai` — OpenAI-compatible API client
- `python-dotenv` — Load environment variables from `.env` file
