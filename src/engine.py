import json
import logging
from typing import Dict, Any

from .client import SeriesClient
from .store import UserStore
from .llm import WingmanLLM
from .agent.graph import create_dating_graph


log = logging.getLogger("orbit.engine")


def process_event(event: Dict, client: SeriesClient, store: UserStore, llm: WingmanLLM, graph=None) -> None:
    """Process incoming Kafka event using LangGraph agent."""
    data = event.get("data", {})
    text = (data.get("text") or "").strip()
    from_phone = data.get("from_phone")
    chat_id = data.get("chat_id")

    if not from_phone or chat_id is None:
        log.warning("Skipping event missing phone/chat_id: %s", event)
        return

    if not text:
        log.info("Skipping empty message")
        return

    # Create graph if not provided
    if graph is None:
        graph = create_dating_graph(store, llm, client)

    # Build initial state
    initial_state = {
        "phone_number": from_phone,
        "chat_id": chat_id,
        "message": text,
        "user_id": None,
        "user": None,
        "profile": None,
        "conversation_state": None,
        "active_match": None,
        "intent": None,
        "response": "",
        "next_node": None,
        "db_updates": []
    }

    try:
        # Set typing indicator
        client.set_typing(chat_id)

        # Run the graph
        log.info(f"Processing message from {from_phone}: {text}")
        result = graph.invoke(initial_state)

        # Send response
        response = result.get("response", "")
        if response:
            log.info(f"Sending response: {response}")
            client.send_message(chat_id, response)
        else:
            log.warning("No response generated")

    except Exception as e:
        log.exception(f"Error processing event: {e}")
        try:
            client.send_message(chat_id, "Sorry, something went wrong. Can you try again?")
        except:
            pass
