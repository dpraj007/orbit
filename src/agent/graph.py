"""LangGraph graph definition for dating agent."""
import json
import logging
import time
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import AIMessage, HumanMessage

from ..api import SeriesAPI
from ..db import Database
from .agentic import run_agent
from .nodes import matching_node, mentor_node, onboarding_node
from .router import classify_intent_node, load_context_node, route_to_node
from .state import DatingState


def generate_general_response(
    status: str, profile_summary: str, context: str, message: str
) -> str:
    """Generate a dynamic general response using LLM."""
    log = logging.getLogger("orbit.agent.general")
    llm = get_llm()

    prompt = GENERAL_RESPONSE_PROMPT.format(
        status=status or "unknown",
        profile_summary=profile_summary or "new user",
        context=context or "general conversation",
        message=message or "",
    )

    try:
        result = llm.invoke(prompt)
        response = result.content if hasattr(result, "content") else str(result)
        return response.strip()
    except Exception as exc:
        log.error("Failed to generate general response: %s", exc)
        # Minimal fallback
        if status == "active":
            return "Ready to find a match? Just say yes!"
        elif status == "onboarding":
            return "Let's continue getting to know you!"
        return "I'm here to help with dating! What would you like to do?"


def general_node(state: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Handle general/fallback messages via the agentic handler."""
    log = logging.getLogger("orbit.agent.general")

    message = state.get("message", "")
    result = run_agent(message, state, db, api=None)  # type: ignore[arg-type]

    response = result.get("response", "")
    db_updates = result.get("db_updates", [])

    log.info("General node using agentic response: %s", response[:80] if response else "(empty)")
    return {"response": response, "next_node": "save_and_respond", "db_updates": db_updates}


def save_and_respond_node(state: Dict[str, Any], db: Any, api: SeriesAPI) -> Dict[str, Any]:
    """Save state and send response to user."""
    log = logging.getLogger("orbit.agent.save")

    response = state.get("response", "")
    chat_id = state.get("chat_id")
    user_id = state.get("user_id")
    conv_state = state.get("conversation_state") or {}
    db_updates = state.get("db_updates", [])

    # Simple dedupe: if we just sent the same response to this user within a few seconds, skip
    context_raw = conv_state.get("context")
    if user_id and response:
        if context_raw:
            try:
                ctx_obj = json.loads(context_raw) if isinstance(context_raw, str) else context_raw
            except Exception:
                ctx_obj = {}
        else:
            ctx_obj = {}
        last_resp = ctx_obj.get("last_response")
        last_ts = ctx_obj.get("last_response_ts", 0)
        if last_resp == response and (time.time() - last_ts) < 5:
            log.info("Skipping duplicate response for user %s", user_id)
            response = ""
        # Update context with last response
        ctx_obj.update({"last_response": response, "last_response_ts": time.time()})
        db.conversation_state.upsert(user_id, context=json.dumps(ctx_obj))

    # Process database updates
    for update in db_updates:
        update_type = update.get("type")

        if update_type == "notify_match":
            # Send notification to match candidate
            try:
                api.send_with_typing(update["chat_id"], update["message"])
            except Exception as exc:
                log.error("Failed to notify match: %s", exc)

        elif update_type == "create_group":
            # Create group chat for mutual match
            try:
                user_a_id = update["user_a_id"]
                user_b_id = update["user_b_id"]

                user_a = db.users.get_by_id(user_a_id)
                user_b = db.users.get_by_id(user_b_id)

                if user_a and user_b:
                    user_a_phone = user_a["phone_number"]
                    user_b_phone = user_b["phone_number"]

                    intro_message = (
                        f"Hi! {update['user_a_name']}, meet {update['user_b_name']}. "
                        f"You both matched! Have fun connecting."
                    )

                    result = api.create_group_chat(
                        [user_a_phone, user_b_phone],
                        intro_message,
                        display_name="Match",
                    )

                    log.info("Created group chat for match: %s", result)

                    # Send a follow-up to let them know the AI is available
                    group_chat_id = result.get("chat", {}).get("id") or result.get("id")
                    if group_chat_id:
                        api.send_message(
                            group_chat_id,
                            "I'm here if you @Orbit for conversation tips. Otherwise, enjoy getting to know each other! 🎉",
                        )

            except Exception as exc:
                log.error("Failed to create group chat: %s", exc)

    # Send response to user
    if response and chat_id:
        try:
            api.send_with_typing(chat_id, response)
            log.info("Sent response to chat %d", chat_id)
        except Exception as exc:
            log.error("Failed to send response: %s", exc)

    return {"response": response}


def build_graph(db: Database, api: SeriesAPI) -> StateGraph:
    """Build the LangGraph state machine."""

    # Create state graph
    graph = StateGraph(DatingState)

    # Create node wrapper functions that include db and api
    def load_context_wrapper(state: DatingState) -> Dict[str, Any]:
        return load_context_node(state, db)

    def classify_intent_wrapper(state: DatingState) -> Dict[str, Any]:
        return classify_intent_node(state)

    def onboarding_wrapper(state: DatingState) -> Dict[str, Any]:
        return onboarding_node(state, db)

    def matching_wrapper(state: DatingState) -> Dict[str, Any]:
        return matching_node(state, db)

    def mentor_wrapper(state: DatingState) -> Dict[str, Any]:
        return mentor_node(state, db)

    def general_wrapper(state: DatingState) -> Dict[str, Any]:
        return general_node(state, db)

    def save_and_respond_wrapper(state: DatingState) -> Dict[str, Any]:
        return save_and_respond_node(state, db, api)

    # Add nodes
    graph.add_node("load_context", load_context_wrapper)
    graph.add_node("classify_intent", classify_intent_wrapper)
    graph.add_node("onboarding", onboarding_wrapper)
    graph.add_node("matching", matching_wrapper)
    graph.add_node("mentor", mentor_wrapper)
    graph.add_node("general", general_wrapper)
    graph.add_node("save_and_respond", save_and_respond_wrapper)

    # PROPER: Use START constant instead of set_entry_point()
    # This is the recommended LangGraph v1.x pattern
    graph.add_edge(START, "load_context")

    # Add edges
    graph.add_edge("load_context", "classify_intent")

    # Conditional routing from classify_intent
    graph.add_conditional_edges(
        "classify_intent",
        route_to_node,
        {
            "onboarding": "onboarding",
            "matching": "matching",
            "mentor": "mentor",
            "general": "general",
        },
    )

    # All nodes go to save_and_respond
    graph.add_edge("onboarding", "save_and_respond")
    graph.add_edge("matching", "save_and_respond")
    graph.add_edge("mentor", "save_and_respond")
    graph.add_edge("general", "save_and_respond")

    # End after save_and_respond
    graph.add_edge("save_and_respond", END)

    # Compile graph
    compiled_graph = graph.compile()

    logging.getLogger("orbit.agent").info("LangGraph compiled successfully")

    return compiled_graph
