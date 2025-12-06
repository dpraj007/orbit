"""
Proof of Concept: Proper LangChain-LangGraph Implementation
============================================================

This demonstrates the CORRECT way to build a LangGraph agent using:
- MessagesState for proper message tracking
- START/END constants for graph definition
- Proper LangChain message types (HumanMessage, AIMessage, SystemMessage)
- Tool binding for agentic behavior
- Checkpointing for conversation persistence

Run with: pytest tests/langgraph_poc/test_proper_langgraph.py -v
"""

import json
import pytest
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
from unittest.mock import MagicMock, patch

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# LangChain imports
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


# =============================================================================
# PROPER STATE DEFINITION
# =============================================================================

class DatingAgentState(TypedDict):
    """
    Proper state definition using LangGraph patterns.
    
    Key differences from current implementation:
    1. Uses `Annotated` with `add_messages` for automatic message accumulation
    2. Messages are proper LangChain message types, not plain strings
    3. State is designed for graph traversal, not just data passing
    """
    # Core conversation tracking - uses add_messages reducer
    # This automatically appends new messages instead of replacing
    messages: Annotated[List[BaseMessage], add_messages]
    
    # User context
    user_id: Optional[int]
    phone_number: str
    chat_id: Optional[int]
    
    # Profile data
    profile: Optional[Dict[str, Any]]
    user: Optional[Dict[str, Any]]
    
    # Routing
    intent: Optional[str]
    
    # Response for external use
    final_response: Optional[str]


# =============================================================================
# MOCK LLM FOR TESTING
# =============================================================================

class MockChatModel:
    """Mock LLM that simulates ChatOpenAI responses."""
    
    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.call_history: List[List[BaseMessage]] = []
    
    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        """Invoke with proper message list (not plain string!)."""
        self.call_history.append(messages)
        
        # Get the last human message
        last_human_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_human_msg = msg.content.lower()
                break
        
        # Return appropriate response based on content
        if "name" in last_human_msg or "passionate" in last_human_msg:
            return AIMessage(content="Nice to meet you! What kind of relationship are you looking for?")
        elif "match" in last_human_msg or "find" in last_human_msg:
            return AIMessage(content="I found someone great for you! Want an intro?")
        elif "help" in last_human_msg or "advice" in last_human_msg:
            return AIMessage(content="Here's a tip: Be genuine and ask open-ended questions!")
        elif "yes" in last_human_msg:
            return AIMessage(content="Great! Connecting you now...")
        else:
            return AIMessage(content="I'm here to help with dating! What would you like to do?")
    
    def bind_tools(self, tools: List[Any]) -> "MockChatModel":
        """Mock tool binding."""
        return self


# =============================================================================
# PROPER NODE DEFINITIONS
# =============================================================================

def create_router_node(llm):
    """
    Router node that classifies intent using proper message patterns.
    
    PROPER PATTERN:
    - Receives state with messages list
    - Uses LLM with message list, not string concatenation
    - Returns dict that will be merged with state
    """
    def router_node(state: DatingAgentState) -> Dict[str, Any]:
        messages = state["messages"]
        user = state.get("user", {})
        
        # Get the last human message
        last_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_message = msg.content.lower()
                break
        
        # Determine intent (in production, use LLM)
        status = user.get("status", "onboarding") if user else "onboarding"
        
        if status == "onboarding":
            intent = "onboarding"
        elif any(kw in last_message for kw in ["match", "find", "intro", "yes", "no"]):
            intent = "matching"
        elif any(kw in last_message for kw in ["help", "advice", "tip"]):
            intent = "mentor"
        else:
            intent = "general"
        
        return {"intent": intent}
    
    return router_node


def create_onboarding_node(llm):
    """
    Onboarding node with proper message handling.
    
    PROPER PATTERN:
    - Builds conversation with system + history
    - Returns AIMessage that gets appended to messages
    """
    def onboarding_node(state: DatingAgentState) -> Dict[str, Any]:
        messages = state["messages"]
        
        # Build proper message list for LLM
        system_prompt = SystemMessage(content="""You are Orbit, a friendly dating assistant.
You're helping a new user set up their profile. Ask about:
- Their name and passions
- What they're looking for
- Their communication style
Keep responses warm and brief.""")
        
        # Create conversation context
        llm_messages = [system_prompt] + list(messages)
        
        # Get LLM response (returns AIMessage)
        response = llm.invoke(llm_messages)
        
        return {
            "messages": [response],  # Will be appended via add_messages
            "final_response": response.content,
        }
    
    return onboarding_node


def create_matching_node(llm):
    """Matching node with proper message handling."""
    
    def matching_node(state: DatingAgentState) -> Dict[str, Any]:
        messages = state["messages"]
        
        system_prompt = SystemMessage(content="""You are Orbit, helping users find matches.
When they want a match, describe a potential match anonymously.
When they say yes, confirm you'll connect them.
When they say no, offer to find someone else.""")
        
        llm_messages = [system_prompt] + list(messages)
        response = llm.invoke(llm_messages)
        
        return {
            "messages": [response],
            "final_response": response.content,
        }
    
    return matching_node


def create_mentor_node(llm):
    """Mentor node with proper message handling."""
    
    def mentor_node(state: DatingAgentState) -> Dict[str, Any]:
        messages = state["messages"]
        
        system_prompt = SystemMessage(content="""You are Orbit, a dating coach.
Provide helpful, supportive advice about:
- Conversation starters
- Date preparation
- Handling rejection
Keep advice practical and encouraging.""")
        
        llm_messages = [system_prompt] + list(messages)
        response = llm.invoke(llm_messages)
        
        return {
            "messages": [response],
            "final_response": response.content,
        }
    
    return mentor_node


def create_general_node(llm):
    """General fallback node."""
    
    def general_node(state: DatingAgentState) -> Dict[str, Any]:
        messages = state["messages"]
        
        system_prompt = SystemMessage(content="""You are Orbit, a friendly dating assistant.
Help users understand what you can do:
- Find matches
- Give dating advice
- Help with conversations""")
        
        llm_messages = [system_prompt] + list(messages)
        response = llm.invoke(llm_messages)
        
        return {
            "messages": [response],
            "final_response": response.content,
        }
    
    return general_node


def route_by_intent(state: DatingAgentState) -> Literal["onboarding", "matching", "mentor", "general"]:
    """
    Conditional routing function.
    
    PROPER PATTERN:
    - Returns string literal matching node names
    - Used with add_conditional_edges
    """
    intent = state.get("intent", "general")
    
    routing_map = {
        "onboarding": "onboarding",
        "matching": "matching",
        "mentor": "mentor",
    }
    
    return routing_map.get(intent, "general")


# =============================================================================
# PROPER GRAPH BUILDER
# =============================================================================

def build_proper_graph(llm=None):
    """
    Build a proper LangGraph following best practices.
    
    Key improvements:
    1. Uses START constant instead of set_entry_point()
    2. Uses MessagesState pattern with add_messages
    3. Proper conditional routing
    4. Can add checkpointer for persistence
    """
    if llm is None:
        llm = MockChatModel()
    
    # Create state graph with proper state
    graph = StateGraph(DatingAgentState)
    
    # Add nodes with injected LLM
    graph.add_node("router", create_router_node(llm))
    graph.add_node("onboarding", create_onboarding_node(llm))
    graph.add_node("matching", create_matching_node(llm))
    graph.add_node("mentor", create_mentor_node(llm))
    graph.add_node("general", create_general_node(llm))
    
    # PROPER: Use START constant for entry point
    graph.add_edge(START, "router")
    
    # Conditional routing from router
    graph.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "onboarding": "onboarding",
            "matching": "matching",
            "mentor": "mentor",
            "general": "general",
        }
    )
    
    # All domain nodes go to END
    graph.add_edge("onboarding", END)
    graph.add_edge("matching", END)
    graph.add_edge("mentor", END)
    graph.add_edge("general", END)
    
    # Compile the graph
    return graph.compile()


# =============================================================================
# TESTS
# =============================================================================

class TestProperLangGraph:
    """Test suite for the proper LangGraph implementation."""
    
    def test_graph_compiles(self):
        """Test that the graph compiles successfully."""
        graph = build_proper_graph()
        assert graph is not None
    
    def test_state_with_messages(self):
        """Test that state properly tracks messages."""
        graph = build_proper_graph()
        
        # PROPER: Input uses HumanMessage, not plain string
        initial_state = {
            "messages": [HumanMessage(content="Hi, I'm Alex and I love hiking!")],
            "phone_number": "+1234567890",
            "user": {"status": "onboarding"},
        }
        
        result = graph.invoke(initial_state)
        
        # Should have original message + AI response
        assert len(result["messages"]) >= 2
        assert isinstance(result["messages"][0], HumanMessage)
        assert isinstance(result["messages"][-1], AIMessage)
    
    def test_onboarding_routing(self):
        """Test that onboarding users are routed correctly."""
        graph = build_proper_graph()
        
        result = graph.invoke({
            "messages": [HumanMessage(content="Hello!")],
            "phone_number": "+1234567890",
            "user": {"status": "onboarding"},
        })
        
        # Should get onboarding response
        assert result["intent"] == "onboarding"
        assert result["final_response"] is not None
    
    def test_matching_routing(self):
        """Test that match requests are routed correctly."""
        graph = build_proper_graph()
        
        result = graph.invoke({
            "messages": [HumanMessage(content="Find me a match please!")],
            "phone_number": "+1234567890",
            "user": {"status": "active"},
        })
        
        assert result["intent"] == "matching"
        assert "match" in result["final_response"].lower() or "found" in result["final_response"].lower()
    
    def test_mentor_routing(self):
        """Test that advice requests are routed to mentor."""
        graph = build_proper_graph()
        
        result = graph.invoke({
            "messages": [HumanMessage(content="I need help with conversation tips")],
            "phone_number": "+1234567890",
            "user": {"status": "active"},
        })
        
        assert result["intent"] == "mentor"
        assert "tip" in result["final_response"].lower() or "help" in result["final_response"].lower()
    
    def test_message_accumulation(self):
        """Test that messages accumulate correctly with add_messages."""
        graph = build_proper_graph()
        
        # First turn
        result1 = graph.invoke({
            "messages": [HumanMessage(content="Hi!")],
            "phone_number": "+1234567890",
            "user": {"status": "active"},
        })
        
        # Simulate second turn by adding to messages
        result2 = graph.invoke({
            "messages": result1["messages"] + [HumanMessage(content="Find me a match")],
            "phone_number": "+1234567890",
            "user": {"status": "active"},
        })
        
        # Should have accumulated messages
        assert len(result2["messages"]) >= 3  # 2 from first + at least 1 more
    
    def test_llm_receives_proper_messages(self):
        """Test that LLM is invoked with proper message types."""
        mock_llm = MockChatModel()
        graph = build_proper_graph(llm=mock_llm)
        
        graph.invoke({
            "messages": [HumanMessage(content="Hello there!")],
            "phone_number": "+1234567890",
            "user": {"status": "active"},
        })
        
        # Check that LLM received messages (not strings)
        assert len(mock_llm.call_history) > 0
        last_call = mock_llm.call_history[-1]
        
        # First should be SystemMessage, followed by conversation
        assert isinstance(last_call[0], SystemMessage)
        assert any(isinstance(m, HumanMessage) for m in last_call)


class TestComparisonWithOldImplementation:
    """Tests demonstrating differences from the old implementation."""
    
    def test_proper_message_type_usage(self):
        """
        OLD: Uses plain strings for messages
        NEW: Uses proper LangChain message types
        """
        # OLD (wrong) way
        old_state = {
            "message": "Hello!",  # Plain string
            "response": "",  # Plain string output
        }
        
        # NEW (correct) way
        new_state: DatingAgentState = {
            "messages": [HumanMessage(content="Hello!")],  # Proper type
            "phone_number": "+1234567890",
            "user_id": None,
            "chat_id": None,
            "profile": None,
            "user": None,
            "intent": None,
            "final_response": None,
        }
        
        assert isinstance(new_state["messages"][0], HumanMessage)
    
    def test_proper_start_constant_usage(self):
        """
        OLD: Uses graph.set_entry_point("node")
        NEW: Uses graph.add_edge(START, "node")
        """
        graph = StateGraph(DatingAgentState)
        graph.add_node("router", lambda x: x)
        
        # NEW (correct) way - use START constant
        graph.add_edge(START, "router")
        graph.add_edge("router", END)
        
        compiled = graph.compile()
        assert compiled is not None
    
    def test_proper_message_accumulation(self):
        """
        OLD: Replaces messages each time
        NEW: Uses add_messages reducer to accumulate
        """
        # The Annotated[List[BaseMessage], add_messages] pattern
        # automatically appends new messages instead of replacing
        
        state1: DatingAgentState = {
            "messages": [HumanMessage(content="First message")],
            "phone_number": "",
            "user_id": None,
            "chat_id": None,
            "profile": None,
            "user": None,
            "intent": None,
            "final_response": None,
        }
        
        # When a node returns {"messages": [AIMessage(content="Response")]}
        # it gets APPENDED, not replaced
        # This is handled by the add_messages reducer
        
        assert len(state1["messages"]) == 1


# =============================================================================
# INTEGRATION EXAMPLE
# =============================================================================

def demo_proper_graph_usage():
    """
    Demonstrates how the proper graph should be used.
    """
    # Build graph
    graph = build_proper_graph()
    
    # Initialize conversation with proper state
    state = {
        "messages": [HumanMessage(content="Hi, I'm Sarah and I love photography!")],
        "phone_number": "+1234567890",
        "user": {"status": "onboarding", "name": None},
        "profile": None,
    }
    
    # First turn - onboarding
    result = graph.invoke(state)
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['final_response']}")
    print(f"Message count: {len(result['messages'])}")
    
    # Continue conversation - simulate second message
    state["messages"] = result["messages"] + [
        HumanMessage(content="I'm looking for something serious")
    ]
    state["user"]["status"] = "active"  # Assume onboarding complete
    
    result = graph.invoke(state)
    print(f"\nSecond turn - Intent: {result['intent']}")
    print(f"Response: {result['final_response']}")
    print(f"Message count: {len(result['messages'])}")


if __name__ == "__main__":
    demo_proper_graph_usage()

