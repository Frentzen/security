"""Conditional edge functions for the security research agent."""

import logging
from typing import Literal

import sys
sys.path.insert(0, '/home/user/security')

from src.agent.state import AgentState
from config import MAX_ITERATIONS

logger = logging.getLogger(__name__)


def route_after_context_analysis(state: AgentState) -> Literal["repository_analyzer", "planner"]:
    """Route after context analysis based on discovery needs.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    needs_discovery = state.get("needs_discovery", False)

    if needs_discovery:
        logger.info("Routing to repository analyzer for discovery")
        return "repository_analyzer"
    else:
        logger.info("Routing directly to planner")
        return "planner"


def route_after_repository_analysis(state: AgentState) -> Literal["tech_stack_discovery", "planner"]:
    """Route after repository analysis.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    repository_analysis = state.get("repository_analysis")

    if repository_analysis:
        logger.info("Routing to tech stack discovery")
        return "tech_stack_discovery"
    else:
        logger.info("Repository analysis failed, routing to planner with available context")
        return "planner"


def route_after_validation(state: AgentState) -> Literal["revision", "report_generator"]:
    """Route after validation based on feedback severity.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    validation_feedback = state.get("validation_feedback", [])
    iteration_count = state.get("iteration_count", 0)

    # Check if we've exceeded max iterations
    if iteration_count >= MAX_ITERATIONS:
        logger.info(f"Max iterations ({MAX_ITERATIONS}) reached, generating final report")
        return "report_generator"

    # Count critical and important issues
    critical_issues = [f for f in validation_feedback if f.get("severity") == "critical"]
    important_issues = [f for f in validation_feedback if f.get("severity") == "important"]

    # Revise if there are critical issues or multiple important issues
    if critical_issues or len(important_issues) >= 2:
        logger.info(f"Found {len(critical_issues)} critical, {len(important_issues)} important issues - revising")
        return "revision"

    logger.info("Validation passed, generating final report")
    return "report_generator"


def route_after_revision(state: AgentState) -> Literal["validator", "report_generator"]:
    """Route after revision to re-validate or finalize.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    iteration_count = state.get("iteration_count", 0)

    # If we've hit max iterations, go straight to report
    if iteration_count >= MAX_ITERATIONS:
        logger.info(f"Max iterations ({MAX_ITERATIONS}) reached after revision")
        return "report_generator"

    # Re-validate after revision
    logger.info("Re-validating after revision")
    return "validator"


def should_continue_research(state: AgentState) -> bool:
    """Check if more research is needed.

    Args:
        state: Current agent state

    Returns:
        True if more research needed
    """
    search_results = state.get("search_results", [])
    synthesized_knowledge = state.get("synthesized_knowledge")

    # Need more research if no results or synthesis failed
    if not search_results:
        return True

    if not synthesized_knowledge:
        return True

    # Check if we have enough information
    if len(search_results) < 5:
        return True

    return False
