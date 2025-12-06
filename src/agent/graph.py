import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from .state import DatingState
from .nodes.load_context import load_context_node
from .nodes.router import classify_intent_node, route_by_intent
from .nodes.onboarding import onboarding_node
from .nodes.matching import matching_node
from .nodes.mentor import mentor_node
from .nodes.general import general_node


log = logging.getLogger("orbit.agent.graph")


def create_dating_graph(store, llm, client):
    """Create and compile the dating agent graph."""

    # Create the graph
    workflow = StateGraph(DatingState)

    # Add nodes
    workflow.add_node("load_context", lambda state: load_context_node(state, store))
    workflow.add_node("classify_intent", lambda state: classify_intent_node(state, llm))
    workflow.add_node("onboarding", lambda state: onboarding_node(state, store, llm))
    workflow.add_node("matching", lambda state: matching_node(state, store, llm, client))
    workflow.add_node("mentor", lambda state: mentor_node(state, store, llm))
    workflow.add_node("general", lambda state: general_node(state))

    # Set entry point
    workflow.set_entry_point("load_context")

    # Add edges
    workflow.add_edge("load_context", "classify_intent")

    # Conditional routing from classify_intent
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "onboarding": "onboarding",
            "matching": "matching",
            "mentor": "mentor",
            "general": "general"
        }
    )

    # All nodes end after execution
    workflow.add_edge("onboarding", END)
    workflow.add_edge("matching", END)
    workflow.add_edge("mentor", END)
    workflow.add_edge("general", END)

    # Compile the graph
    app = workflow.compile()

    log.info("Dating agent graph compiled successfully")
    return app
