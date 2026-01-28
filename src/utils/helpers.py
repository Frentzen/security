"""Utility functions for the security research agent."""

import json
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_search_results(results: list[dict]) -> str:
    """Format search results for use in prompts.

    Args:
        results: List of search result dictionaries

    Returns:
        Formatted string representation
    """
    if not results:
        return "No search results available."

    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"""
Result {i}:
- Query: {result.get('query', 'N/A')}
- Title: {result.get('title', 'N/A')}
- URL: {result.get('url', 'N/A')}
- Content: {result.get('snippet', 'N/A')}
""")
    return "\n".join(formatted)


def extract_json_from_response(response: str) -> Any:
    """Extract JSON from a Claude response that may contain markdown code blocks.

    Args:
        response: Raw response string from Claude

    Returns:
        Parsed JSON object

    Raises:
        ValueError: If no valid JSON found
    """
    # Try to find JSON in code blocks first
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(code_block_pattern, response)

    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try to find raw JSON (array or object)
    json_patterns = [
        r'\[[\s\S]*\]',  # Array
        r'\{[\s\S]*\}',  # Object
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, response)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    # Last resort: try the whole response
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        raise ValueError(f"Could not extract valid JSON from response: {response[:200]}...")


def sanitize_markdown(markdown: str) -> str:
    """Clean up and sanitize markdown output.

    Args:
        markdown: Raw markdown string

    Returns:
        Cleaned markdown string
    """
    if not markdown:
        return ""

    # Remove excessive blank lines (more than 2 consecutive)
    markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)

    # Ensure code blocks have language tags where obvious
    def add_language_tag(match):
        code = match.group(1)
        if code.strip().startswith('import ') or 'def ' in code or 'class ' in code:
            return f'```python\n{code}```'
        elif code.strip().startswith('const ') or code.strip().startswith('function ') or 'import ' in code and 'from' not in code:
            return f'```javascript\n{code}```'
        elif code.strip().startswith('FROM ') or code.strip().startswith('RUN '):
            return f'```dockerfile\n{code}```'
        elif code.strip().startswith('version:') or code.strip().startswith('services:'):
            return f'```yaml\n{code}```'
        return match.group(0)

    # Only process code blocks without language tags
    markdown = re.sub(r'```\n([\s\S]*?)```', add_language_tag, markdown)

    # Ensure proper spacing around headers
    markdown = re.sub(r'([^\n])\n(#{1,6} )', r'\1\n\n\2', markdown)

    return markdown.strip()


def merge_tech_stacks(user_stack: dict, discovered_stack: dict) -> dict:
    """Merge user-provided tech stack with discovered tech stack.

    User-provided values take precedence.

    Args:
        user_stack: Tech stack provided by user
        discovered_stack: Tech stack discovered from repository

    Returns:
        Merged tech stack dictionary
    """
    merged = {**discovered_stack}

    for key, value in user_stack.items():
        if value is not None and value != "":
            merged[key] = value

    return merged


def truncate_text(text: str, max_length: int = 2000, suffix: str = "...") -> str:
    """Truncate text to maximum length while preserving word boundaries.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')

    if last_space > max_length * 0.8:  # Only break at space if it's reasonably close
        truncated = truncated[:last_space]

    return truncated + suffix


def validate_state(state: dict, required_fields: list[str]) -> list[str]:
    """Validate that required fields are present in state.

    Args:
        state: Current agent state
        required_fields: List of required field names

    Returns:
        List of missing field names
    """
    missing = []
    for field in required_fields:
        if field not in state or state[field] is None:
            missing.append(field)
        elif isinstance(state[field], (list, dict, str)) and len(state[field]) == 0:
            missing.append(field)
    return missing
