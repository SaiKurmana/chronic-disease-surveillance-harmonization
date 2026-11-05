"""CLI: ``python -m ingest [--domain diabetes|vision|kidney|all] [--force]``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ingest import diabetes, kidney, vision
from ingest.storage import RAW_DIR

MODULES = {"diabetes": diabetes, "vision": vision, "kidney": kidney}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="all", choices=["all", *MODULES])
    parser.add_argument("--force", action="store_true", help="re-pull even if unchanged")
    parser.add_argument("--root", type=Path, default=RAW_DIR, help="raw zone directory")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    domains = list(MODULES) if args.domain == "all" else [args.domain]
    failures = []
    for d in domains:
        try:
            MODULES[d].run(force=args.force, root=args.root)
        except Exception as exc:  # keep going so one outage does not block others
            logging.getLogger("ingest").error("%s domain failed: %s", d, exc)
            failures.append(d)
    if failures:
        logging.getLogger("ingest").error("failed domains: %s", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
