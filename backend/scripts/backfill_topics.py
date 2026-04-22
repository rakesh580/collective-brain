"""CLI entrypoint for re-canonicalizing topics already in the database.

Run from the backend directory:
    python -m scripts.backfill_topics          # apply changes
    python -m scripts.backfill_topics --dry-run # just print counts
"""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verbose", action="store_true", help="Enable INFO logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Import after argparse so --help doesn't trigger DB init
    from app.db.database import create_session, init_db
    from app.services.topic_backfill import run_topic_backfill

    init_db()
    db = create_session()
    try:
        result = run_topic_backfill(db, dry_run=args.dry_run)
    finally:
        db.close()

    sys.stdout.write(
        "Backfill"
        f" {'(dry-run) ' if args.dry_run else ''}—"
        f" contributions: {result.contributions_scanned} scanned,"
        f" {result.contributions_changed} changed;"
        f" members: {result.members_scanned} scanned,"
        f" {result.members_changed} changed\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
