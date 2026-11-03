"""
CLI entry for the MoonDev-style analysis pass.

Usage (from repo root, Hermes bundled Python):
  python -m moondev.run_moondev --symbols EURUSDX GBPUSDX
  python -m moondev.run_moondev --symbols EURUSDX --allocate 10000
  python -m moondev.run_moondev --list

Free by default (nvidia/nemotron-3-ultra-550b-a55b:free); override with
--model or MOONDEV_MODEL env var.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .agent import MoonDevAgent
from .data_adapter import available_symbols

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def main():
    ap = argparse.ArgumentParser(description="MoonDev-style LLM analysis on swarm data")
    ap.add_argument("--symbols", nargs="+", default=["EURUSDX"],
                    help="Feature-store keys, e.g. EURUSDX GBPUSDX ^GSPC GLD")
    ap.add_argument("--model", default=None, help="OpenRouter model slug")
    ap.add_argument("--allocate", type=float, default=None,
                    help="Optional portfolio size in USD for the allocation pass")
    ap.add_argument("--list", action="store_true", help="List available symbols and exit")
    args = ap.parse_args()

    if args.list:
        print("Available:", ", ".join(available_symbols()))
        return 0

    agent = MoonDevAgent(model=args.model)
    print(f"Model: {agent.model}")
    print(f"Analyzing {len(args.symbols)} symbol(s)...\n")

    recs = agent.run_once(args.symbols)

    print("\n=== Recommendations ===")
    print(recs[["symbol", "action", "confidence"]].to_string(index=False))

    allocation = None
    if args.allocate:
        allocation = agent.allocate(args.allocate)
        print(f"\n=== Allocation of ${args.allocate:,.0f} ===")
        for k, v in allocation.items():
            if isinstance(v, (int, float)):
                print(f"  {k}: ${v:,.2f}")
            else:
                print(f"  {k}: {v}")

    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RUNS_DIR / f"{stamp}_recommendations.csv"
    recs.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
