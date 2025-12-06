"""Matching and bilateral scoring prompts."""

BILATERAL_SCORING_PROMPT = """Rate compatibility between these two dating profiles on a scale of 0-100.

Person A Profile:
{profile_a}

Person A Looking For:
{looking_for_a}

Person B Profile:
{profile_b}

Person B Looking For:
{looking_for_b}

Consider:
1. Shared interests and lifestyle compatibility
2. Compatible communication styles
3. Mutual fit to each other's preferences
4. Values alignment
5. Complementary traits that create positive dynamics

Rate how well Person A would match Person B's needs and preferences.

Respond with ONLY a JSON object:
{{"score": <0-100>, "reason": "<brief 1-2 sentence explanation>"}}"""

MATCH_PITCH_PROMPT = """Generate an anonymized match pitch to present to a user.

User Profile: {user_profile}
Match Profile: {match_profile}
Compatibility Score: {score}
Match Highlights: {highlights}

Create a short, engaging pitch (2-3 sentences) that:
- Highlights shared interests and values
- Explains why they might connect well
- Maintains anonymity (no name, specific identifiers)
- Is warm and encouraging, not salesy
- Keep the tone smooth, low-key, and natural. Avoid hype and exclamation marks.

Output the pitch only, as if speaking directly to the user."""
