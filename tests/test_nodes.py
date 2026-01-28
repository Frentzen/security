"""Unit tests for agent nodes."""

import json
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, '/home/user/security')

from src.agent.state import AgentState
from src.agent.nodes import context_analyzer, query_parser, planner
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


class TestQueryParser:
    """Tests for query_parser node."""

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_parses_natural_language_query(self, mock_claude, mock_tavily):
        """Test parsing a natural language query into structured context."""
        mock_claude.generate_json.return_value = json.dumps({
            "security_topic": "JWE JSON Payload Encryption",
            "project_type": "microservice",
            "tech_stack": {
                "backend": "Spring Boot",
                "frontend": None,
                "database": None,
                "deployment": "AKS"
            },
            "project_name": None,
            "project_url": None,
            "requirements": {
                "additional_context": "Azure environment with APIM and Application Gateway",
                "cloud_provider": "Azure",
                "infrastructure_components": ["APIM", "Application Gateway"]
            }
        })

        state: AgentState = {
            "context": {
                "raw_query": "I need to use JWE to encrypt my json payloads in my springboot microservices deployed in AKS exposed through APIM and AppGw all in Azure"
            }
        }

        result = query_parser(state)

        assert result["context"]["security_topic"] == "JWE JSON Payload Encryption"
        assert result["context"]["project_type"] == "microservice"
        assert result["context"]["tech_stack"]["backend"] == "Spring Boot"
        assert result["context"]["tech_stack"]["deployment"] == "AKS"
        assert result["context"]["requirements"]["cloud_provider"] == "Azure"
        assert result["needs_query_parsing"] == False

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_user_provided_values_take_precedence(self, mock_claude, mock_tavily):
        """Test that explicit user values override parsed values."""
        mock_claude.generate_json.return_value = json.dumps({
            "security_topic": "JWT Authentication",
            "project_type": "api_only",
            "tech_stack": {
                "backend": "Django",
                "frontend": None,
                "database": "SQLite",
                "deployment": "Docker"
            },
            "project_name": None,
            "project_url": None,
            "requirements": {}
        })

        state: AgentState = {
            "context": {
                "raw_query": "I want JWT auth in my app",
                "tech_stack": {"backend": "FastAPI"},  # User override
                "project_type": "microservice",  # User override
            }
        }

        result = query_parser(state)

        # User-provided values should win
        assert result["context"]["tech_stack"]["backend"] == "FastAPI"
        assert result["context"]["project_type"] == "microservice"
        # Parsed values fill gaps
        assert result["context"]["tech_stack"]["deployment"] == "Docker"
        assert result["context"]["security_topic"] == "JWT Authentication"

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_handles_parsing_failure_gracefully(self, mock_claude, mock_tavily):
        """Test graceful fallback when Claude fails to parse."""
        mock_claude.generate_json.side_effect = Exception("API Error")

        state: AgentState = {
            "context": {
                "raw_query": "Something about security"
            },
            "errors": []
        }

        result = query_parser(state)

        assert result["needs_query_parsing"] == False
        assert len(result["errors"]) > 0

    @patch('src.agent.nodes.claude')
    def test_empty_query_skips_parsing(self, mock_claude):
        """Test that empty query skips parsing."""
        state: AgentState = {
            "context": {
                "raw_query": ""
            }
        }

        result = query_parser(state)

        assert result["needs_query_parsing"] == False
        mock_claude.generate_json.assert_not_called()

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_handles_list_response_gracefully(self, mock_claude, mock_tavily):
        """Test graceful handling when Claude returns a JSON array instead of object."""
        # Claude sometimes returns a list instead of an object
        mock_claude.generate_json.return_value = '["item1", "item2"]'

        state: AgentState = {
            "context": {
                "raw_query": "I need JWT authentication"
            },
            "errors": []
        }

        result = query_parser(state)

        # Should handle gracefully and record error
        assert result["needs_query_parsing"] == False
        assert len(result["errors"]) > 0
        assert "Expected JSON object" in result["errors"][0] or "list" in result["errors"][0]


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

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_planner_generates_research_plan(self, mock_claude, mock_tavily):
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

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_planner_fallback_on_error(self, mock_claude, mock_tavily):
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
