#!/usr/bin/env python3
"""
bridge.py — run VibeTrading swarm presets against the quant-swarm universe.

Wires the quant swarm's 12 symbols (4 FX + 3 indices + 5 synthetics) into
VibeTrading's swarm teams. Requires `vibe-trading-ai` installed
(`pip install vibe-trading-ai`).

Usage:
    python vibetrading/bridge.py --preset quant_strategy_desk --market forex
    python vibetrading/bridge.py --preset macro_rates_fx_desk
    python vibetrading/bridge.py --preset investment_committee
    python vibetrading/bridge.py --list
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAP = json.loads((REPO / "vibetrading" / "presets_map.json").read_text())

SYMBOL_STRINGS = {
    "forex":      "EURUSD GBPUSD USDJPY AUDUSD",
    "indices":    "^GSPC ^DJI ^IXIC",
    "synthetics": "GLD SLV USO TLT GC=F",
    "all":        "EURUSD GBPUSD USDJPY AUDUSD ^GSPC ^DJI ^IXIC GLD SLV USO TLT GC=F",
}


def run_preset(preset: str, market: str, extra: str) -> int:
    if preset not in MAP["presets"]:
        print(f"unknown preset '{preset}'. run --list", file=sys.stderr)
        return 2

    # market/goal context VibeTrading presets expect as JSON input
    ctx = {
        "market": market,
        "goal": extra or f"backtest {MAP['presets'][preset]['focus']} on "
                        f"{SYMBOL_STRINGS.get(market, SYMBOL_STRINGS['all'])}",
        "symbols": SYMBOL_STRINGS.get(market, SYMBOL_STRINGS["all"]),
    }

    cmd = [
        sys.executable, "-m", "vibe_trading",
        "--swarm-run", preset, json.dumps(ctx),
    ]
    print(">>> " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="list presets + mapping")
    ap.add_argument("--preset", help="VibeTrading preset name")
    ap.add_argument("--market", default="all",
                    choices=list(SYMBOL_STRINGS.keys()), help="symbol universe")
    ap.add_argument("--goal", default="", help="override the goal string")
    a = ap.parse_args()

    if a.list:
        for name, m in MAP["presets"].items():
            print(f"{name:28s} -> {m['stage']:12s} | {m['focus']}")
        return 0

    if not a.preset:
        ap.print_help()
        return 1

    return run_preset(a.preset, a.market, a.goal)


if __name__ == "__main__":
    raise SystemExit(main())
