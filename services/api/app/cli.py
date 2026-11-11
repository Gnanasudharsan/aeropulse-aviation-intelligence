"""Command-line entry points.

python -m app.cli seed                 # load airport dimension
python -m app.cli ingest faa|metar|taf|all
python -m app.cli worker               # run the scheduler (blocking)
python -m app.cli purge-bronze
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.seed import seed_airports
from app.db.session import session_scope
from app.ingestion.jobs import JOBS, run_maintenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aeropulse")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    ing = sub.add_parser("ingest")
    ing.add_argument("job", choices=[*JOBS, "all"])
    sub.add_parser("worker")
    sub.add_parser("purge-bronze")
    args = parser.parse_args(argv)

    # Human-readable logs in a terminal, JSON lines in containers / CI.
    configure_logging(get_settings().log_level, json=not sys.stdout.isatty())

    if args.cmd == "seed":
        with session_scope() as s:
            print(f"seeded {seed_airports(s)} airports")
        return 0
    if args.cmd == "ingest":
        names = list(JOBS) if args.job == "all" else [args.job]
        failed = False
        for name in names:
            summary = asyncio.run(JOBS[name](trigger="manual"))
            failed |= summary.status == "failed"
            print(json.dumps(_summary(summary), default=str))
        return 1 if failed else 0
    if args.cmd == "worker":
        from app.worker import run_worker

        asyncio.run(run_worker())
        return 0
    if args.cmd == "purge-bronze":
        print(f"purged {run_maintenance()} bronze rows")
        return 0
    return 2


def _summary(summary: object) -> dict[str, object]:
    fields = ("job", "run_id", "status", "fetched", "inserted", "updated", "rejected", "error")
    return {f: getattr(summary, f) for f in fields}


if __name__ == "__main__":
    sys.exit(main())
