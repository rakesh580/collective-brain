import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

logger = logging.getLogger("collective_brain.insights")

from app.models.contribution import ContributionRecord
from app.models.insight import InsightRecord
from app.services.llm_service import LLMService
from app.services.memory_graph import MemoryGraph
from app.services.prompts import INSIGHT_DETECTION_PROMPT, WEEKLY_SUMMARY_PROMPT


class InsightEngine:
    def __init__(self, db: Session, llm: LLMService, room_id: str | None = None):
        self.db = db
        self.llm = llm
        self.room_id = room_id
        self.graph = MemoryGraph(db, room_id=room_id)

    async def generate_weekly_summary(self) -> InsightRecord:
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        # Gather last week's activity
        query = (
            self.db.query(ContributionRecord)
            .filter(ContributionRecord.timestamp >= week_ago)
        )
        if self.room_id:
            query = query.filter(ContributionRecord.room_id == self.room_id)
        contribs = query.order_by(ContributionRecord.timestamp.desc()).all()

        activity_data = self._format_contributions(contribs)
        prompt = WEEKLY_SUMMARY_PROMPT.format(activity_data=activity_data)

        messages = [
            {"role": "system", "content": "You are a team analytics assistant."},
            {"role": "user", "content": prompt},
        ]
        summary_text = await self.llm.generate(messages)

        # Parse highlights and recommendations from the text
        highlights = self._extract_list_section(summary_text, "accomplishments")
        recommendations = self._extract_list_section(summary_text, "recommendations")

        insight = InsightRecord(
            id=str(uuid4()),
            insight_type="weekly_summary",
            title=f"Weekly Summary: {week_ago.strftime('%b %d')} - {now.strftime('%b %d')}",
            body=summary_text,
            generated_at=now,
            related_member_ids=list({c.member_id for c in contribs if c.member_id}),
            confidence=0.9,
            period_start=week_ago,
            period_end=now,
            room_id=self.room_id,
            metadata_json={
                "highlights": highlights,
                "recommendations": recommendations,
            },
        )
        self.db.add(insight)
        self.db.commit()
        return insight

    async def detect_patterns(self) -> list[InsightRecord]:
        """Detect patterns using both graph analysis and LLM."""
        insights = []

        # Graph-based pattern detection (no LLM needed)
        graph_patterns = self.graph.detect_patterns()
        for p in graph_patterns:
            insight = InsightRecord(
                id=str(uuid4()),
                insight_type=p["type"],
                title=p["title"],
                body=p["body"],
                generated_at=datetime.now(UTC),
                related_member_ids=p.get("related_members", []),
                confidence=p.get("confidence", 0.5),
            )
            self.db.add(insight)
            insights.append(insight)

        # LLM-based deeper pattern analysis
        contrib_query = (
            self.db.query(ContributionRecord)
        )
        if self.room_id:
            contrib_query = contrib_query.filter(ContributionRecord.room_id == self.room_id)
        contribs = (
            contrib_query
            .order_by(ContributionRecord.timestamp.desc())
            .limit(50)
            .all()
        )
        if contribs:
            team_data = self._format_contributions(contribs)
            prompt = INSIGHT_DETECTION_PROMPT.format(team_data=team_data)
            messages = [
                {"role": "system", "content": "You are a team analytics assistant. Respond in valid JSON."},
                {"role": "user", "content": prompt},
            ]
            try:
                response = await self.llm.generate(messages)
                llm_insights = self._parse_llm_insights(response)
                for li in llm_insights:
                    insight = InsightRecord(
                        id=str(uuid4()),
                        insight_type=li.get("insight_type", "pattern"),
                        title=li.get("title", "Detected Pattern"),
                        body=li.get("body", ""),
                        generated_at=datetime.now(UTC),
                        related_member_ids=li.get("related_members", []),
                        confidence=li.get("confidence", 0.5),
                    )
                    self.db.add(insight)
                    insights.append(insight)
            except Exception as e:
                logger.warning("LLM insight generation failed: %s", e)

        self.db.commit()
        return insights

    async def get_cached_insights(
        self, insight_type: str | None = None, limit: int = 10
    ) -> list[InsightRecord]:
        query = self.db.query(InsightRecord).order_by(InsightRecord.generated_at.desc())
        if self.room_id:
            query = query.filter(InsightRecord.room_id == self.room_id)
        if insight_type:
            query = query.filter(InsightRecord.insight_type == insight_type)
        return query.limit(limit).all()

    def _format_contributions(self, contribs: list[ContributionRecord]) -> str:
        parts = []
        for c in contribs:
            ts = c.timestamp.strftime("%Y-%m-%d %H:%M") if c.timestamp else "unknown"
            topics_str = ", ".join(c.topics or [])
            parts.append(
                f"- [{c.contribution_type}] {c.description or ''} "
                f"(by {c.member_id}, {ts}, topics: {topics_str})"
            )
        return "\n".join(parts) if parts else "(No activity data)"

    def _extract_list_section(self, text: str, keyword: str) -> list[str]:
        items = []
        in_section = False
        for line in text.split("\n"):
            lower = line.lower()
            if keyword in lower and (":" in line or "#" in line):
                in_section = True
                continue
            if in_section:
                stripped = line.strip()
                if stripped.startswith(("-", "*", "•")) or (
                    len(stripped) > 1 and stripped[0].isdigit() and stripped[1] in (".", ")")
                ):
                    items.append(stripped.lstrip("-*•0123456789.) "))
                elif stripped == "" and items:
                    break
        return items

    def _parse_llm_insights(self, response: str) -> list[dict]:
        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if "```" in response:
                start = response.find("```")
                end = response.rfind("```")
                if start != end:
                    # Skip opening ``` (and optional "json" tag) to closing ```
                    inner = response[start:end]
                    # Remove the opening fence line (```json or ```)
                    first_newline = inner.find("\n")
                    if first_newline != -1:
                        json_str = inner[first_newline + 1:]
                    else:
                        json_str = inner.replace("```json", "").replace("```", "")
                else:
                    # Only one ``` found — try parsing the whole response
                    json_str = response.replace("```json", "").replace("```", "")
            else:
                json_str = response
            parsed = json.loads(json_str.strip())
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
            return []
        except (json.JSONDecodeError, ValueError):
            return []
