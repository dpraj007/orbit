ONBOARDING_QUESTIONS = [
    "Hey! What's your name?",
    "What are you looking for? Something casual, serious, or just exploring?",
    "Tell me a bit about yourself - what do you do, what are you into?",
    "What do you do for fun? Any hobbies or passions?",
    "What matters most to you in a partner?",
    "Any absolute dealbreakers?",
    "Thanks! I'll start looking for great matches for you."
]

PROFILE_EXTRACTION_PROMPT = """You are extracting information from a user's message during dating profile onboarding.

Onboarding step {step}:
Question asked: {question}
User response: {message}

Current profile summary: {current_summary}
Current looking_for summary: {current_looking_for}

Extract relevant information and generate updated natural language summaries.

For profile_summary: Write 2-4 sentences about who they are (personality, interests, lifestyle).
For looking_for_summary: Write 2-3 sentences about what they want in a partner.

Also extract:
- name: Their name if mentioned
- relationship_goal: casual | serious | exploring | unsure
- communication_style: warm | witty | direct | analytical | expressive
- interests: List of hobbies and interests
- dealbreakers: List of non-negotiables

Respond in JSON format:
{{
    "name": "...",
    "profile_summary": "Updated summary about who they are...",
    "looking_for_summary": "Updated summary about what they want...",
    "relationship_goal": "...",
    "communication_style": "...",
    "interests": ["...", "..."],
    "dealbreakers": ["...", "..."]
}}

Only include fields that can be extracted. Preserve existing info unless contradicted."""

def get_extraction_prompt(step: int, message: str, current_summary: str = "", current_looking_for: str = "") -> str:
    question = ONBOARDING_QUESTIONS[step] if step < len(ONBOARDING_QUESTIONS) else ""
    return PROFILE_EXTRACTION_PROMPT.format(
        step=step,
        question=question,
        message=message,
        current_summary=current_summary or "None yet",
        current_looking_for=current_looking_for or "None yet"
    )
