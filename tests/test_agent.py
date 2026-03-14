"""
Regression tests for agent.py

Tests verify that the agent:
- Runs successfully with a question argument
- Outputs valid JSON to stdout
- Contains required fields: answer and tool_calls
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_returns_json_with_required_fields():
    """Test that agent.py returns valid JSON with answer and tool_calls fields."""
    # Path to agent.py in project root
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"
    
    # Test question
    question = "What is 2+2?"
    
    # Run agent.py as subprocess
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,  # Give extra time for LLM response
    )
    
    # Print stderr for debugging
    print(f"stderr: {result.stderr}")
    
    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"
    
    # Parse stdout as JSON
    stdout = result.stdout.strip()
    print(f"stdout: {stdout}")
    
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nOutput: {stdout}")
    
    # Verify 'answer' field exists and is non-empty
    assert "answer" in response, "Missing 'answer' field in response"
    assert isinstance(response["answer"], str), "'answer' must be a string"
    assert len(response["answer"]) > 0, "'answer' must be non-empty"
    
    # Verify 'tool_calls' field exists and is an array
    assert "tool_calls" in response, "Missing 'tool_calls' field in response"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"


if __name__ == "__main__":
    test_agent_returns_json_with_required_fields()
    print("Test passed!")
