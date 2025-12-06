"""Mentor mode prompts for dating guidance."""

ICEBREAKER_PROMPT = """Generate 3 conversation openers for someone to send to their match.

About the user: {user_profile}
About their match: {match_profile}
User's communication style: {user_style}

Create openers that:
- Reference something specific they share
- Match the user's natural communication style
- Are open-ended and encourage dialogue
- Avoid generic greetings like "hey" or "what's up"
- Feel authentic to who the user is

Return as a numbered list of 3 options."""

CONVERSATION_CONTINUATION_PROMPT = """Provide conversation continuation advice for someone chatting with their match.

User profile: {user_profile}
Match profile: {match_profile}
Recent conversation excerpt: {conversation_excerpt}

The user is asking for help continuing the conversation.

Analyze the conversation and suggest:
1. Promising threads to explore based on what the match engaged with
2. Specific questions or topics that align with both profiles
3. When it might be time to suggest meeting in person

Keep suggestions brief (2-3 options) and actionable.
Match the user's communication style.
Focus on genuine connection, not scripts."""

PRE_DATE_PREP_PROMPT = """Provide pre-date preparation advice for someone meeting their match.

User profile: {user_profile}
Match profile: {match_profile}
Date context: {date_context}

Generate a warm, encouraging prep message that includes:
1. Key things about the match (interests, communication style)
2. Conversation topics likely to resonate
3. Reminder of the user's strengths
4. Confidence-building encouragement

Keep it concise and natural, like a friend giving advice."""

POST_DATE_DEBRIEF_PROMPT = """Help someone process and learn from a date experience.

User profile: {user_profile}
Match profile: {match_profile}
User's date reflection: {user_reflection}

Respond as a supportive friend who:
1. Asks open-ended questions to understand how they feel
2. Helps identify patterns across dating experiences
3. Gently suggests growth areas if appropriate
4. Validates feelings without dismissing concerns
5. Offers concrete next steps when relevant

Be warm, non-judgmental, and focused on their growth."""

RECOVERY_PROMPT = """Provide supportive guidance after a difficult dating situation.

User profile: {user_profile}
Situation: {situation}

Respond with empathy and perspective:
1. Validate their feelings first
2. Offer perspective without dismissing pain
3. Remind them of their worth
4. Suggest concrete next steps if appropriate
5. Know when to just listen

Be genuine and supportive, like a trusted friend."""
