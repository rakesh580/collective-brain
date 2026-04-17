# Collective Brain — Agent Playbook

## The Team (8 World-Class Agents)

| Agent | Skill File | Expertise | Bug Rate |
|-------|-----------|-----------|----------|
| **AI Engineer** | `ai-engineer.md` | LLM pipelines, embeddings, extraction, search | 4 bugs → 0 after skill.md |
| **Backend Engineer** | `backend-engineer.md` | FastAPI routers, API endpoints, DB integration | 13 bugs → 0 after skill.md |
| **Frontend Engineer** | `frontend-engineer.md` | React 19, TypeScript, Tailwind, Recharts, force-graph | 0 bugs (always clean) |
| **DevOps Engineer** | `devops-engineer.md` | Alembic migrations, CI/CD, Docker, secrets management | 0 bugs (always clean) |
| **QA Engineer** | `qa-engineer.md` | pytest, vitest, integration tests, cross-agent audits | Caught all 17 bugs |
| **Data Scientist** | `data-scientist.md` | Scoring algorithms, graph analytics, anomaly detection, embeddings | NEW |
| **Senior Researcher** | `senior-researcher.md` | Org science, decision theory, knowledge management, evaluation frameworks | NEW |
| **Cybersecurity Engineer** | `cybersecurity-engineer.md` | OWASP, STRIDE threat model, auth/authz, API security, compliance | NEW |

## Agent Capabilities

### AI Engineer
- Builds LLM extraction pipelines (decision extraction, onboarding briefings)
- Designs hybrid search (keyword + semantic + LLM synthesis)
- Handles prompt engineering with proper brace escaping
- Implements graceful fallbacks when LLM is unavailable

### Backend Engineer
- Writes FastAPI routers with proper auth, DB lifecycle, error handling
- **MUST read service files first** — this is the #1 rule (learned the hard way)
- Integrates services with correct method names and parameters
- Follows `_get_db()` + `try/finally: db.close()` pattern on every endpoint

### Frontend Engineer
- Builds React 19 pages with dark theme, framer-motion animations
- Uses Recharts for data visualization, react-force-graph-2d for graphs
- Follows the complete checklist: types → api → page → route → sidebar → tests
- Matches existing design system perfectly

### DevOps Engineer
- Manages Alembic migration chains (revision IDs under 32 chars!)
- Wires routers in main.py (primary + legacy deprecated)
- Sets GitHub secrets, configures CI/CD pipelines
- Handles Supabase IPv6 limitations in GitHub Actions

### QA Engineer
- Writes unit tests with proper mocking patterns
- Writes integration tests against live FastAPI TestClient
- Runs cross-agent audits (router ↔ service method verification)
- Validates frontend ↔ backend API contracts

### Data Scientist
- Designs multi-factor weighted scoring algorithms
- Implements Gini coefficient for distribution analysis
- Uses temporal decay (stepped, not continuous) for recency weighting
- Builds anomaly detection with relative thresholds (not hardcoded)
- Generates actionable recommendations, not just scores

### Senior Researcher
- Validates features against organizational science literature
- Applies RICE-D framework to prioritize features
- Designs evaluation frameworks for LLM and scoring quality
- Identifies anti-patterns (features without feedback loops, metrics without context)
- Ensures every feature answers "why does anyone care?"

### Cybersecurity Engineer
- Reviews every endpoint against OWASP Top 10
- Maintains STRIDE threat model for the application
- Validates multi-tenant isolation (organization_id on every query)
- Checks LLM prompt injection defenses
- Validates webhook URLs against SSRF
- Ensures secrets management follows zero-trust principles

## Launch Order (Proven Safe)

```
Wave 1 (parallel):  AI Engineer + Frontend + DevOps + Data Scientist
Wave 2 (after Wave 1): Backend Engineer (reads service files first!)
Wave 3 (after Wave 2): QA Engineer (needs both routers + services)
Wave 4 (any time):  Senior Researcher (validates architecture)
Wave 5 (after code): Cybersecurity Engineer (security review)
```

## The #1 Rule

> **Never let an agent guess what another agent built. Provide exact method signatures, or run agents sequentially so they can read the actual files.**
