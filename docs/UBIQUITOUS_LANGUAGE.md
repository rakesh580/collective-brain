# Ubiquitous Language

A single, opinionated glossary for Collective Brain. When adding a new concept or feature, check here first; if the term you want already has a canonical meaning, reuse it. If not, add it here and reference it in code + docs.

Source of truth: `backend/app/models/` ORM classes define what the code thinks each concept is. This document describes what the domain *means* them to be.

## Tenancy

| Term              | Definition                                                                        | Aliases to avoid     |
| ----------------- | --------------------------------------------------------------------------------- | -------------------- |
| **Organization**  | A tenant. Everything else (artifacts, members, signals) is scoped to exactly one. | Tenant, workspace¹, account |
| **Workspace**¹    | A Slack workspace specifically. Distinct from **Organization** — one Org may own several Slack Workspaces. | -                    |
| **User**          | An authentication identity. Logs in, holds a JWT, has a role (`admin`/`owner`/`member`). | Login, account       |
| **Membership**    | A `(User, Organization, role)` triple. One User can belong to many Orgs.         | Assignment           |

¹ "Workspace" in this codebase means *Slack workspace only*. The noun for "your company on the platform" is always **Organization**. Don't use "workspace" to mean tenant.

## People & their work

| Term              | Definition                                                                        | Aliases to avoid     |
| ----------------- | --------------------------------------------------------------------------------- | -------------------- |
| **Member**        | A person who has contributed to the Org's knowledge base. May or may not be linked to a **User**. A Slack bot post creates a Member without a User. | Contributor², person, author |
| **Contribution**  | A single attributed action by a Member inside an **Artifact** — a commit in a repo, a message in a thread, an edit in a doc. Has a timestamp, topics, sentiment, impact_score. | Activity, event, action |
| **WorkItem**      | A unified PR / issue / task record with lifecycle state (open → in_progress → merged/closed) and cycle-time fields. Distinct from **Artifact**: an Artifact is *content*, a WorkItem is *a unit of work with deadlines and state*. | Ticket, task, issue  |
| **Artifact**      | A piece of ingested content — a markdown file, a code file, a chat thread, a GitHub PR's description + diff. Has a title, source_type, chunks for vector search. | Document, source, file |

² "Contributor" is fine in English prose, but in code the class is `MemberRecord`.

## Knowledge model

| Term               | Definition                                                                           | Aliases to avoid     |
| ------------------ | ------------------------------------------------------------------------------------ | -------------------- |
| **Topic**          | A canonical domain keyword extracted from Contributions or declared by a User as expertise. Canonicalized via the topic allowlist + alias map.  | Tag³, category, label |
| **Expertise**      | The Member↔Topic relationship, weighted by recency, contribution_type, and co-occurrence. Stored in the graph as edge weights, surfaced via `expertise_scores`. | Skill, knowledge     |
| **Declared skill** | A skill a User typed into their profile (`UserRecord.skills`). Distinct from **Expertise** — declared skills may be unbacked by any Contribution. | Profile tag          |
| **Strength**       | A topic a Member has been actively contributing to in the last 30 days (>=3 Contributions). Computed nightly by `strengths_weaknesses_service`. | - |
| **Weakness**       | A topic a Member had Contributions in 30-60 days ago but zero in the last 30. Signals expertise going stale. | Gap⁴                 |

³ `expertise_tags` the ORM field is fine, but in new code and in UI copy, say "topic" not "tag" unless specifically referring to the raw database column.

⁴ "Gap" is the Risk Radar concept (missing coverage at the Organization level), not the per-Member "Weakness".

## Surfacing patterns (the most overloaded area — read carefully)

| Term              | Definition                                                                        | Aliases to avoid     |
| ----------------- | --------------------------------------------------------------------------------- | -------------------- |
| **Insight**       | A free-form emergent pattern produced by `insight_engine` — old-generation, broader, often LLM-summarized. Surfaced on the Dashboard "Latest Insights" strip. | -                    |
| **Signal**        | A *specific* detected pattern from the nightly `pattern_detection` job: slow_lane, silent_area, load_skew, friday_land, review_bottleneck. Has severity + dedup_key + lifecycle (open/acknowledged/resolved). Lives on the Pulse > Signals tab. | Alert⁵, detection    |
| **RiskAlert**     | A risk-oriented finding from `risk_radar` (bus_factor risk, knowledge_gap, etc.). Has is_resolved, detected_at. Lives on the Pulse > Risk Radar tab. | Alert⁵, warning      |
| **HealthSnapshot**| Point-in-time team metrics: bus_factor_count, coverage_pct, collab_density, active_member_pct, avg_breadth, health_score. Written nightly. | Metric sample        |

⁵ **"Alert" is the single most overloaded word in the codebase.** Never use it alone. Always say **Signal** (from pattern_detection) or **RiskAlert** (from risk_radar). These are separate tables with separate lifecycles — conflating them in code or docs has caused bugs. When you need an umbrella term, say "surfaced finding".

## Periodic aggregates

| Term                   | Definition                                                                        | Aliases to avoid     |
| ---------------------- | --------------------------------------------------------------------------------- | -------------------- |
| **ContributionRollup** | Per-Member, per-window (7d/30d) precomputed counts, topic histogram, last_activity_at. Written nightly by `contribution_rollup_service`. | Member summary       |
| **HealthSnapshot**     | (above) — per-Org, not per-Member.                                               | -                    |
| **StrengthsWeaknessesSnapshot** | The `organizations.strengths_weaknesses_json` column: latest per-Org strengths, weaknesses, bus_factor list, top_members. Written by `strengths_weaknesses_service`. | -    |
| **Digest**             | The weekly email/Slack summary sent to Org members. The data payload is built by `digest_service.generate_weekly_digest`; delivery attempts are logged in **DigestLog**. | Newsletter, report   |
| **DigestLog**          | One audit row per delivery attempt (sent/failed/skipped). Separate from the Digest itself. | -                    |

**Do not say "snapshot" to mean "rollup".** A Snapshot is per-Org whole-team state; a Rollup is per-Member window state. They answer different questions.

## Decisions

| Term                 | Definition                                                                        | Aliases to avoid     |
| -------------------- | --------------------------------------------------------------------------------- | -------------------- |
| **Decision**         | An explicit choice extracted from Artifacts (via `decision_extraction`) or logged manually. Has context_summary, alternatives_considered, confidence_score, status (active/superseded/reverted). | Choice, resolution   |
| **DecisionOutcome**  | A retrospective note on how a prior Decision played out. Linked 1:many to a Decision. | Follow-up            |
| **DecisionLink**     | A relationship between two Decisions (supersedes, supports, conflicts_with).      | -                    |

## Relationships

- A **User** belongs to zero-or-more **Organizations** via **Memberships**. An Org always has at least one owner **User**.
- A **Member** belongs to exactly one **Organization** and optionally to zero-or-one **User** (via `UserRecord.linked_member_id`).
- An **Artifact** belongs to exactly one **Organization** and can have many **Contributions** from many **Members**.
- A **Contribution** belongs to exactly one **Member**, one **Organization**, and zero-or-one **Artifact**; carries a list of **Topics** and a `contribution_type` (git_commit, github_pr, slack_msg, …).
- A **WorkItem** belongs to one **Organization** and, when matchable, to one **Artifact**; its unique key is `(source, external_id, repo)`.
- A **Signal** belongs to one **Organization** and has a `dedup_key` so repeated nightly detections update a single open row.
- A **Digest** is *assembled* per-Organization on demand; its *deliveries* are rows in **DigestLog**.
- A **ContributionRollup** row is unique per `(Member, window_days, computed_at floor-to-day)`.
- A **HealthSnapshot** row is written per-Organization (nullable; system-wide when NULL) per nightly run.

## Example dialogue

> **Dev:** "The Pulse tab is 500ing — is it the **Signal** lookup that's broken, or the **RiskAlert** one?"
>
> **Domain expert:** "Different tables. Pulse > Signals reads the `signals` table (from `pattern_detection`). Pulse > Risk Radar reads `risk_alerts` (from `risk_radar`). The error_type in the 500 response tells you which."
>
> **Dev:** "Right. And the Team Health tab?"
>
> **Domain expert:** "That's `health_snapshots` via `team_health_service`. None of those three are **Insights** — **Insights** come from the older `insight_engine` and show on the Dashboard, not Pulse."
>
> **Dev:** "So when a Member hasn't contributed to a Topic in 30 days, that becomes what — a **Weakness**, a **Signal**, or an **Insight**?"
>
> **Domain expert:** "Depends on scope. At the **Member** level it's a **Weakness** (stored in `MemberRecord.weaknesses`, computed by `strengths_weaknesses_service`). At the **Organization** level, if *everyone* stopped contributing to that Topic, it becomes a `silent_area` **Signal** on the Pulse tab. Those are distinct things — don't rename one to match the other."
>
> **Dev:** "Got it — and the `cb_digests_sent_total` metric counts **Digest** deliveries, so it should increment once per **DigestLog** row."
>
> **Domain expert:** "Exactly. One **Digest** (the data) can produce many **DigestLog** rows (the deliveries: Slack, email fallback, in-app)."

## Flagged ambiguities (action items)

1. **"Alert"** is used in code comments to mean both `Signal` and `RiskAlert` — these are distinct tables. **Action:** grep the codebase for standalone "alert" in comments + strings, qualify or rename. Reject review comments that say "the alert system" without specifying which.
2. **"Tag"** appears as both `expertise_tags` (Topics declared on MemberRecord) and as UI chip labels for unrelated things (risk_summary top_risk, signal severity). **Action:** in new UI strings, call them "topics" if they refer to the knowledge graph, "chips" if they're purely visual affordances.
3. **"Activity"** is used loosely to mean both `Contribution` (the persisted attributed action) and a derived count like `ContributionRollup.contributions_count`. **Action:** when describing what the system *records*, say **Contribution**. When describing what it *displays* as a number, say "activity" qualified by the window ("7-day activity").
4. **"Snapshot"** vs **"Rollup"** drift. **Action:** a Rollup is per-Member + window; a Snapshot is per-Organization + point-in-time. The `team_health_service.save_health_snapshot` name is correct. The `contribution_rollup_service.save_health_snapshot` would be *wrong* if it existed — and it does not. Keep it that way.
5. **"Insight"** vs **"Signal"**. **Insights** are LLM-summarized freeform narratives from `insight_engine` (older Phase 4 feature). **Signals** are deterministic pattern-detection output (Phase 9/Week 9-10). They serve related but distinct purposes; don't consolidate without a migration plan.

## How to use this document

- **When writing new code**: if you name a class or column, grep this document first. If your concept already has a term here, reuse it. If you add a new term, add it to the right section and submit it with the PR.
- **When reviewing a PR**: if a variable name like `alert`, `snapshot`, `tag`, or `activity` appears without qualification, ask which canonical concept it refers to.
- **When debugging a 500**: the `error_type` in the response body often names an ORM class — map it back to the domain term here to understand what's really broken.
- **When onboarding a new contributor**: this is the fast path to "how the platform thinks". Read it before the ARCHITECTURE.md.
