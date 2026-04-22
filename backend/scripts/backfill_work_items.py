"""One-time backfill of GitHub PR + issue history into ``work_items``.

Pulls the last N days (default 90) of PRs and issues for each provided repo
via the GitHub REST API and upserts them via the same
``_upsert_work_item`` path the live webhook handler uses — so state
transitions, cycle-time computation, and idempotency all match.

Usage:
    python -m scripts.backfill_work_items --repo owner/repo [--repo other/repo] \\
        --token $GITHUB_TOKEN [--days 90] [--dry-run]

Auth: requires a GitHub personal access token (``repo`` scope for private
repos, none needed for public). Rate-limit aware: sleeps when the
``X-RateLimit-Remaining`` header drops below a safe threshold.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger("collective_brain.backfill.work_items")

GITHUB_API = "https://api.github.com"
_RATE_LIMIT_FLOOR = 50  # pause when this few requests remain


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "collective-brain-backfill/1.0",
    }


def _respect_rate_limit(resp: httpx.Response) -> None:
    """Sleep briefly when close to the rate-limit ceiling."""
    remaining = resp.headers.get("X-RateLimit-Remaining")
    reset = resp.headers.get("X-RateLimit-Reset")
    if remaining is None or reset is None:
        return
    try:
        r = int(remaining)
        reset_at = int(reset)
    except ValueError:
        return
    if r < _RATE_LIMIT_FLOOR:
        wait = max(0, reset_at - int(time.time()))
        logger.warning("GitHub rate limit low (remaining=%d). Sleeping %ds until reset.", r, wait)
        time.sleep(wait + 1)


def _paginate(
    client: httpx.Client,
    url: str,
    *,
    token: str,
    params: dict[str, Any],
    since: datetime | None = None,
) -> Iterator[dict]:
    """Iterate through every page. Stops when created_at < since."""
    page = 1
    params = dict(params, per_page=100, page=page)
    while True:
        params["page"] = page
        resp = client.get(url, headers=_headers(token), params=params, timeout=30)
        _respect_rate_limit(resp)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            return
        for item in items:
            created_at = _parse_ts(item.get("created_at"))
            if since is not None and created_at is not None and created_at < since:
                return
            yield item
        # GitHub uses Link header "rel=next" for pagination; a short-circuit
        # on an empty page covers the final case for either approach.
        if len(items) < params["per_page"]:
            return
        page += 1


def backfill_repo(
    repo: str,
    *,
    token: str,
    days: int,
    dry_run: bool,
) -> dict[str, int]:
    """Run the backfill for a single ``owner/repo``."""
    since = datetime.now(UTC) - timedelta(days=days)
    counts = {"prs": 0, "issues": 0, "skipped": 0}

    # Local imports so --help stays fast and doesn't touch the DB.
    from app.db.database import create_session, init_db
    from app.ingestion.topic_extractor import (
        canonicalize_list,
        extract_topics_from_commit,
        extract_topics_from_labels,
    )
    from app.services.github_event_processor import (
        _parse_ts as processor_parse_ts,
    )
    from app.services.github_event_processor import (
        _pr_state,
        _upsert_work_item,
    )

    init_db()
    db = create_session()

    try:
        with httpx.Client(base_url=GITHUB_API) as client:
            # ── PRs ────────────────────────────────────────────────────────
            pr_url = f"/repos/{repo}/pulls"
            for pr in _paginate(
                client,
                pr_url,
                token=token,
                params={"state": "all", "sort": "created", "direction": "desc"},
                since=since,
            ):
                title = pr.get("title", "") or ""
                labels = [lbl.get("name", "") for lbl in pr.get("labels", [])]
                topics = canonicalize_list(
                    extract_topics_from_labels(labels) + extract_topics_from_commit(title, []),
                )
                merged = pr.get("merged_at") is not None
                raw_state = pr.get("state", "")
                action = "closed" if raw_state == "closed" else "opened"
                state = _pr_state(action, merged, raw_state)

                if dry_run:
                    counts["prs"] += 1
                    continue

                _upsert_work_item(
                    db,
                    source="github_pr",
                    external_id=str(pr.get("number")),
                    repo=repo,
                    title=title,
                    state=state,
                    author_member_id=None,  # member resolution deferred
                    created_at=processor_parse_ts(pr.get("created_at")),
                    completed_at=processor_parse_ts(pr.get("merged_at") or pr.get("closed_at")),
                    labels=labels,
                    topics=topics,
                )
                counts["prs"] += 1

            # ── Issues ─────────────────────────────────────────────────────
            # The issues endpoint also returns PRs — filter those out since
            # we already processed them via /pulls.
            issue_url = f"/repos/{repo}/issues"
            for issue in _paginate(
                client,
                issue_url,
                token=token,
                params={
                    "state": "all",
                    "since": since.isoformat(),
                    "sort": "created",
                    "direction": "desc",
                },
                since=since,
            ):
                if "pull_request" in issue:
                    counts["skipped"] += 1
                    continue

                title = issue.get("title", "") or ""
                labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
                topics = canonicalize_list(
                    extract_topics_from_labels(labels) + extract_topics_from_commit(title, []),
                )
                state = "closed" if issue.get("state") == "closed" else "open"

                if dry_run:
                    counts["issues"] += 1
                    continue

                _upsert_work_item(
                    db,
                    source="github_issue",
                    external_id=str(issue.get("number")),
                    repo=repo,
                    title=title,
                    state=state,
                    author_member_id=None,
                    created_at=processor_parse_ts(issue.get("created_at")),
                    completed_at=processor_parse_ts(issue.get("closed_at")) if state == "closed" else None,
                    labels=labels,
                    topics=topics,
                )
                counts["issues"] += 1

        if not dry_run:
            db.commit()
    finally:
        db.close()

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        help="owner/repo (repeatable)",
    )
    parser.add_argument("--token", required=True, help="GitHub personal access token")
    parser.add_argument("--days", type=int, default=90, help="Backfill window in days")
    parser.add_argument("--dry-run", action="store_true", help="Count only, do not write")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    totals = {"prs": 0, "issues": 0, "skipped": 0}
    for repo in args.repo:
        logger.info("Backfilling %s (last %d days, dry_run=%s)", repo, args.days, args.dry_run)
        counts = backfill_repo(repo, token=args.token, days=args.days, dry_run=args.dry_run)
        for k, v in counts.items():
            totals[k] += v
        sys.stdout.write(f"{repo}: prs={counts['prs']} issues={counts['issues']} skipped={counts['skipped']}\n")

    sys.stdout.write(
        f"TOTAL: prs={totals['prs']} issues={totals['issues']} "
        f"skipped={totals['skipped']}{' (dry-run)' if args.dry_run else ''}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
