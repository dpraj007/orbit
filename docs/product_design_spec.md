# Series Dating: Product Design Specification

## Executive Summary

Series Dating extends the Series "AI Friend" model to romantic connections. Rather than swipe-based matching, users build relationships with an AI companion who deeply understands them, finds genuinely compatible matches through bilateral scoring, and provides ongoing mentorship to help users navigate dating conversations authentically.

**Core thesis**: The same "engineering luck" philosophy that powers Series' professional networking can transform dating from a numbers game into meaningful, mutual connections.

---

## Product Vision

### The Problem

Modern dating apps optimize for engagement, not outcomes. Users experience:
- Superficial matching based on photos and sparse bios
- Asymmetric interest (one-sided swiping)
- Conversation anxiety and ghosting
- No guidance on how to actually connect
- Vanity metrics (match counts) that don't translate to real relationships

### Our Solution

An AI Friend that:
1. Learns who you really are through natural conversation
2. Finds matches where genuine mutual interest exists
3. Mentors you through the dating journey with personalized guidance
4. Facilitates introductions only when both parties opt in

### Design Principles

**Bilateral value**: Every match must benefit both people. No one-sided recommendations.

**Conversational depth over visual snap judgments**: Personality and compatibility first, photos later.

**Mentor, not matchmaker**: The AI helps users become better at connecting, not dependent on AI-written messages.

**Privacy by default**: Minimal information shared until mutual opt-in at each stage.

**Authentic connection**: AI facilitates human relationships, never replaces them.

---

## User Personas

### Primary: The Intentional Dater
- Age 22-30, college-educated professional
- Tired of swipe fatigue and superficial apps
- Values meaningful conversation over volume of matches
- Willing to invest time upfront for better outcomes
- Already familiar with Series for professional networking

### Secondary: The Conversation-Anxious
- Knows what they want but struggles to express it
- Experiences "blank page" anxiety when messaging matches
- Would benefit from coaching and encouragement
- Values having a "wingman" who actually knows them

### Tertiary: The Network Dater
- Prefers warm introductions over cold matching
- Trusts friends-of-friends more than algorithms
- Values the .edu verification and Series trust layer
- Wants dating to feel more like meeting through mutual friends

---

## Core Features

### 1. Conversational Profile Building

**Purpose**: Extract rich, multi-dimensional user profiles through natural dialogue rather than form-filling.

**User Experience**:
- User texts their AI Friend expressing interest in dating features
- AI Friend initiates a warm, conversational onboarding
- Over 10-15 minutes of chat, the AI learns:
  - Relationship goals (casual, serious, exploring)
  - Personality traits and communication style
  - Interests, passions, and lifestyle
  - Values and dealbreakers
  - Past relationship patterns (optional, gentle exploration)
  - What they bring to a relationship
  - What they're looking for in a partner

**Key Design Decisions**:

*Progressive disclosure*: Don't ask everything upfront. Learn more over time through ongoing conversations.

*Inference over interrogation*: Extract personality from HOW users communicate, not just what they say. Message length, emoji usage, response patterns, vocabulary all signal personality.

*Reflection and validation*: AI Friend periodically summarizes understanding: "So it sounds like you value intellectual connection and someone who shares your love of the outdoors. Am I getting that right?"

*No traditional "bio"*: Users never write a dating profile. The AI Friend generates match-relevant summaries dynamically based on what would resonate with each specific potential match.

**Profile Schema** (internal, not user-facing):

```
User Dating Profile:
├── Core Identity
│   ├── communication_style: [analytical, expressive, warm, witty, direct]
│   ├── attachment_signals: [secure, anxious, avoidant indicators]
│   ├── energy_level: [introvert ← → extrovert spectrum]
│   └── life_stage: [exploring, building career, settling down, established]
│
├── Preferences
│   ├── stated_preferences: [explicit user statements]
│   ├── inferred_preferences: [derived from conversation patterns]
│   ├── dealbreakers: [hard stops, non-negotiable]
│   └── nice_to_haves: [flexible preferences]
│
├── Compatibility Vectors
│   ├── conversation_embedding: [768-dim vector of chat style]
│   ├── values_embedding: [what matters to them]
│   ├── interests_embedding: [hobbies, passions, lifestyle]
│   └── humor_embedding: [what makes them laugh]
│
├── Dating Context
│   ├── relationship_goal: [casual, serious, open, unsure]
│   ├── timeline_pressure: [low, medium, high]
│   ├── past_patterns: [optional insights from user sharing]
│   └── growth_areas: [self-identified areas to work on]
│
└── Dynamic State
    ├── current_matches: [active conversations]
    ├── match_feedback: [what worked, what didn't]
    ├── mentor_interactions: [guidance history]
    └── profile_confidence: [how well AI knows them]
```

---

### 2. Bilateral Matching Engine

**Purpose**: Find matches where genuine mutual compatibility exists, not just one-sided interest.

**Matching Philosophy**:

Traditional apps: "A likes B" → show B to A
Series Dating: "A would value B" AND "B would value A" → facilitate introduction

**Scoring Model**:

```
bilateral_score(A, B) = geometric_mean(
    compatibility_score(A → B),
    compatibility_score(B → A)
)
```

Using geometric mean ensures both directions must be strong. A 0.9 × 0.1 scores lower than 0.5 × 0.5.

**Compatibility Components**:

1. **Values alignment** (weight: 0.30)
   - Core beliefs and life priorities
   - Relationship philosophy
   - Long-term vision compatibility

2. **Communication compatibility** (weight: 0.25)
   - Conversation style matching
   - Humor alignment
   - Emotional expression patterns

3. **Interest overlap** (weight: 0.20)
   - Shared hobbies and passions
   - Lifestyle compatibility
   - Activity preferences

4. **Complementary traits** (weight: 0.15)
   - Where differences create positive dynamics
   - Growth opportunities for each person
   - Balance in partnership

5. **Logistics** (weight: 0.10)
   - Location proximity
   - Schedule compatibility
   - Life stage alignment

**Anti-patterns to avoid**:
- Matching based solely on mutual attraction to photos
- Over-indexing on stated preferences vs. behavioral signals
- Creating "leagues" or desirability hierarchies
- Recommending the same popular profiles to everyone

**Cold Start Handling**:
- New users with sparse profiles get matched with other new users initially
- AI Friend proactively asks clarifying questions after early matches
- Feedback loops rapidly improve profile accuracy

---

### 3. Double Opt-In Introduction Flow

**Purpose**: Ensure both parties are genuinely interested before any connection happens.

**Flow**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTRODUCTION FLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: AI identifies high bilateral match                      │
│          bilateral_score(A,B) > threshold                        │
│                         │                                        │
│                         ▼                                        │
│  Step 2: AI Friend reaches out to User A                         │
│          "I found someone interesting - [anonymized pitch]       │
│           Want to know more?"                                    │
│                         │                                        │
│              ┌─────────┴─────────┐                               │
│              ▼                   ▼                                │
│           A: "Yes"            A: "No"                            │
│              │                   │                                │
│              ▼                   ▼                                │
│  Step 3: AI reaches out      Match archived                      │
│          to User B           (with optional                      │
│          (same pitch)        feedback request)                   │
│              │                                                   │
│              ▼                                                   │
│           B: "Yes"                                               │
│              │                                                   │
│              ▼                                                   │
│  Step 4: Mutual opt-in confirmed                                 │
│          Exchange names + AI-curated intros                      │
│          Open direct message channel                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Anonymized Pitch Content**:

What AI Friend shares BEFORE opt-in:
- General vibe/energy description
- 2-3 shared interests or values
- Why AI thinks they'd connect
- Conversation style preview

What AI Friend does NOT share before opt-in:
- Name
- Photos
- Specific identifying details
- Workplace or school
- Social media

**Post Mutual Opt-In**:

Once both say yes:
- Names revealed
- AI-generated "why you might click" summary for each person
- Optional: photos revealed (user preference)
- Direct messaging channel opened
- Mentor mode activated for both users

---

### 4. AI Dating Mentor

**Purpose**: Guide users through dating conversations with personalized, contextual advice that helps them connect authentically.

**Mentor Philosophy**:

The mentor suggests, never scripts. Goals:
- Help users express their authentic selves better
- Reduce conversation anxiety
- Surface relevant topics based on match profiles
- Encourage vulnerability and genuine connection
- Know when to step back

**Mentor Modes**:

#### 4.1 Icebreaker Generation

*Trigger*: New match connection opened, user hasn't sent first message

*Behavior*:
- AI Friend proactively offers: "Want some conversation starters for [Name]?"
- Generates 3-5 openers based on:
  - Shared interests from both profiles
  - Match's communication style
  - User's natural voice
  - Avoiding generic openers

*Example*:
```
AI Friend: "Here are some openers that might work with Alex:

1. You both love climbing - ask about their favorite local spot
2. They mentioned loving cooking shows - any strong opinions on that?
3. Something playful: 'My AI wingman says we'd get along. Thoughts?'

Which feels most like you?"
```

#### 4.2 Conversation Continuation

*Trigger*: User explicitly asks for help mid-conversation OR conversation goes quiet for extended period

*Behavior*:
- Analyze recent conversation context
- Identify promising threads to explore
- Suggest pivots if conversation is stalling
- Never offer unsolicited advice mid-flow

*Example*:
```
User: "The conversation is dying, help"

AI Friend: "Looking at your chat - they got really animated 
when you mentioned travel. You could:

- Ask about their dream destination
- Share that funny story from your Portugal trip
- See if they want to grab coffee and swap travel stories IRL

The travel thread has legs. Pull on it."
```

#### 4.3 Pre-Date Prep

*Trigger*: User mentions upcoming date or asks for advice

*Behavior*:
- Summarize what AI knows about match
- Suggest conversation topics likely to resonate
- Offer confidence-building encouragement
- Remind user of their own strengths

*Example*:
```
AI Friend: "Date with Jordan tomorrow! Here's what I know:

They love: indie films, their dog Max, trying new restaurants
They value: intellectual conversation, someone who listens
Communication style: thoughtful, appreciates humor

You're great at: asking good questions, making people laugh, 
being genuinely curious

Some topics that might land:
- That documentary you mentioned last week
- Ask about Max (dog people love talking about dogs)
- The new Thai place you wanted to try

You've got this. Be yourself - that's why they said yes."
```

#### 4.4 Post-Date Debrief

*Trigger*: User initiates conversation after a date

*Behavior*:
- Ask open-ended questions about how it went
- Help process feelings without judgment
- Identify patterns across dating experiences
- Suggest growth areas gently if appropriate

*Example*:
```
User: "Date was okay I guess"

AI Friend: "Just okay? Tell me more - what worked, what felt off?"

User: "Conversation was good but I felt nervous the whole time"

AI Friend: "Nervousness is normal - it often means you care. 
Did they seem to notice, or did you manage to push through?

Also noticing this is the third time you've mentioned first-date 
nerves. Want to brainstorm some ways to feel more grounded 
going in?"
```

#### 4.5 Recovery Mode

*Trigger*: User expresses distress about dating situation (ghosting, rejection, awkward moment)

*Behavior*:
- Validate feelings first
- Offer perspective without dismissing
- Suggest concrete next steps if appropriate
- Know when to just listen

*Example*:
```
User: "They stopped responding. Did I say something wrong?"

AI Friend: "That's frustrating, and it's natural to wonder why. 
Looking at your conversation, you didn't do anything wrong - 
you were engaged and genuine.

Sometimes people fade for reasons that have nothing to do with you. 
It's not a reflection of your worth.

Want to talk through it, or would you rather I find some new 
matches to focus on?"
```

**Mentor Boundaries**:

The AI mentor explicitly does NOT:
- Write full messages for users to copy-paste
- Encourage manipulation or game-playing
- Push users toward specific outcomes
- Offer advice on physical intimacy
- Replace professional therapy or counseling
- Intervene without being asked (except gentle check-ins)

---

### 5. Trust & Safety Layer

**Purpose**: Create a safe dating environment leveraging Series' existing trust infrastructure.

**Trust Signals**:

1. **Verified identity**
   - .edu email verification (existing Series feature)
   - Optional: ID verification for non-students
   - Profile linked to real Series identity

2. **Network trust**
   - Mutual connections in Series network surfaced
   - "Friend of friend" matches prioritized optionally
   - Reputation signals from professional interactions

3. **Behavior scoring**
   - Response rate and quality
   - Conversation conduct
   - Feedback from past matches (anonymized)

**Safety Features**:

1. **Conversation monitoring** (consent-based)
   - AI can flag concerning patterns if user opts in
   - Resources surfaced for uncomfortable situations
   - Easy blocking and reporting

2. **Controlled information release**
   - Photos optional until trust established
   - Location sharing only when user initiates
   - No social media linking required

3. **Pace controls**
   - Users set their own matching frequency
   - "Pause" feature without losing profile
   - No pressure mechanics or artificial urgency

---

### 6. Feedback & Learning Loop

**Purpose**: Continuously improve matching and mentorship through user feedback.

**Feedback Touchpoints**:

1. **Post-introduction** (24 hours after match)
   - "How's the conversation going?"
   - Quick pulse check, not intrusive survey

2. **Post-date** (if user mentions date)
   - Open-ended debrief conversation
   - Extract what worked, what didn't

3. **Match closure** (when conversation ends)
   - Brief feedback on match quality
   - Option to explain what was missing
   - Input feeds back to matching algorithm

4. **Periodic check-ins** (weekly for active users)
   - Overall satisfaction pulse
   - Preference refinement
   - Mentor effectiveness

**Learning Applications**:

- Recalibrate compatibility weights based on outcomes
- Improve profile inference from conversation patterns
- Refine mentor suggestions based on what helps
- Identify and deprioritize problematic users

---

## Information Architecture

### Conversation States

```
┌─────────────────────────────────────────────────────────────┐
│                    USER JOURNEY STATES                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ONBOARDING                                                  │
│  └── User expresses interest in dating                       │
│      └── Profile building conversation                       │
│          └── Minimum viable profile reached                  │
│              └── Matching enabled                            │
│                                                              │
│  MATCHING                                                    │
│  └── Receiving match suggestions                             │
│      └── Reviewing anonymized profiles                       │
│          └── Opt-in / opt-out decisions                      │
│              └── Awaiting mutual opt-in                      │
│                                                              │
│  ACTIVE CONNECTION                                           │
│  └── Matched and chatting                                    │
│      └── Mentor available on request                         │
│          └── Date planning/execution                         │
│              └── Relationship progression                    │
│                                                              │
│  FEEDBACK                                                    │
│  └── Post-match reflection                                   │
│      └── Pattern identification                              │
│          └── Profile refinement                              │
│                                                              │
│  PAUSED                                                      │
│  └── Taking a break                                          │
│      └── Profile preserved                                   │
│          └── Easy reactivation                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Message Types (Kafka Events)

```
Inbound Events (User → System):
├── dating.onboarding.response     # Profile building answers
├── dating.match.decision          # Accept/reject match suggestion  
├── dating.conversation.message    # Direct message to match
├── dating.mentor.request          # Asking for mentor help
├── dating.feedback.submission     # Match/date feedback
└── dating.settings.update         # Preference changes

Outbound Events (System → User):
├── dating.onboarding.question     # Profile building prompts
├── dating.match.suggestion        # New match proposal
├── dating.match.confirmed         # Mutual opt-in notification
├── dating.mentor.response         # Mentor advice
├── dating.reminder.gentle         # Check-ins and nudges
└── dating.insight.periodic        # Pattern/progress updates
```

---

## LangGraph Agent Architecture

### Graph Structure

```
                    ┌─────────────────┐
                    │   Entry Point   │
                    │  (Message In)   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     Router      │
                    │ (Intent Class.) │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Onboarding  │   │    Matching   │   │    Mentor     │
│     Node      │   │     Node      │   │     Node      │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    Profile    │   │  Match Eval   │   │   Context     │
│    Builder    │   │   & Scoring   │   │   Retrieval   │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │    Response     │
                   │   Generator     │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Message Out    │
                   │ (Kafka Produce) │
                   └─────────────────┘
```

### Node Specifications

#### Router Node
- **Input**: Raw user message + conversation history
- **Output**: Classified intent + routed to appropriate node
- **Logic**: LLM-based intent classification with fallback rules

Intent categories:
- `onboarding.*` → Onboarding Node
- `match.*` → Matching Node  
- `mentor.*` → Mentor Node
- `settings.*` → Settings Handler
- `general.*` → General Conversation

#### Onboarding Node
- **Input**: User message in onboarding context
- **Output**: Next profile-building question OR completion signal
- **State access**: User profile (read/write)
- **Logic**: 
  - Track which profile areas are complete
  - Generate contextual follow-up questions
  - Validate and store responses
  - Determine when MVP profile reached

#### Matching Node
- **Input**: Match-related intent (suggestion response, feedback)
- **Output**: Match decision processing OR new suggestion
- **State access**: User profile, match pool, match history
- **Logic**:
  - Process opt-in/opt-out decisions
  - Trigger bilateral confirmation flow
  - Generate anonymized match pitches
  - Record feedback for learning

#### Mentor Node
- **Input**: Mentor request + conversation context
- **Output**: Contextual dating advice
- **State access**: User profile, match profile, conversation history
- **Sub-modes**:
  - Icebreaker generation
  - Conversation continuation
  - Pre-date prep
  - Post-date debrief
  - Recovery support

#### Response Generator
- **Input**: Structured response intent from nodes
- **Output**: Natural language message in AI Friend voice
- **Logic**:
  - Maintain consistent personality
  - Adapt tone to emotional context
  - Format appropriately for iMessage

### State Schema

```python
class DatingAgentState(TypedDict):
    # Conversation context
    user_id: str
    thread_id: str
    messages: list[BaseMessage]
    current_intent: str
    
    # User profile
    profile: UserDatingProfile
    profile_completeness: float
    
    # Matching state
    pending_suggestions: list[MatchSuggestion]
    active_matches: list[ActiveMatch]
    match_history: list[MatchOutcome]
    
    # Mentor state
    mentor_mode: Optional[str]
    mentor_context: Optional[MentorContext]
    
    # Conversation state
    conversation_stage: str
    last_interaction: datetime
    awaiting_response_to: Optional[str]
```

---

## Privacy & Data Handling

### Data Classification

**Highly Sensitive** (encrypted at rest, minimal retention):
- Explicit relationship/dating preferences
- Match conversation content
- Feedback about specific people

**Sensitive** (standard encryption, retained for service):
- Profile attributes and embeddings
- Match history (anonymized over time)
- Mentor interaction logs

**Standard** (normal handling):
- Aggregate usage patterns
- Feature engagement metrics
- System performance data

### User Controls

Users can:
- Export all their dating data
- Delete dating profile independently of main Series profile
- Control what's shared at each matching stage
- Opt out of any AI analysis
- Request human review of AI decisions

### Data Boundaries

- Dating data siloed from professional Series data
- No cross-pollination of profiles without explicit consent
- Match information never shared with third parties
- Conversation content not used for advertising

---

## Success Metrics

### North Star
**Meaningful connections formed**: Matches that progress to dates and beyond

### Primary Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Bilateral match rate | % of suggestions where both opt in | >40% |
| Conversation depth | Avg messages exchanged per match | >20 |
| Date conversion | % of matches leading to IRL meeting | >25% |
| Mentor engagement | % of users using mentor features | >60% |
| User satisfaction | NPS for dating feature | >50 |

### Secondary Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Profile completion rate | % completing onboarding | >80% |
| Time to first match | Median time from signup to first mutual match | <48 hrs |
| Feedback submission rate | % of matches receiving feedback | >50% |
| Reactivation rate | % of paused users returning | >30% |
| Safety incident rate | Reports per 1000 matches | <5 |

### Anti-Metrics (what we don't optimize for)

- Total swipes/views (vanity engagement)
- Time in app (should be efficient, not addictive)
- Match volume (quality over quantity)
- Message count (depth over frequency)

---

## Hackathon MVP Scope

Given 24-hour constraint, prioritize:

### Must Have (Demo-Ready)
1. Conversational profile builder (5-7 questions, rich extraction)
2. Bilateral matching concept (even with mock/simple scoring)
3. Double opt-in flow demonstration
4. One mentor feature (icebreaker generation)
5. Working Kafka integration (consume/produce messages)

### Should Have (If Time)
6. Basic conversation continuation mentor mode
7. Simple feedback collection
8. Profile completeness tracking

### Won't Have (Post-Hackathon)
- Full ML matching pipeline
- Comprehensive safety systems
- All mentor modes
- Analytics dashboard
- Scale infrastructure

### Demo Script Suggestion

1. "Watch me onboard" - Show profile building conversation
2. "Here's a match" - Demonstrate bilateral scoring concept
3. "Both said yes" - Walk through opt-in flow
4. "Need help?" - Show icebreaker generation
5. "The vision" - Explain full roadmap

---

## Open Questions for Team Discussion

1. **Photos**: When in the flow should photos be revealed? Before opt-in? After? User choice?

2. **Transparency**: Should users know when their match is using mentor features? "Series-assisted" badge?

3. **Cross-pollination**: Can professional Series connections become dating matches? Should they?

4. **Exclusivity**: One match at a time (focused) or multiple concurrent (efficient)?

5. **AI disclosure**: How explicit should we be that matches are AI-suggested vs. organic?

6. **Failure modes**: What happens when the AI consistently fails to find good matches for someone?

---

## Appendix: Series Alignment Checklist

| Series Principle | How Dating Feature Aligns |
|------------------|---------------------------|
| Engineering luck | Makes serendipitous romantic connections repeatable |
| Anti-vanity metrics | No swipes, no match counts, no "likes" |
| Bilateral value | Both parties must opt in; both must benefit |
| Authentic connection | AI mentors authentic self-expression, not fabrication |
| Democratizing access | Good matches regardless of existing social capital |
| Trust layer | .edu verification, network trust signals |
| Conversational first | Profiles built through chat, not forms |
| Human-centered AI | AI facilitates human connection, doesn't replace it |

---

*Document Version: 1.0*
*Created for: Series Hackathon (December 5-6, 2025)*
*Team: [Your Team Name]*
