"""Agent module containing state, nodes, edges, and graph definitions."""

from .state import AgentState

# Lazy import for graph to avoid requiring langgraph at import time
def create_agent_graph():
    """Create the agent graph (lazy import)."""
    from .graph import create_agent_graph as _create_agent_graph
    return _create_agent_graph()

__all__ = ["AgentState", "create_agent_graph"]
