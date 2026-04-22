"""Unit tests for the topic backfill service.

Uses MagicMock for ORM rows (same pattern as other unit tests in this
repo) so the backfill logic is tested in isolation from the real DB.
"""

from unittest.mock import MagicMock

from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.services.topic_backfill import run_topic_backfill


def _make_contribution(member_id: str, topics: list[str]) -> MagicMock:
    c = MagicMock(spec=ContributionRecord)
    c.member_id = member_id
    c.topics = topics
    return c


def _make_member(member_id: str, tags: list[str]) -> MagicMock:
    m = MagicMock(spec=MemberRecord)
    m.id = member_id
    m.expertise_tags = tags
    return m


def _fake_db(contribs: list[MagicMock], members: list[MagicMock]) -> MagicMock:
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        if model is ContributionRecord:
            q.all.return_value = contribs
        elif model is MemberRecord:
            q.all.return_value = members
        else:
            q.all.return_value = []
        return q

    db.query.side_effect = _query
    return db


class TestRunTopicBackfill:
    def test_cleans_noisy_contributions(self):
        c = _make_contribution(
            "alice",
            [
                "python",
                ": test fixtures for ci — seed data, fk constraints",
                "TS",  # alias → typescript
                "some random commit body",
            ],
        )
        m = _make_member("alice", ["python"])
        db = _fake_db([c], [m])

        result = run_topic_backfill(db)

        assert c.topics == ["python", "typescript"]
        assert result.contributions_changed == 1
        assert result.contributions_scanned == 1

    def test_rebuilds_members_expertise_tags_from_contributions(self):
        c1 = _make_contribution("alice", ["python", "frontend"])
        c2 = _make_contribution("alice", ["testing"])
        m = _make_member("alice", [])  # empty — will be rebuilt
        db = _fake_db([c1, c2], [m])

        run_topic_backfill(db)

        assert set(m.expertise_tags) == {"python", "frontend", "testing"}

    def test_drops_unknown_topics_in_expertise_tags(self):
        c = _make_contribution("bob", ["python"])
        # Bob had noisy tag from old data
        m = _make_member("bob", ["python", "sentence fragment from commit"])
        db = _fake_db([c], [m])

        run_topic_backfill(db)

        assert m.expertise_tags == ["python"]

    def test_idempotent(self):
        c = _make_contribution("alice", ["python", "typescript"])
        m = _make_member("alice", ["python", "typescript"])
        db = _fake_db([c], [m])

        first = run_topic_backfill(db)
        # First run on already-clean data: rebuilt set matches, nothing changes
        assert first.contributions_changed == 0
        assert first.members_changed == 0

        # Second run is guaranteed no-op
        second = run_topic_backfill(db)
        assert second.contributions_changed == 0
        assert second.members_changed == 0

    def test_dry_run_does_not_mutate(self):
        original_topics = [
            "python",
            ": test fixtures for ci",
        ]
        c = _make_contribution("alice", list(original_topics))
        m = _make_member("alice", ["something noisy"])
        db = _fake_db([c], [m])

        result = run_topic_backfill(db, dry_run=True)

        # Counts still reported
        assert result.contributions_changed == 1
        # But the objects are untouched
        assert c.topics == original_topics
        assert m.expertise_tags == ["something noisy"]
        # And no commit was issued
        db.commit.assert_not_called()

    def test_as_dict_serializes_counts(self):
        c = _make_contribution("alice", ["python"])
        m = _make_member("alice", ["python"])
        db = _fake_db([c], [m])

        result = run_topic_backfill(db)
        d = result.as_dict()
        assert set(d.keys()) == {
            "contributions_scanned",
            "contributions_changed",
            "members_scanned",
            "members_changed",
        }
        assert all(isinstance(v, int) for v in d.values())

    def test_preserves_clean_contributions_on_member_rebuild(self):
        # Even with a member who has noisy historical tags, rebuild uses their
        # contributions (which are already clean) + canonicalized leftovers
        c = _make_contribution("alice", ["python"])
        m = _make_member("alice", ["python", "typescript", "junk phrase here"])
        db = _fake_db([c], [m])

        run_topic_backfill(db)

        # typescript came from the old tags (canonicalized and kept),
        # python from contributions, junk phrase dropped
        assert set(m.expertise_tags) == {"python", "typescript"}
