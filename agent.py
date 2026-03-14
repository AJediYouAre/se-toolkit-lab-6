#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    Debug info to stderr
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


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


def call_llm(question: str, config: dict[str, str]) -> str:
    """Call the LLM API and return the answer."""
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
        "messages": [
            {
                "role": "user",
                "content": question,
            }
        ],
        "temperature": 0.7,
    }
    
    print(f"Calling LLM at {url}...", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            
            print(f"Got response from LLM", file=sys.stderr)
            return answer
            
    except httpx.TimeoutException:
        print("Error: LLM request timed out (>60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error: Failed to parse LLM response: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    print(f"Question: {question}", file=sys.stderr)
    
    config = load_config()
    answer = call_llm(question, config)
    
    result = {
        "answer": answer,
        "tool_calls": [],
    }
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()
