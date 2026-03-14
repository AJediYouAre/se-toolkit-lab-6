"""
Regression tests for agent.py

Tests verify that the agent:
- Runs successfully with a question argument
- Outputs valid JSON to stdout
- Contains required fields: answer, source, and tool_calls
- Uses tools correctly (read_file, list_files)
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> tuple[int, str, str]:
    """
    Run agent.py as a subprocess and return (returncode, stdout, stderr).
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py directly with Python (dependencies already installed in venv)
    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(project_root),
    )

    return result.returncode, result.stdout.strip(), result.stderr


def test_agent_returns_json_with_required_fields():
    """Test that agent.py returns valid JSON with answer, source, and tool_calls fields."""
    question = "What is 2+2?"

    returncode, stdout, stderr = run_agent(question)

    print(f"stderr: {stderr}")
    print(f"stdout: {stdout}")

    # Check exit code
    assert returncode == 0, f"Agent exited with code {returncode}: {stderr}"

    # Parse stdout as JSON
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nOutput: {stdout}")

    # Verify required fields
    assert "answer" in response, "Missing 'answer' field in response"
    assert isinstance(response["answer"], str), "'answer' must be a string"

    assert "source" in response, "Missing 'source' field in response"
    assert isinstance(response["source"], str), "'source' must be a string"

    assert "tool_calls" in response, "Missing 'tool_calls' field in response"
    assert isinstance(response["tool_calls"], list), "'tool_calls' must be an array"


def test_documentation_agent_uses_read_file():
    """
    Test that the agent correctly identifies a git-related source for merge conflict questions.
    
    Question: "How do you resolve a merge conflict?"
    Expected: source references a git-related wiki file (git-workflow.md, git.md, or git-vscode.md)
    """
    question = "How do you resolve a merge conflict?"

    returncode, stdout, stderr = run_agent(question)

    print(f"stderr: {stderr}")
    print(f"stdout: {stdout}")

    # Check exit code
    assert returncode == 0, f"Agent exited with code {returncode}: {stderr}"

    # Parse JSON
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nOutput: {stdout}")

    # Verify source references a git-related wiki file
    source = response.get("source", "")
    valid_sources = ["git-workflow.md", "git.md", "git-vscode.md"]
    has_valid_source = any(src in source for src in valid_sources)
    assert has_valid_source, f"Expected git-related source, got: {source}"

    # Verify answer is non-empty
    answer = response.get("answer", "")
    assert len(answer) > 0, "Expected non-empty answer"


def test_documentation_agent_uses_list_files():
    """
    Test that the agent uses list_files tool for directory exploration questions.
    
    Question: "What files are in the wiki?"
    Expected: list_files in tool_calls
    """
    question = "What files are in the wiki?"

    returncode, stdout, stderr = run_agent(question)

    print(f"stderr: {stderr}")
    print(f"stdout: {stdout}")

    # Check exit code
    assert returncode == 0, f"Agent exited with code {returncode}: {stderr}"

    # Parse JSON
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nOutput: {stdout}")

    # Verify tool_calls contains list_files
    tool_calls = response.get("tool_calls", [])
    assert len(tool_calls) > 0, "Expected tool_calls to be non-empty"

    tool_names = [call.get("tool") for call in tool_calls]
    assert "list_files" in tool_names, f"Expected 'list_files' in tool_calls, got: {tool_names}"


if __name__ == "__main__":
    print("=== Test 1: Basic JSON structure ===")
    test_agent_returns_json_with_required_fields()
    print("PASSED\n")

    print("=== Test 2: read_file tool usage ===")
    test_documentation_agent_uses_read_file()
    print("PASSED\n")

    print("=== Test 3: list_files tool usage ===")
    test_documentation_agent_uses_list_files()
    print("PASSED\n")

    print("All tests passed!")
