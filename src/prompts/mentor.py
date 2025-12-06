ICEBREAKER_GENERATION_PROMPT = """Generate conversation starters for someone to send to their match.

About the user:
{user_profile}

About their match:
{match_profile}

Generate 3 conversation openers that:
- Reference something specific they share
- Match the user's communication style
- Are open-ended and encourage response
- Avoid generic greetings like "hey what's up"
- Feel natural and genuine

Format as a numbered list (1. 2. 3.)"""

CONVERSATION_HELP_PROMPT = """Provide helpful advice for continuing a dating conversation.

User profile: {user_profile}
Match profile: {match_profile}
User's question: {message}

Give 2-3 specific, actionable suggestions that:
- Reference the match's interests and style
- Play to the user's strengths
- Are authentic, not manipulative
- Are brief and practical

Keep your response to 3-4 sentences max."""

def get_icebreaker_prompt(user_profile: str, match_profile: str) -> str:
    return ICEBREAKER_GENERATION_PROMPT.format(
        user_profile=user_profile,
        match_profile=match_profile
    )

def get_conversation_help_prompt(user_profile: str, match_profile: str, message: str) -> str:
    return CONVERSATION_HELP_PROMPT.format(
        user_profile=user_profile,
        match_profile=match_profile,
        message=message
    )
