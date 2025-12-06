"""Onboarding and profile extraction prompts."""

PROFILE_EXTRACTION_PROMPT = """You are extracting dating profile information from a conversation.

Current profile summary: {current_profile}
User's latest message: {message}
Onboarding step: {step}

Extract the following information and return as JSON:
- name: User's name if mentioned
- age: Age if mentioned
- occupation: What they do for work/school
- interests: List of hobbies and passions
- personality_traits: Observable personality characteristics
- communication_style: How they communicate (analytical/warm/witty/direct)
- relationship_goal: What they're looking for (casual/serious/exploring)
- dealbreakers: Any hard stops or non-negotiables
- values: What matters to them in relationships

Return ONLY valid JSON with these keys. Use null for missing values."""

PROFILE_UPDATE_PROMPT = """You are updating a dating profile based on new conversation.

Current profile summary: {current_summary}
New message from user: {message}

Extract any new information and generate an updated natural language profile summary.
The summary should be 2-4 sentences, warm and natural, in third person.

Format:
"{Name} is a {age}-year-old {occupation} at {school/company}.
They come across as {communication_style} with {personality_traits}.
Into {interests}. Values {values}.
{Additional_context_from_conversations}."

Preserve existing info unless contradicted.
Output the updated summary only."""

LOOKING_FOR_UPDATE_PROMPT = """You are updating what someone is looking for in a dating partner.

Current looking-for summary: {current_looking_for}
New message from user: {message}

Generate an updated summary of what they're looking for.
Format:
"{Name} is looking for someone {key_traits}.
They want {relationship_type} and value {priorities}.
Dealbreaker: {dealbreakers}."

Output the updated summary only."""
