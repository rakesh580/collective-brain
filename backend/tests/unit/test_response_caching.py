"""Unit tests for Redis response caching, cache invalidation, and migration guard.

Tests verify:
- Cache hits return data without DB queries
- Cache misses trigger DB queries and populate cache
- Different parameters produce different cache keys
- Mutation endpoints invalidate the correct cache patterns
- Migration guard respects CB_RUN_MIGRATIONS env var
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_request(cache_get_return=None):
    """Build a mock FastAPI Request with redis + vector_store on app.state."""
    mock_request = MagicMock()
    mock_redis = MagicMock()
    mock_redis.cache_get = AsyncMock(return_value=cache_get_return)
    mock_redis.cache_set = AsyncMock()
    mock_redis.cache_delete_pattern = AsyncMock()
    mock_request.app.state.redis = mock_redis
    mock_request.app.state.vector_store = MagicMock()
    mock_request.app.state.vector_store.count.return_value = 42
    mock_request.app.state.llm_service = MagicMock()
    mock_request.app.state.settings = Settings(
        jwt_secret="test-secret-key-minimum-32-chars-long",
        jwt_algorithm="HS256",
        jwt_expire_minutes=30,
        google_client_id="test",
    )
    return mock_request


def _make_mock_db():
    """Build a mock DB session that satisfies dashboard/member/decision queries."""
    db = MagicMock()

    # MemberRecord queries
    member_query = MagicMock()
    member_query.count.return_value = 3
    member_query.order_by.return_value.limit.return_value.all.return_value = []
    member_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    # ArtifactRecord queries
    art_query = MagicMock()
    art_query.filter.return_value = art_query
    art_query.count.return_value = 10

    # InsightRecord queries
    ins_query = MagicMock()
    ins_query.order_by.return_value = ins_query
    ins_query.filter.return_value = ins_query
    ins_query.limit.return_value.all.return_value = []

    # DecisionRecord / RiskAlert queries
    dec_query = MagicMock()
    dec_query.count.return_value = 5
    dec_query.filter.return_value.count.return_value = 1
    dec_query.order_by.return_value.desc = MagicMock()
    dec_query.order_by.return_value.limit.return_value.all.return_value = []
    dec_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    # ContributionRecord queries
    contrib_query = MagicMock()
    contrib_query.filter.return_value = contrib_query
    contrib_query.distinct.return_value.all.return_value = []

    # Route db.query(Model) to the right mock based on the model class name
    def query_router(model_cls):
        name = getattr(model_cls, "__name__", str(model_cls))
        if "Member" in name:
            return member_query
        if "Artifact" in name:
            return art_query
        if "Insight" in name:
            return ins_query
        if "Contribution" in name:
            return contrib_query
        # DecisionRecord, RiskAlert, etc.
        return dec_query

    db.query.side_effect = query_router
    return db


def _mock_user():
    user = MagicMock()
    user.id = "test-user-id"
    return user


# ── Dashboard Caching ───────────────────────────────────────────────────────

class TestDashboardCaching:

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """When cache has data, should return it without DB queries."""
        cached_data = {"total_members": 99, "cached": True}
        mock_request = _make_request(cache_get_return=cached_data)

        from app.routers.insights import get_dashboard

        with patch("app.routers.insights.get_current_user", return_value=_mock_user()):
            result = await get_dashboard(request=mock_request, room_id=None, user=_mock_user())

        assert result == cached_data
        # DB should never have been touched
        mock_request.app.state.redis.cache_get.assert_awaited_once_with("dashboard:all")

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db_and_caches(self):
        """When cache empty, should query DB and store result with TTL 60."""
        mock_request = _make_request(cache_get_return=None)
        mock_db = _make_mock_db()

        from app.routers.insights import get_dashboard

        with (
            patch("app.routers.insights._get_db", return_value=mock_db),
            patch("app.routers.insights.get_current_user", return_value=_mock_user()),
        ):
            result = await get_dashboard(request=mock_request, room_id=None, user=_mock_user())

        # Should have stored result in cache
        redis = mock_request.app.state.redis
        redis.cache_set.assert_awaited_once()
        call_args = redis.cache_set.call_args
        assert call_args[0][0] == "dashboard:all"  # key
        assert call_args[1]["ttl_seconds"] == 60 or call_args[0][2] == 60  # TTL
        assert isinstance(result, dict)
        assert "total_members" in result

    @pytest.mark.asyncio
    async def test_different_room_ids_use_different_keys(self):
        """room_id=None and room_id='abc' should produce different cache keys."""
        mock_request_all = _make_request(cache_get_return={"room": "all"})
        mock_request_abc = _make_request(cache_get_return={"room": "abc"})

        from app.routers.insights import get_dashboard

        with patch("app.routers.insights.get_current_user", return_value=_mock_user()):
            await get_dashboard(request=mock_request_all, room_id=None, user=_mock_user())
            await get_dashboard(request=mock_request_abc, room_id="abc", user=_mock_user())

        mock_request_all.app.state.redis.cache_get.assert_awaited_once_with("dashboard:all")
        mock_request_abc.app.state.redis.cache_get.assert_awaited_once_with("dashboard:abc")


# ── Members List Caching ────────────────────────────────────────────────────

class TestMembersListCaching:

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """When cache has data, should return it without DB queries."""
        cached_data = {"members": [], "total": 0}
        mock_request = _make_request(cache_get_return=cached_data)

        from app.routers.members import list_members

        with patch("app.dependencies.get_current_user", return_value=_mock_user()):
            result = await list_members(request=mock_request, room_id=None, limit=50, offset=0)

        assert result == cached_data
        mock_request.app.state.redis.cache_get.assert_awaited_once_with("members:list:all:50:0")

    @pytest.mark.asyncio
    async def test_different_params_produce_different_keys(self):
        """Different limit/offset/room_id should produce different cache keys."""
        req1 = _make_request(cache_get_return={"v": 1})
        req2 = _make_request(cache_get_return={"v": 2})
        req3 = _make_request(cache_get_return={"v": 3})

        from app.routers.members import list_members

        with patch("app.dependencies.get_current_user", return_value=_mock_user()):
            await list_members(request=req1, room_id=None, limit=50, offset=0)
            await list_members(request=req2, room_id="room-1", limit=50, offset=0)
            await list_members(request=req3, room_id=None, limit=10, offset=20)

        req1.app.state.redis.cache_get.assert_awaited_once_with("members:list:all:50:0")
        req2.app.state.redis.cache_get.assert_awaited_once_with("members:list:room-1:50:0")
        req3.app.state.redis.cache_get.assert_awaited_once_with("members:list:all:10:20")

    @pytest.mark.asyncio
    async def test_cache_miss_stores_with_ttl_120(self):
        """Cache miss should query DB and store result with TTL 120."""
        mock_request = _make_request(cache_get_return=None)
        mock_db = _make_mock_db()

        from app.routers.members import list_members

        with (
            patch("app.routers.members._get_db", return_value=mock_db),
            patch("app.dependencies.get_current_user", return_value=_mock_user()),
        ):
            result = await list_members(request=mock_request, room_id=None, limit=50, offset=0)

        redis = mock_request.app.state.redis
        redis.cache_set.assert_awaited_once()
        call_args = redis.cache_set.call_args
        assert call_args[0][0] == "members:list:all:50:0"
        assert call_args[1].get("ttl_seconds") == 120


# ── Decisions List Caching ──────────────────────────────────────────────────

class TestDecisionsListCaching:

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """When cache has data, should return it without DB queries."""
        cached_data = {"decisions": [], "total": 0}
        mock_request = _make_request(cache_get_return=cached_data)

        from app.routers.decisions import list_decisions

        with patch("app.routers.decisions.get_current_user", return_value=_mock_user()):
            result = await list_decisions(
                request=mock_request,
                decision_type=None,
                status=None,
                tag=None,
                member_id=None,
                limit=50,
                offset=0,
                user=_mock_user(),
            )

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_miss_stores_with_ttl_120(self):
        """Cache miss should query DB and store with TTL 120."""
        mock_request = _make_request(cache_get_return=None)
        mock_db = _make_mock_db()

        from app.routers.decisions import list_decisions

        with (
            patch("app.routers.decisions._get_db", return_value=mock_db),
            patch("app.routers.decisions.get_current_user", return_value=_mock_user()),
        ):
            result = await list_decisions(
                request=mock_request,
                decision_type=None,
                status=None,
                tag=None,
                member_id=None,
                limit=50,
                offset=0,
                user=_mock_user(),
            )

        redis = mock_request.app.state.redis
        redis.cache_set.assert_awaited_once()
        call_args = redis.cache_set.call_args
        assert call_args[1].get("ttl_seconds") == 120


# ── Cache Invalidation ──────────────────────────────────────────────────────

class TestCacheInvalidation:

    @pytest.mark.asyncio
    async def test_member_create_clears_members_and_dashboard(self):
        """Creating a member should invalidate members:list:* and dashboard:*."""
        mock_request = _make_request()
        mock_db = _make_mock_db()
        # Make the member ID lookup return None (no conflict)
        mock_db.query.side_effect = None
        member_query = MagicMock()
        member_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = member_query

        from app.routers.members import create_member
        from app.schemas.requests import MemberCreateRequest

        body = MemberCreateRequest(name="Test User", email="test@example.com")

        with (
            patch("app.routers.members._get_db", return_value=mock_db),
            patch("app.routers.members.require_role", return_value=lambda: _mock_user()),
        ):
            await create_member(body=body, request=mock_request, user=_mock_user())

        redis = mock_request.app.state.redis
        patterns = [call[0][0] for call in redis.cache_delete_pattern.call_args_list]
        assert "members:list:*" in patterns
        assert "dashboard:*" in patterns

    @pytest.mark.asyncio
    async def test_ingest_clears_dashboard_and_members(self):
        """Ingestion should invalidate dashboard:* and members:list:*."""
        mock_request = _make_request()

        from app.routers.ingest import _ingest_and_invalidate

        mock_connector = MagicMock()

        with patch("app.routers.ingest._run_ingestion", return_value={"status": "ok"}):
            await _ingest_and_invalidate(
                request=mock_request,
                connector=mock_connector,
                source_input="test",
                source_path="/test",
            )

        redis = mock_request.app.state.redis
        patterns = [call[0][0] for call in redis.cache_delete_pattern.call_args_list]
        assert "dashboard:*" in patterns
        assert "members:list:*" in patterns

    @pytest.mark.asyncio
    async def test_decision_delete_clears_decisions_and_dashboard(self):
        """Deleting a decision should invalidate decisions:list:* and dashboard:*."""
        mock_request = _make_request()
        mock_db = MagicMock()
        mock_decision = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_decision
        mock_db.query.return_value.filter.return_value.delete.return_value = 0

        from app.routers.decisions import delete_decision

        with (
            patch("app.routers.decisions._get_db", return_value=mock_db),
            patch("app.routers.decisions.get_current_user", return_value=_mock_user()),
        ):
            await delete_decision(decision_id="dec-1", request=mock_request, user=_mock_user())

        redis = mock_request.app.state.redis
        patterns = [call[0][0] for call in redis.cache_delete_pattern.call_args_list]
        assert "decisions:list:*" in patterns
        assert "dashboard:*" in patterns

    @pytest.mark.asyncio
    async def test_decision_update_clears_decisions_and_dashboard(self):
        """Updating a decision should invalidate decisions:list:* and dashboard:*."""
        mock_request = _make_request()
        mock_db = MagicMock()
        mock_decision = MagicMock()
        mock_decision.id = "dec-1"
        mock_decision.organization_id = None
        mock_decision.title = "Old"
        mock_decision.description = "desc"
        mock_decision.decision_type = "technical"
        mock_decision.status = "draft"
        mock_decision.confidence_score = 0.8
        mock_decision.context_summary = ""
        mock_decision.alternatives_considered = []
        mock_decision.outcome_summary = None
        mock_decision.source_artifact_ids = []
        mock_decision.source_chunk_ids = []
        mock_decision.involved_member_ids = []
        mock_decision.tags = []
        mock_decision.decided_at = None
        mock_decision.extracted_at = None
        mock_decision.created_at = None
        mock_decision.updated_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_decision

        from app.routers.decisions import DecisionUpdate, update_decision

        body = DecisionUpdate(title="New Title")

        with (
            patch("app.routers.decisions._get_db", return_value=mock_db),
            patch("app.routers.decisions.get_current_user", return_value=_mock_user()),
        ):
            await update_decision(decision_id="dec-1", body=body, request=mock_request, user=_mock_user())

        redis = mock_request.app.state.redis
        patterns = [call[0][0] for call in redis.cache_delete_pattern.call_args_list]
        assert "decisions:list:*" in patterns
        assert "dashboard:*" in patterns

    @pytest.mark.asyncio
    async def test_member_delete_clears_members_and_dashboard(self):
        """Deleting a member should invalidate members:list:* and dashboard:*."""
        mock_request = _make_request()
        mock_db = MagicMock()
        mock_member = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_member
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        # Artifacts with member_ids
        mock_db.query.return_value.filter.return_value.all.return_value = []

        from app.routers.members import delete_member

        with (
            patch("app.routers.members._get_db", return_value=mock_db),
            patch("app.routers.members.require_role", return_value=lambda: _mock_user()),
        ):
            await delete_member(member_id="test-member", request=mock_request, user=_mock_user())

        redis = mock_request.app.state.redis
        patterns = [call[0][0] for call in redis.cache_delete_pattern.call_args_list]
        assert "members:list:*" in patterns
        assert "dashboard:*" in patterns


# ── Migration Guard ─────────────────────────────────────────────────────────

class TestMigrationGuard:

    def test_cb_run_migrations_false_skips_migrations(self):
        """When CB_RUN_MIGRATIONS=false, _run_alembic_migrations should NOT be called."""
        with (
            patch.dict(os.environ, {"CB_RUN_MIGRATIONS": "false"}),
            patch("app.db.database._run_alembic_migrations") as mock_migrate,
            patch("app.db.database.create_engine") as mock_engine,
        ):
            engine = MagicMock()
            conn = MagicMock()
            engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
            engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value = engine

            from app.db.database import init_db

            settings = MagicMock()
            settings.effective_database_url = "postgresql://test:test@localhost/test"
            settings.db_pool_size = 5
            settings.db_max_overflow = 10
            settings.db_pool_timeout = 30
            settings.db_pool_recycle = 1800

            init_db(settings=settings)

            mock_migrate.assert_not_called()

    def test_cb_run_migrations_true_runs_migrations(self):
        """When CB_RUN_MIGRATIONS=true (default), migrations should run."""
        with (
            patch.dict(os.environ, {"CB_RUN_MIGRATIONS": "true"}),
            patch("app.db.database._run_alembic_migrations") as mock_migrate,
            patch("app.db.database.create_engine") as mock_engine,
        ):
            engine = MagicMock()
            conn = MagicMock()
            engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
            engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_engine.return_value = engine

            from app.db.database import init_db

            settings = MagicMock()
            settings.effective_database_url = "postgresql://test:test@localhost/test"
            settings.db_pool_size = 5
            settings.db_max_overflow = 10
            settings.db_pool_timeout = 30
            settings.db_pool_recycle = 1800
            settings.effective_migration_url = "postgresql://test:test@localhost/test"

            init_db(settings=settings)

            mock_migrate.assert_called_once_with(settings)
