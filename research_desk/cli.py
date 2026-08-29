"""research-desk command-line interface.

Subcommands:
  once       run a single pipeline cycle and print the brief
  run        run continuously on the configured poll interval
  brief      print the most recent brief markdown
  feedback   record a label for a claim id (learning loop)
  sources    list known sources and their trust scores
  config     print the resolved config
"""
from __future__ import annotations

import argparse
import sys
import time

from .desk import ResearchDesk


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="research-desk",
                                description="Real-time X news intelligence desk")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("once", help="run one pipeline cycle")
    run = sub.add_parser("run", help="run continuously")
    run.add_argument("--max-cycles", type=int, default=0,
                     help="stop after N cycles (0 = forever)")

    sub.add_parser("brief", help="print the latest brief")
    sub.add_parser("sources", help="list sources and trust")

    fb = sub.add_parser("feedback", help="label a claim for the learning loop")
    fb.add_argument("claim_id")
    fb.add_argument("label", choices=[
        "useful", "not_useful", "rumor", "too_local",
        "too_political", "want_more"])

    cfg = sub.add_parser("config", help="show resolved config")
    cfg.add_argument("--path", default=None, help="config.toml path")

    p.add_argument("--config", default=None, help="path to config.toml")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    desk = ResearchDesk(config_path=args.config)

    if args.cmd == "once":
        desk.cycle()
        print("\n" + desk.latest_brief())
        desk.close()
        return 0

    if args.cmd == "run":
        print(f"[desk] engine={desk.engine}; cycling every "
              f"{desk.config.poll_interval}s (Ctrl-C to stop)")
        cycles = 0
        try:
            while True:
                desk.cycle()
                cycles += 1
                if args.max_cycles and cycles >= args.max_cycles:
                    break
                time.sleep(desk.config.poll_interval)
        except KeyboardInterrupt:
            print("\n[desk] stopped")
        desk.close()
        return 0

    if args.cmd == "brief":
        print(desk.latest_brief())
        desk.close()
        return 0

    if args.cmd == "sources":
        for s in sorted(desk.vault.all_sources(),
                        key=lambda x: x.trust, reverse=True):
            print(f"{s.handle:<24} {s.tier.value:<18} trust={s.trust:.2f} "
                  f"conf={s.confirmations} miss={s.misses}")
        desk.close()
        return 0

    if args.cmd == "feedback":
        desk.feedback(args.claim_id, args.label)
        desk.close()
        return 0

    if args.cmd == "config":
        import json
        print(json.dumps(desk.config.raw, indent=2, default=str))
        desk.close()
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
