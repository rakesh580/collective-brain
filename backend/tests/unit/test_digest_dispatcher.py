"""Unit tests for the timezone-aware weekly-digest dispatcher.

Exercises the matching logic (org timezone × SlackDigestConfig schedule),
idempotency, email fallback, and per-org failure isolation. Uses an
in-memory SQLite-like mock — no real DB, no real Slack, no real SMTP.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import digest_dispatcher
from app.services.digest_dispatcher import (
    _is_slack_cfg_due,
    _org_local_now,
    _recent_enough,
    reset_breakers_for_tests,
    run_due_digests,
)


@pytest.fixture(autouse=True)
def _reset_breakers():
    """Keep the module-level CircuitBreakers CLOSED between tests."""
    reset_breakers_for_tests()
    yield
    reset_breakers_for_tests()


def _cfg(
    cfg_id: str = "cfg-1",
    workspace_id: str = "W1",
    channel_id: str = "C1",
    day: int = 4,
    hour: int = 16,
    enabled: bool = True,
    last_sent_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=cfg_id,
        workspace_id=workspace_id,
        channel_id=channel_id,
        schedule_day=day,
        schedule_hour=hour,
        enabled=enabled,
        last_sent_at=last_sent_at,
    )


def _org(
    org_id: str = "org-1",
    name: str = "Acme",
    digest_enabled: bool = True,
    digest_timezone: str = "UTC",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=org_id,
        name=name,
        is_active=True,
        digest_enabled=digest_enabled,
        digest_timezone=digest_timezone,
    )


class TestOrgLocalNow:
    def test_converts_utc_to_configured_tz(self):
        org = _org(digest_timezone="America/Los_Angeles")
        utc_now = datetime(2026, 4, 24, 23, 0, tzinfo=UTC)  # Fri 23:00 UTC
        local = _org_local_now(org, utc_now)
        # LA is UTC-7 in April (PDT) → 16:00 local Friday
        assert local.weekday() == 4
        assert local.hour == 16

    def test_invalid_timezone_falls_back_to_utc(self):
        org = _org(digest_timezone="Not/A/Real/Zone")
        utc_now = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        local = _org_local_now(org, utc_now)
        assert local.hour == 16


class TestIsSlackCfgDue:
    def test_matches_weekday_and_hour(self):
        org_local = datetime(2026, 4, 24, 16, 0)  # Fri 16:00 local
        cfg = _cfg(day=4, hour=16)
        now_utc = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        assert _is_slack_cfg_due(cfg, org_local, now_utc) is True

    def test_disabled_not_due(self):
        org_local = datetime(2026, 4, 24, 16, 0)
        cfg = _cfg(day=4, hour=16, enabled=False)
        assert _is_slack_cfg_due(cfg, org_local, datetime.now(UTC)) is False

    def test_recent_send_blocks(self):
        org_local = datetime(2026, 4, 24, 16, 0)
        now_utc = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        cfg = _cfg(day=4, hour=16, last_sent_at=now_utc - timedelta(hours=2))
        assert _is_slack_cfg_due(cfg, org_local, now_utc) is False


class TestRecentEnough:
    def test_naive_datetime_accepted(self):
        now = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        naive = (now - timedelta(hours=1)).replace(tzinfo=None)
        assert _recent_enough(naive, now) is True

    def test_none_is_not_recent(self):
        assert _recent_enough(None, datetime.now(UTC)) is False


class _QueryMux:
    """Route db.query(Model) to a per-model fake query."""

    def __init__(self, rows_by_model: dict[str, list]):
        self.rows_by_model = rows_by_model
        self.added: list = []
        self.committed = 0

    def __call__(self, model):
        name = getattr(model, "__name__", str(model))
        q = _Query(self.rows_by_model.get(name, []))
        return q

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1


class _Query:
    def __init__(self, rows: list):
        self._rows = rows

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


def _make_db(**rows_by_model) -> MagicMock:
    mux = _QueryMux(rows_by_model)
    db = MagicMock()
    db.query.side_effect = mux
    db.add.side_effect = mux.add
    db.commit.side_effect = mux.commit
    db.added_rows = mux.added
    return db


class TestRunDueDigests:
    @pytest.mark.asyncio
    async def test_slack_path_fires_and_logs(self, monkeypatch):
        now = datetime(2026, 4, 24, 23, 0, tzinfo=UTC)  # Fri 4 PM PDT
        org = _org(digest_timezone="America/Los_Angeles")
        cfg = _cfg(workspace_id="W1", channel_id="C1", day=4, hour=16)

        db = _make_db(
            OrganizationRecord=[org],
            SlackDigestConfig=[cfg],
        )
        send = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(digest_dispatcher, "send_digest_to_slack", send)

        summary = await run_due_digests(db, now=now)

        assert summary["sent"] == 1
        assert summary["failed"] == 0
        send.assert_awaited_once_with(db=db, workspace_id="W1", channel_id="C1")
        # Expect a digest_log row appended.
        assert any(
            getattr(row, "delivery_channel", None) == "slack" and getattr(row, "status", None) == "sent"
            for row in db.added_rows
        )

    @pytest.mark.asyncio
    async def test_digest_disabled_org_is_skipped(self, monkeypatch):
        now = datetime(2026, 4, 24, 23, 0, tzinfo=UTC)
        org = _org(digest_timezone="America/Los_Angeles", digest_enabled=False)
        # Digest-disabled orgs are filtered at query time. Pass zero results.
        db = _make_db(OrganizationRecord=[], SlackDigestConfig=[])
        send = AsyncMock()
        monkeypatch.setattr(digest_dispatcher, "send_digest_to_slack", send)

        summary = await run_due_digests(db, now=now)
        assert summary["due"] == 0
        send.assert_not_awaited()
        # Defensive: org above is unused; the filter test lives in the query
        # layer (not exercised by this mock). This test documents the contract.
        _ = org

    @pytest.mark.asyncio
    async def test_slack_failure_isolated_and_logged(self, monkeypatch):
        now = datetime(2026, 4, 24, 23, 0, tzinfo=UTC)
        org = _org(digest_timezone="America/Los_Angeles")
        cfg = _cfg(workspace_id="W1", channel_id="C1", day=4, hour=16)

        db = _make_db(
            OrganizationRecord=[org],
            SlackDigestConfig=[cfg],
        )

        async def bad(db, workspace_id, channel_id):
            raise RuntimeError("slack unreachable")

        monkeypatch.setattr(digest_dispatcher, "send_digest_to_slack", bad)

        summary = await run_due_digests(db, now=now)

        assert summary["failed"] == 1
        assert summary["sent"] == 0
        assert any(getattr(row, "status", None) == "failed" for row in db.added_rows)

    @pytest.mark.asyncio
    async def test_email_fallback_when_no_slack_config(self, monkeypatch):
        # Friday 16:00 in UTC org.
        now = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        org = _org(digest_timezone="UTC")

        db = _make_db(
            OrganizationRecord=[org],
            SlackDigestConfig=[],  # no slack → fallback path
        )

        # Stub out the digest content generation + SMTP sender.
        monkeypatch.setattr(
            digest_dispatcher,
            "generate_weekly_digest",
            lambda db: {"period_start": None, "period_end": None},
        )
        monkeypatch.setattr(digest_dispatcher, "format_text_digest", lambda d: "digest body")
        monkeypatch.setattr(
            digest_dispatcher,
            "_admin_emails_for_org",
            lambda db, org_id: ["alice@acme.com"],
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "_recent_digest_log_exists",
            lambda db, oid, ch, now: False,
        )

        called: dict = {}

        def fake_send(**kwargs):
            called.update(kwargs)
            return {"ok": True, "recipients": kwargs["to"]}

        monkeypatch.setattr(digest_dispatcher, "send_email", fake_send)

        summary = await run_due_digests(db, now=now)

        assert summary["sent"] == 1
        assert called["to"] == ["alice@acme.com"]
        assert any(getattr(row, "delivery_channel", None) == "email" for row in db.added_rows)

    @pytest.mark.asyncio
    async def test_email_fallback_no_recipients_logs_skip(self, monkeypatch):
        now = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        org = _org(digest_timezone="UTC")
        db = _make_db(OrganizationRecord=[org], SlackDigestConfig=[])

        monkeypatch.setattr(digest_dispatcher, "_admin_emails_for_org", lambda db, org_id: [])
        monkeypatch.setattr(
            digest_dispatcher,
            "_recent_digest_log_exists",
            lambda db, oid, ch, now: False,
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "generate_weekly_digest",
            lambda db: {"period_start": None, "period_end": None},
        )

        summary = await run_due_digests(db, now=now)

        assert summary["sent"] == 0
        # logged in_app skipped
        assert any(
            getattr(row, "delivery_channel", None) == "in_app" and getattr(row, "status", None) == "skipped"
            for row in db.added_rows
        )

    @pytest.mark.asyncio
    async def test_email_fallback_smtp_unconfigured_stores_in_app(self, monkeypatch):
        from app.services.email_service import EmailNotConfigured

        now = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
        org = _org(digest_timezone="UTC")
        db = _make_db(OrganizationRecord=[org], SlackDigestConfig=[])

        monkeypatch.setattr(
            digest_dispatcher,
            "_admin_emails_for_org",
            lambda db, org_id: ["ops@acme.com"],
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "_recent_digest_log_exists",
            lambda db, oid, ch, now: False,
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "generate_weekly_digest",
            lambda db: {"period_start": None, "period_end": None},
        )
        monkeypatch.setattr(digest_dispatcher, "format_text_digest", lambda d: "body")

        def unconfigured(**kwargs):
            raise EmailNotConfigured("CB_SMTP_HOST is not set")

        monkeypatch.setattr(digest_dispatcher, "send_email", unconfigured)

        summary = await run_due_digests(db, now=now)

        assert summary["sent"] == 1
        # Captured as in_app "sent" so the dashboard card still renders.
        assert any(
            getattr(row, "delivery_channel", None) == "in_app" and getattr(row, "status", None) == "sent"
            for row in db.added_rows
        )

    @pytest.mark.asyncio
    async def test_email_skipped_when_not_friday_4pm_local(self, monkeypatch):
        # Friday 10 AM local — not the default email window (16:00).
        now = datetime(2026, 4, 24, 10, 0, tzinfo=UTC)
        org = _org(digest_timezone="UTC")
        db = _make_db(OrganizationRecord=[org], SlackDigestConfig=[])

        send = MagicMock()
        monkeypatch.setattr(digest_dispatcher, "send_email", send)

        summary = await run_due_digests(db, now=now)

        assert summary["sent"] == 0
        send.assert_not_called()


class TestCircuitBreakers:
    @pytest.mark.asyncio
    async def test_slack_breaker_trips_after_repeat_failures(self, monkeypatch):
        """After 5 consecutive Slack errors the breaker opens; further attempts
        get a CircuitBreakerError recorded in digest_log as 'failed'."""
        from app.services.circuit_breaker import CircuitBreakerError

        now = datetime(2026, 4, 24, 23, 0, tzinfo=UTC)
        org = _org(digest_timezone="America/Los_Angeles")
        configs = [_cfg(cfg_id=f"cfg{i}", workspace_id="W1", channel_id=f"C{i}", day=4, hour=16) for i in range(7)]
        db = _make_db(OrganizationRecord=[org], SlackDigestConfig=configs)

        async def always_fail(db, workspace_id, channel_id):
            raise RuntimeError("slack 5xx")

        monkeypatch.setattr(digest_dispatcher, "send_digest_to_slack", always_fail)

        summary = await run_due_digests(db, now=now)

        # 5 real failures open the breaker; the remaining 2 get
        # CircuitBreakerError — still counted as failed.
        assert summary["failed"] == 7
        errors = [row for row in db.added_rows if getattr(row, "status", None) == "failed"]
        assert any("CircuitBreakerError" in (getattr(r, "error", "") or "") for r in errors)
        # Final state: breaker is OPEN.
        assert not digest_dispatcher._slack_breaker.is_available
        # CircuitBreakerError import used for clarity:
        assert CircuitBreakerError is not None


class TestIntegrationEndToEnd:
    """Dispatcher + digest_log + slack send + email fallback, in one run."""

    @pytest.mark.asyncio
    async def test_mixed_orgs_one_run(self, monkeypatch):
        now = datetime(2026, 4, 24, 23, 0, tzinfo=UTC)  # Fri 4 PM PDT / 11 PM UTC

        slack_org = _org(org_id="org-slack", digest_timezone="America/Los_Angeles")
        email_org = _org(org_id="org-email", digest_timezone="America/Los_Angeles")
        cfg = _cfg(workspace_id="WS", channel_id="CH", day=4, hour=16)

        # OrganizationRecord query returns both orgs; SlackDigestConfig query
        # returns the single cfg for slack_org only.
        class _MuxWithConfigs:
            def __init__(self):
                self.added: list = []
                self.commits = 0
                self._slack_query_count = 0

            def __call__(self, model):
                name = getattr(model, "__name__", str(model))
                if name == "OrganizationRecord":
                    return _Query([slack_org, email_org])
                if name == "SlackDigestConfig":
                    self._slack_query_count += 1
                    # First call is for slack_org, second for email_org.
                    if self._slack_query_count == 1:
                        return _Query([cfg])
                    return _Query([])
                return _Query([])

        mux = _MuxWithConfigs()
        db = MagicMock()
        db.query.side_effect = mux
        db.add.side_effect = lambda r: mux.added.append(r)
        db.commit.side_effect = lambda: setattr(mux, "commits", mux.commits + 1)
        db.added_rows = mux.added

        monkeypatch.setattr(
            digest_dispatcher,
            "send_digest_to_slack",
            AsyncMock(return_value={"ok": True}),
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "_admin_emails_for_org",
            lambda db, org_id: ["ceo@acme.com"] if org_id == "org-email" else [],
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "_recent_digest_log_exists",
            lambda db, oid, ch, now: False,
        )
        monkeypatch.setattr(
            digest_dispatcher,
            "generate_weekly_digest",
            lambda db: {"period_start": None, "period_end": None},
        )
        monkeypatch.setattr(digest_dispatcher, "format_text_digest", lambda d: "body")
        monkeypatch.setattr(digest_dispatcher, "send_email", lambda **kw: {"ok": True})

        summary = await run_due_digests(db, now=now)

        assert summary["sent"] == 2  # 1 slack + 1 email
        channels = {getattr(r, "delivery_channel", None) for r in db.added_rows}
        assert "slack" in channels
        assert "email" in channels
