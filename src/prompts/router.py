INTENT_CLASSIFICATION_PROMPT = """You are classifying user intent for a dating AI assistant.

Current user status: {status}
Current conversation node: {current_node}
User message: {message}

Classify the intent into ONE of these categories:
- onboarding: User is answering profile building questions
- match_decision: User is responding yes/no to a match suggestion
- mentor: User is asking for dating advice, conversation help, or icebreakers
- general: General conversation or questions
- settings: User wants to change preferences or pause

Respond with ONLY the category name, nothing else."""

def get_intent_prompt(message: str, status: str = "", current_node: str = "") -> str:
    return INTENT_CLASSIFICATION_PROMPT.format(
        message=message,
        status=status,
        current_node=current_node
    )
