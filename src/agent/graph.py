"""LangGraph workflow definition for the security research agent."""

import logging
from langgraph.graph import StateGraph, END

import sys
sys.path.insert(0, '/home/user/security')

from src.agent.state import AgentState
from src.agent.nodes import (
    query_parser,
    context_analyzer,
    repository_analyzer,
    tech_stack_discovery,
    planner,
    researcher,
    synthesizer,
    architect,
    validator,
    revision,
    report_generator,
)
from src.agent.edges import (
    route_entry_point,
    route_after_context_analysis,
    route_after_repository_analysis,
    route_after_validation,
    route_after_revision,
)

logger = logging.getLogger(__name__)


def create_agent_graph() -> StateGraph:
    """Create and compile the security research agent graph.

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Creating agent graph")

    # Create the graph with state schema
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("entry_router", lambda state: state)  # pass-through for routing
    graph.add_node("query_parser", query_parser)
    graph.add_node("context_analyzer", context_analyzer)
    graph.add_node("repository_analyzer", repository_analyzer)
    graph.add_node("tech_stack_discovery", tech_stack_discovery)
    graph.add_node("planner", planner)
    graph.add_node("researcher", researcher)
    graph.add_node("synthesizer", synthesizer)
    graph.add_node("architect", architect)
    graph.add_node("validator", validator)
    graph.add_node("revision", revision)
    graph.add_node("report_generator", report_generator)

    # Set entry point - routes to query parser or context analyzer
    graph.set_entry_point("entry_router")

    graph.add_conditional_edges(
        "entry_router",
        route_entry_point,
        {
            "query_parser": "query_parser",
            "context_analyzer": "context_analyzer",
        }
    )

    # After query parsing, always go to context analysis
    graph.add_edge("query_parser", "context_analyzer")

    # Add conditional edge after context analysis
    graph.add_conditional_edges(
        "context_analyzer",
        route_after_context_analysis,
        {
            "repository_analyzer": "repository_analyzer",
            "planner": "planner",
        }
    )

    # Add conditional edge after repository analysis
    graph.add_conditional_edges(
        "repository_analyzer",
        route_after_repository_analysis,
        {
            "tech_stack_discovery": "tech_stack_discovery",
            "planner": "planner",
        }
    )

    # Tech stack discovery always goes to planner
    graph.add_edge("tech_stack_discovery", "planner")

    # Linear flow from planner through synthesis
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "synthesizer")
    graph.add_edge("synthesizer", "architect")

    # Architect goes to validator
    graph.add_edge("architect", "validator")

    # Conditional edge after validation
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "revision": "revision",
            "report_generator": "report_generator",
        }
    )

    # Conditional edge after revision
    graph.add_conditional_edges(
        "revision",
        route_after_revision,
        {
            "validator": "validator",
            "report_generator": "report_generator",
        }
    )

    # Report generator ends the graph
    graph.add_edge("report_generator", END)

    # Compile the graph
    compiled = graph.compile()
    logger.info("Agent graph compiled successfully")

    return compiled


def run_agent(input_context: dict) -> str:
    """Run the security research agent with the given input.

    Args:
        input_context: Input context dictionary matching InputContext schema

    Returns:
        Final markdown report
    """
    # Determine if we need to parse a raw query
    has_raw_query = bool(input_context.get("raw_query"))
    has_security_topic = bool(input_context.get("security_topic"))
    needs_query_parsing = has_raw_query and not has_security_topic

    if needs_query_parsing:
        logger.info(f"Running agent with raw query: {input_context.get('raw_query', '')[:80]}...")
    else:
        logger.info(f"Running agent for topic: {input_context.get('security_topic', 'Unknown')}")

    # Create initial state
    initial_state: AgentState = {
        "context": input_context,
        "needs_discovery": False,
        "needs_query_parsing": needs_query_parsing,
        "repository_analysis": None,
        "research_plan": [],
        "search_results": [],
        "synthesized_knowledge": None,
        "architecture_draft": "",
        "validation_feedback": [],
        "final_report": "",
        "iteration_count": 0,
        "errors": [],
    }

    # Create and run the graph
    graph = create_agent_graph()
    final_state = graph.invoke(initial_state)

    # Extract and return the final report
    final_report = final_state.get("final_report", "")

    if not final_report:
        logger.error("No final report generated")
        return "Error: Failed to generate implementation guide"

    logger.info(f"Agent completed. Report length: {len(final_report)} chars")
    return final_report
