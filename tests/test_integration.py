"""Integration tests for the security research agent."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, '/home/user/security')

from src.agent.graph import create_agent_graph, run_agent
from src.agent.edges import (
    route_after_context_analysis,
    route_after_validation,
    route_after_revision,
)


class TestEdgeRouting:
    """Tests for conditional edge routing."""

    def test_route_to_discovery_for_oss(self):
        """Test routing to discovery for OSS projects."""
        state = {"needs_discovery": True}
        result = route_after_context_analysis(state)
        assert result == "repository_analyzer"

    def test_route_to_planner_directly(self):
        """Test routing directly to planner when no discovery needed."""
        state = {"needs_discovery": False}
        result = route_after_context_analysis(state)
        assert result == "planner"

    def test_route_to_revision_on_critical_issues(self):
        """Test routing to revision when critical issues found."""
        state = {
            "validation_feedback": [
                {"issue": "Missing auth", "severity": "critical", "suggestion": "Add auth"}
            ],
            "iteration_count": 0
        }
        result = route_after_validation(state)
        assert result == "revision"

    def test_route_to_report_when_no_issues(self):
        """Test routing to report generator when validation passes."""
        state = {
            "validation_feedback": [],
            "iteration_count": 0
        }
        result = route_after_validation(state)
        assert result == "report_generator"

    def test_route_to_report_at_max_iterations(self):
        """Test routing to report at max iterations regardless of issues."""
        state = {
            "validation_feedback": [
                {"issue": "Critical issue", "severity": "critical", "suggestion": "Fix it"}
            ],
            "iteration_count": 3
        }
        result = route_after_validation(state)
        assert result == "report_generator"

    def test_route_after_revision_revalidates(self):
        """Test that revision routes back to validator."""
        state = {"iteration_count": 1}
        result = route_after_revision(state)
        assert result == "validator"

    def test_route_after_revision_stops_at_max(self):
        """Test that revision stops at max iterations."""
        state = {"iteration_count": 3}
        result = route_after_revision(state)
        assert result == "report_generator"


class TestGraphCreation:
    """Tests for graph creation."""

    def test_graph_compiles(self):
        """Test that the graph compiles successfully."""
        graph = create_agent_graph()
        assert graph is not None

    def test_graph_has_entry_point(self):
        """Test that graph has proper entry point."""
        graph = create_agent_graph()
        # LangGraph compiled graphs should be invokable
        assert hasattr(graph, 'invoke')


class TestAgentIntegration:
    """Integration tests for the full agent."""

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_simple_flow_generates_report(self, mock_claude, mock_tavily):
        """Test that a simple flow generates a final report."""
        # Mock Claude responses
        mock_claude.generate_json.side_effect = [
            '["JWT best practices", "FastAPI JWT tutorial"]',  # Planner
            '{"prerequisites": ["python-jose"], "implementation_steps": []}',  # Synthesizer
            '{"issues": [], "overall_quality": "good"}',  # Validator
        ]
        mock_claude.generate.return_value = "# JWT Implementation Guide\n\nThis is a test guide."

        # Mock Tavily responses
        mock_tavily.search_parallel.return_value = [
            {"query": "JWT", "url": "https://owasp.org/jwt", "title": "OWASP JWT", "snippet": "JWT info"}
        ]

        context = {
            "project_type": "api_only",
            "tech_stack": {"backend": "FastAPI"},
            "security_topic": "JWT Authentication"
        }

        report = run_agent(context)

        assert report is not None
        assert len(report) > 0
        assert "JWT" in report or "Implementation" in report

    @patch('src.agent.nodes.tavily')
    @patch('src.agent.nodes.claude')
    def test_discovery_flow_for_oss(self, mock_claude, mock_tavily):
        """Test that OSS projects trigger discovery flow."""
        # Mock responses for discovery
        mock_tavily.search.return_value = [
            {"query": "repo", "url": "https://github.com/test", "title": "Test Repo", "snippet": "Python Flask app"}
        ]

        mock_claude.generate_json.side_effect = [
            '{"languages": ["Python"], "frameworks": ["Flask"], "detected_tech_stack": {"backend": "Flask"}}',  # Repo analyzer
            '["API rate limiting best practices"]',  # Planner
            '{"prerequisites": [], "implementation_steps": []}',  # Synthesizer
            '{"issues": [], "overall_quality": "good"}',  # Validator
        ]
        mock_claude.generate.return_value = "# Rate Limiting Guide\n\nThis is a test guide."

        mock_tavily.search_parallel.return_value = [
            {"query": "rate limit", "url": "https://example.com", "title": "Rate Limiting", "snippet": "Info"}
        ]

        context = {
            "project_type": "opensource_project",
            "project_url": "https://github.com/test/repo",
            "tech_stack": {},
            "security_topic": "API Rate Limiting"
        }

        report = run_agent(context)

        assert report is not None
        # Discovery should have been triggered
        mock_tavily.search.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
