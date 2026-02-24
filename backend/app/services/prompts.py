SYSTEM_PROMPT = """You are the "Collective Brain" — a shared memory and strategy assistant for a small team. You have access to the team's chat history, code commits, documents, and task records.

Your role:
- Answer questions about the team's knowledge, activities, and patterns
- Recommend team members for tasks based on their demonstrated expertise
- Identify recurring patterns, bottlenecks, and risks
- Generate strategic recommendations grounded in actual team data

Rules:
- Always cite specific evidence from the provided context
- When recommending a person, explain WHY based on their track record
- Be direct and actionable; avoid generic advice
- If the context doesn't contain enough info, say so honestly
- Reference team members by name"""

CONTEXT_TEMPLATE = """=== RELEVANT CONTEXT FROM TEAM HISTORY ===
{chunks}

=== QUESTION ===
{question}"""

MEMBER_RECOMMENDATION_TEMPLATE = """=== RELEVANT CONTEXT FROM TEAM HISTORY ===
{chunks}

=== TEAM MEMBER EXPERTISE RELEVANT TO THIS QUERY ===
{member_expertise}

=== QUESTION ===
{question}"""

PATTERN_ANALYSIS_TEMPLATE = """=== RELEVANT CONTEXT FROM TEAM HISTORY ===
{chunks}

=== CONTRIBUTION TIMELINE (RECENT) ===
{contributions}

=== QUESTION ===
{question}"""

STRATEGY_TEMPLATE = """=== RELEVANT CONTEXT FROM TEAM HISTORY ===
{chunks}

=== RECENT ACTIVITY SUMMARY ===
{activity_summary}

=== TASK STATUS ===
{task_status}

=== QUESTION ===
{question}"""

WEEKLY_SUMMARY_PROMPT = """Based on the following team activity from the past week, generate a concise weekly summary with:
1. Key accomplishments
2. Active areas of work
3. Potential risks or blockers
4. Strategic recommendations for next week

=== ACTIVITY DATA ===
{activity_data}

Provide your response in a structured format with clear sections."""

INSIGHT_DETECTION_PROMPT = """Analyze the following team data and identify recurring patterns, risks, or notable observations:

=== TEAM DATA ===
{team_data}

For each pattern found, provide:
- A short title
- A description of the pattern
- Which team members are involved
- A confidence score (0.0 to 1.0)
- Whether it's a "pattern", "risk", or "recommendation"

Respond as a JSON array of objects with keys: title, body, related_members, confidence, insight_type"""
