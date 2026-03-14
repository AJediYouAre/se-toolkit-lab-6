# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM and returns structured JSON answers. It serves as the foundation for the agentic system that will be extended with tools and an agentic loop in Tasks 2-3.

## LLM Provider

**Provider:** Qwen Code API (DashScope)

**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Available in Russia
- OpenAI-compatible API
- Strong tool calling capabilities

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Command Line   │ ──> │  agent.py    │ ──> │  LLM API    │ ──> │  JSON Output │
│  (question)     │     │  (CLI)       │     │  (Qwen)     │     │  (stdout)    │
└─────────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
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

### 2. LLM Client (`call_llm()`)

- Uses `httpx` to make HTTP requests to the LLM API
- Sends chat completion request with user question
- Parses the response to extract the answer
- Handles errors:
  - Timeout (>60s)
  - HTTP errors (4xx, 5xx)
  - Network errors
  - Invalid response format

### 3. CLI Interface (`main()`)

- Parses command-line argument (the question)
- Calls the configuration loader and LLM client
- Outputs JSON to stdout
- Outputs debug/progress info to stderr

## Input/Output

### Input

```bash
uv run agent.py "What does REST stand for?"
```

### Output (stdout)

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Debug Output (stderr)

```
Question: What does REST stand for?
Calling LLM at https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions...
Got response from LLM
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

2. Get your API key:
   - For Qwen Code: Run `qwen auth login` and get the token from `~/.qwen/oauth_creds.json`
   - Or use the DashScope API key from your Alibaba Cloud account

3. Edit `.env.agent.secret` and fill in the values

## Running the Agent

```bash
# Install dependencies
uv sync

# Run with a question
uv run agent.py "What is 2+2?"
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error to stderr |
| Missing environment variables | Exit with error to stderr |
| API timeout (>60s) | Exit with error to stderr |
| HTTP error (4xx, 5xx) | Exit with error to stderr, show response |
| Network error | Exit with error to stderr |
| Invalid API response | Exit with error to stderr |

## Exit Codes

- `0` — Success
- `1` — Error (configuration, network, API, parsing)

## Dependencies

- `httpx` — HTTP client for API requests
- `python-dotenv` — Load environment variables from `.env` file

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

The test verifies:
- Agent runs successfully
- Output is valid JSON
- `answer` field exists and is non-empty
- `tool_calls` field exists and is an array

## Future Extensions (Tasks 2-3)

- **Task 2:** Add tools (file system, API queries, etc.)
- **Task 3:** Add agentic loop for multi-step reasoning
