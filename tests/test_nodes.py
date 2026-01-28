"""Unit tests for agent nodes."""

import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, '/home/user/security')

from src.agent.state import AgentState
from src.agent.nodes import context_analyzer, planner
from src.utils.helpers import extract_json_from_response, sanitize_markdown, merge_tech_stacks


class TestContextAnalyzer:
    """Tests for context_analyzer node."""

    def test_simple_api_no_discovery(self):
        """Test that simple API projects don't trigger discovery."""
        state: AgentState = {
            "context": {
                "project_type": "api_only",
                "tech_stack": {"backend": "FastAPI"},
                "security_topic": "JWT Authentication"
            }
        }

        result = context_analyzer(state)

        assert result["needs_discovery"] == False
        assert result["iteration_count"] == 0

    def test_oss_project_with_url_needs_discovery(self):
        """Test that OSS projects with URL but no tech stack need discovery."""
        state: AgentState = {
            "context": {
                "project_type": "opensource_project",
                "project_url": "https://github.com/example/repo",
                "tech_stack": {},
                "security_topic": "API Rate Limiting"
            }
        }

        result = context_analyzer(state)

        assert result["needs_discovery"] == True

    def test_oss_project_with_tech_stack_no_discovery(self):
        """Test that OSS projects with tech stack don't need discovery."""
        state: AgentState = {
            "context": {
                "project_type": "opensource_project",
                "project_url": "https://github.com/example/repo",
                "tech_stack": {"backend": "Spring Boot"},
                "security_topic": "API Rate Limiting"
            }
        }

        result = context_analyzer(state)

        assert result["needs_discovery"] == False


class TestHelpers:
    """Tests for helper functions."""

    def test_extract_json_from_code_block(self):
        """Test JSON extraction from markdown code blocks."""
        response = '''Here is the result:
```json
{"key": "value", "number": 42}
```
'''
        result = extract_json_from_response(response)
        assert result == {"key": "value", "number": 42}

    def test_extract_json_array(self):
        """Test JSON array extraction."""
        response = '["item1", "item2", "item3"]'
        result = extract_json_from_response(response)
        assert result == ["item1", "item2", "item3"]

    def test_extract_json_invalid(self):
        """Test that invalid JSON raises ValueError."""
        response = "This is not JSON at all"
        with pytest.raises(ValueError):
            extract_json_from_response(response)

    def test_sanitize_markdown_removes_excess_newlines(self):
        """Test that excessive newlines are reduced."""
        markdown = "Line 1\n\n\n\n\n\nLine 2"
        result = sanitize_markdown(markdown)
        assert "\n\n\n\n" not in result

    def test_merge_tech_stacks_user_precedence(self):
        """Test that user values take precedence in merge."""
        user = {"backend": "FastAPI", "frontend": None}
        discovered = {"backend": "Django", "frontend": "React", "database": "PostgreSQL"}

        result = merge_tech_stacks(user, discovered)

        assert result["backend"] == "FastAPI"  # User value
        assert result["frontend"] == "React"  # Discovered value (user was None)
        assert result["database"] == "PostgreSQL"  # Discovered value


class TestPlanner:
    """Tests for planner node."""

    @patch('src.agent.nodes.claude')
    def test_planner_generates_research_plan(self, mock_claude):
        """Test that planner generates a research plan."""
        mock_claude.generate_json.return_value = '["query 1", "query 2", "query 3"]'

        state: AgentState = {
            "context": {
                "project_type": "api_only",
                "tech_stack": {"backend": "FastAPI"},
                "security_topic": "JWT Authentication"
            }
        }

        result = planner(state)

        assert "research_plan" in result
        assert len(result["research_plan"]) > 0

    @patch('src.agent.nodes.claude')
    def test_planner_fallback_on_error(self, mock_claude):
        """Test that planner uses fallback plan on error."""
        mock_claude.generate_json.side_effect = Exception("API Error")

        state: AgentState = {
            "context": {
                "project_type": "api_only",
                "tech_stack": {"backend": "FastAPI"},
                "security_topic": "JWT Authentication"
            },
            "errors": []
        }

        result = planner(state)

        assert "research_plan" in result
        assert len(result["research_plan"]) > 0
        assert "errors" in result
        assert len(result["errors"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
