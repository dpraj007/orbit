"""Conversation driver for LLM-simulated personas."""
from dataclasses import dataclass
from typing import Optional

from langchain_openai import ChatOpenAI

from tests.helpers.event_builder import build_event
from tests.helpers.runner import RunResult, TestRunner
from tests.simulation.personas import Persona

SIMULATOR_SYSTEM_PROMPT = """
You are roleplaying as a user on a dating app talking to an AI assistant named Orbit.

YOUR PERSONA:
- Name: {name}
- Age: {age}
- Occupation: {occupation}
- Personality: {personality}
- Looking for: {relationship_goal}
- Interests: {interests}
- Communication style: {communication_style}
- Quirks: {quirks}

CURRENT CONTEXT:
- Conversation history so far:
{conversation_history}

- Orbit's last message:
{agent_response}

INSTRUCTIONS:
- Respond naturally as this persona would
- Stay in character with the communication style and quirks
- If Orbit asks a question, answer it authentically as your persona
- Don't break character or mention you're an AI
- Keep responses realistic (1-3 sentences typically)
- If you want to end the conversation, respond with exactly: [END]

Generate your next message:
"""


@dataclass
class ConversationResult:
    """Result of a simulated conversation."""
    persona: Persona
    turns: list[tuple[str, str]]  # (user_msg, agent_msg) pairs
    results: list[RunResult]
    tokens_used: int = 0

    @property
    def final_db_state(self) -> dict:
        """Get final database state."""
        return self.results[-1].db_state if self.results else {}

    @property
    def onboarding_completed(self) -> bool:
        """Check if onboarding was completed."""
        user = self.final_db_state.get("user", {})
        return user.get("status") == "active" if user else False


class ConversationDriver:
    """Drives multi-turn conversations using LLM-simulated personas."""

    def __init__(
        self,
        runner: TestRunner,
        llm: Optional[ChatOpenAI] = None,
        max_turns: int = 20,
        token_budget: int = 5000,
    ):
        self.runner = runner
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        self.max_turns = max_turns
        self.token_budget = token_budget
        self.tokens_used = 0

    def generate_user_response(
        self, persona: Persona, history: list[tuple[str, str]], agent_response: str
    ) -> Optional[str]:
        """Generate next user message based on persona and context."""
        history_text = "\n".join([
            f"User: {u}\nOrbit: {a}" for u, a in history
        ]) or "(conversation just started)"

        prompt = SIMULATOR_SYSTEM_PROMPT.format(
            name=persona.name,
            age=persona.age,
            occupation=persona.occupation,
            personality=persona.personality,
            relationship_goal=persona.relationship_goal,
            interests=", ".join(persona.interests),
            communication_style=persona.communication_style,
            quirks=", ".join(persona.quirks),
            conversation_history=history_text,
            agent_response=agent_response,
        )

        try:
            result = self.llm.invoke(prompt)
            self.tokens_used += result.response_metadata.get("token_usage", {}).get("total_tokens", 100)

            response = result.content.strip()

            if "[END]" in response or self.tokens_used >= self.token_budget:
                return None

            return response
        except Exception:
            return None

    def run_full_conversation(
        self,
        persona: Persona,
        phone: str = "+15551234567",
        chat_id: int = 1001,
        initial_message: Optional[str] = None,
    ) -> ConversationResult:
        """Run complete conversation until natural end or limits reached."""
        history: list[tuple[str, str]] = []
        results: list[RunResult] = []

        # Start with initial message or generate one
        user_message = initial_message or f"Hey! I'm {persona.name}"

        for turn in range(self.max_turns):
            # Run user message through agent
            event = build_event(phone=phone, chat_id=chat_id, text=user_message)
            result = self.runner.run_event(event)
            results.append(result)

            history.append((user_message, result.response))

            # Check for natural end conditions
            if "I'll start looking for matches" in result.response or result.db_state.get("user", {}).get("status") == "active":
                # Onboarding complete
                break

            # Generate next user response
            user_message = self.generate_user_response(persona, history, result.response)

            if user_message is None:
                break

        return ConversationResult(
            persona=persona,
            turns=history,
            results=results,
            tokens_used=self.tokens_used,
        )

