"""Persona definitions for LLM simulation."""
from dataclasses import dataclass


@dataclass
class Persona:
    """User persona for simulation."""
    name: str
    age: int
    occupation: str
    personality: str  # "outgoing", "shy", "analytical", "playful"
    relationship_goal: str  # "casual", "serious", "exploring"
    interests: list[str]
    communication_style: str  # "verbose", "terse", "emoji-heavy"
    quirks: list[str]  # Unique behaviors like typos, slang


PERSONAS = [
    Persona(
        name="Alex",
        age=25,
        occupation="Software Engineer",
        personality="analytical",
        relationship_goal="serious",
        interests=["hiking", "cooking", "board games"],
        communication_style="verbose",
        quirks=["uses technical metaphors", "asks clarifying questions"],
    ),
    Persona(
        name="Jordan",
        age=28,
        occupation="Marketing Manager",
        personality="outgoing",
        relationship_goal="exploring",
        interests=["music festivals", "yoga", "travel"],
        communication_style="emoji-heavy",
        quirks=["uses lots of exclamation points!", "references pop culture"],
    ),
    Persona(
        name="Sam",
        age=23,
        occupation="Grad Student",
        personality="shy",
        relationship_goal="serious",
        interests=["reading", "indie films", "coffee shops"],
        communication_style="terse",
        quirks=["gives short answers", "takes time to open up"],
    ),
]

