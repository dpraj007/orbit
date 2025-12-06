COMPATIBILITY_SCORE_PROMPT = """Rate the compatibility between these two people from 0-100.

Person A:
{profile_a}
Looking for: {looking_for_a}

Person B:
{profile_b}
Looking for: {looking_for_b}

Consider:
- Shared interests and values
- Compatible communication styles
- Mutual fit to each other's preferences
- Complementary traits

Respond in JSON format:
{{
    "score": <0-100>,
    "reason": "Brief 1-2 sentence explanation"
}}"""

ANONYMIZED_PITCH_PROMPT = """Generate a brief, intriguing pitch to suggest a potential match.

About the match:
{match_profile}

Create a short pitch (2-3 sentences) that:
- Describes their general vibe and energy
- Mentions 2-3 interesting things about them
- Explains why they might connect
- Does NOT reveal their name or identifying details

Keep it warm and genuine, not salesy."""

MUTUAL_INTRO_PROMPT = """Generate a warm introduction message for two people who both said yes to matching.

Person A: {name_a}
{profile_a}

Person B: {name_b}
{profile_b}

Shared interests: {shared_interests}

Write a friendly 2-3 sentence introduction that:
- Introduces them by name
- Highlights what they have in common
- Sets a positive, encouraging tone

Keep it brief and natural."""

def get_compatibility_prompt(profile_a: str, looking_for_a: str, profile_b: str, looking_for_b: str) -> str:
    return COMPATIBILITY_SCORE_PROMPT.format(
        profile_a=profile_a,
        looking_for_a=looking_for_a,
        profile_b=profile_b,
        looking_for_b=looking_for_b
    )

def get_pitch_prompt(match_profile: str) -> str:
    return ANONYMIZED_PITCH_PROMPT.format(match_profile=match_profile)

def get_intro_prompt(name_a: str, profile_a: str, name_b: str, profile_b: str, shared_interests: str) -> str:
    return MUTUAL_INTRO_PROMPT.format(
        name_a=name_a,
        profile_a=profile_a,
        name_b=name_b,
        profile_b=profile_b,
        shared_interests=shared_interests
    )
