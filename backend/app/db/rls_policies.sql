-- ─────────────────────────────────────────────────────────────────────────────
-- Collective Brain — Row Level Security Policies
-- ─────────────────────────────────────────────────────────────────────────────
-- Run this script once after migrations via:
--   psql $CB_MIGRATION_DATABASE_URL -f backend/app/db/rls_policies.sql
--
-- IMPORTANT: These policies assume the app sets a session variable
--   app.current_organization_id  before every query.
--
--   In FastAPI this is done inside get_session() using:
--     db.execute(text("SET LOCAL app.current_organization_id = :oid"), {"oid": org_id})
--
-- Tables without organization_id (e.g. messages, conversation_participants,
-- chat_room_members, chat_room_messages, discussion_messages) are protected
-- transitively through their parent tables' policies.  If you need direct
-- row-level isolation on those tables too, add policies following the same
-- pattern below.
-- ─────────────────────────────────────────────────────────────────────────────

-- Helper: returns the current org from the session variable
CREATE OR REPLACE FUNCTION current_org_id() RETURNS text
  LANGUAGE sql STABLE
  AS $$ SELECT current_setting('app.current_organization_id', true) $$;


-- ── organizations ────────────────────────────────────────────────────────────
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

CREATE POLICY org_isolation ON organizations
  USING (id = current_org_id());


-- ── organization_memberships ─────────────────────────────────────────────────
ALTER TABLE organization_memberships ENABLE ROW LEVEL SECURITY;

CREATE POLICY org_membership_isolation ON organization_memberships
  USING (organization_id = current_org_id());


-- ── users ─────────────────────────────────────────────────────────────────────
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_org_isolation ON users
  USING (organization_id = current_org_id());


-- ── members ──────────────────────────────────────────────────────────────────
ALTER TABLE members ENABLE ROW LEVEL SECURITY;

CREATE POLICY members_org_isolation ON members
  USING (organization_id = current_org_id());


-- ── artifacts ────────────────────────────────────────────────────────────────
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY artifacts_org_isolation ON artifacts
  USING (organization_id = current_org_id());


-- ── contributions ─────────────────────────────────────────────────────────────
ALTER TABLE contributions ENABLE ROW LEVEL SECURITY;

CREATE POLICY contributions_org_isolation ON contributions
  USING (organization_id = current_org_id());


-- ── conversations ─────────────────────────────────────────────────────────────
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_org_isolation ON conversations
  USING (organization_id = current_org_id());


-- ── insights ──────────────────────────────────────────────────────────────────
ALTER TABLE insights ENABLE ROW LEVEL SECURITY;

CREATE POLICY insights_org_isolation ON insights
  USING (organization_id = current_org_id());


-- ── discussion_threads ────────────────────────────────────────────────────────
ALTER TABLE discussion_threads ENABLE ROW LEVEL SECURITY;

CREATE POLICY discussion_threads_org_isolation ON discussion_threads
  USING (organization_id = current_org_id());


-- ── chat_rooms ────────────────────────────────────────────────────────────────
ALTER TABLE chat_rooms ENABLE ROW LEVEL SECURITY;

CREATE POLICY chat_rooms_org_isolation ON chat_rooms
  USING (organization_id = current_org_id());


-- ── slack_workspaces ──────────────────────────────────────────────────────────
ALTER TABLE slack_workspaces ENABLE ROW LEVEL SECURITY;

CREATE POLICY slack_workspaces_org_isolation ON slack_workspaces
  USING (organization_id = current_org_id());


-- ── help_requests ─────────────────────────────────────────────────────────────
ALTER TABLE help_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY help_requests_org_isolation ON help_requests
  USING (organization_id = current_org_id());


-- ── slack_digest_config ───────────────────────────────────────────────────────
ALTER TABLE slack_digest_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY slack_digest_config_org_isolation ON slack_digest_config
  USING (organization_id = current_org_id());


-- ── health_snapshots ──────────────────────────────────────────────────────────
ALTER TABLE health_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY health_snapshots_org_isolation ON health_snapshots
  USING (organization_id = current_org_id());


-- ── knowledge_embeddings ──────────────────────────────────────────────────────
ALTER TABLE knowledge_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY knowledge_embeddings_org_isolation ON knowledge_embeddings
  USING (organization_id = current_org_id());


-- ─────────────────────────────────────────────────────────────────────────────
-- BYPASS for the service-role key (used by backend app via psycopg2)
-- Supabase's service_role bypasses RLS by default, so the app's DB connection
-- (which uses the service key) can query across all orgs when needed for
-- admin operations.  The session variable is used for tenant scoping at the
-- application layer; RLS is the safety net if the app has a bug.
-- ─────────────────────────────────────────────────────────────────────────────
