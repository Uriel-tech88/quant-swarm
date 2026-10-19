#!/usr/bin/env python3
"""
bridge.py — run VibeTrading swarm presets against the quant-swarm universe.

Wires the quant swarm's 12 symbols (4 FX + 3 indices + 5 synthetics) into
VibeTrading's swarm teams. Requires `vibe-trading-ai` installed
(`pip install vibe-trading-ai`). The CLI module is `cli` (entry point
`vibe-trading -> cli:main`), so we invoke `python -m cli`.

Usage:
    python vibetrading/bridge.py --list
    python vibetrading/bridge.py --inspect macro_rates_fx_desk
    python vibetrading/bridge.py --preset quant_strategy_desk --market forex
    python vibetrading/bridge.py --preset macro_rates_fx_desk
    python vibetrading/bridge.py --preset investment_committee
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

# Per-preset variable names (from `python -m cli --swarm-inspect <preset>`).
PRESET_VARS = {
    "macro_rates_fx_desk":        ("goal", "timeframe"),
    "quant_strategy_desk":        ("market", "goal"),
    "technical_analysis_panel":   ("target", "timeframe"),
    "risk_committee":             ("goal",),
    "investment_committee":       ("market", "target"),
    "factor_research_committee":  ("market", "factor_type"),
    "commodity_research_team":    ("commodity", "horizon"),
    "derivatives_strategy_desk":  ("target", "view"),
    "sector_rotation_team":       ("market", "goal"),
    "etf_allocation_desk":        ("market", "risk_profile"),
    "global_allocation_committee": ("goal", "risk_tolerance"),
    "sentiment_intelligence_team": ("target", "timeframe"),
    "crypto_research_lab":        ("target", "timeframe"),
    "crypto_trading_desk":        ("target", "timeframe"),
    "earnings_research_desk":     ("target",),
    "event_driven_task_force":    ("market", "event_type"),
    "geopolitical_war_room":      ("crisis", "market"),
    "value_investing_committee":  ("target",),
    "credit_research_team":       ("target", "market"),
    "convertible_bond_team":      ("market", "goal", "strategy_type"),
    "pairs_research_lab":         ("market", "goal"),
    "statistical_arbitrage_desk": ("market", "goal"),
    "ml_quant_lab":               ("market", "goal"),
    "macro_strategy_forum":       ("goal", "timeframe"),
    "equity_research_team":       ("market", "goal"),
    "global_equities_desk":       ("goal", "risk_tolerance"),
    "fundamental_research_team":  ("target", "market"),
    "portfolio_review_board":     ("goal",),
    "fund_selection_panel":       ("fund_type", "goal"),
    "social_alpha_team":          ("market", "goal"),
}


def build_vars(preset: str, market: str, goal: str) -> dict:
    """Fill the preset's documented variables with sensible quant-swarm values."""
    symbols = SYMBOL_STRINGS.get(market, SYMBOL_STRINGS["all"])
    focus = MAP["presets"][preset]["focus"]
    ctx = {
        "goal": goal or f"{focus} across {symbols} (forex + indices + synthetics)",
        "market": market,
        "target": symbols,
        "timeframe": "1h",
        "horizon": "6m",
        "view": "neutral",
        "commodity": symbols,
        "factor_type": "momentum,value,quality,low-vol",
        "risk_profile": "balanced",
        "risk_tolerance": "moderate",
        "event_type": "macro,earnings,geopolitical",
        "crisis": "macro",
        "fund_type": "quant",
        "strategy_type": "systematic",
    }
    allowed = set(PRESET_VARS.get(preset, ("goal", "market", "target")))
    return {k: ctx[k] for k in allowed if k in ctx}


def run_preset(preset: str, market: str, goal: str) -> int:
    if preset not in MAP["presets"]:
        print(f"unknown preset '{preset}'. run --list", file=sys.stderr)
        return 2
    ctx = build_vars(preset, market, goal)
    cmd = [sys.executable, "-m", "cli", "--swarm-run", preset, json.dumps(ctx)]
    print(">>> " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="list presets + mapping")
    ap.add_argument("--inspect", metavar="PRESET", help="show a preset's DAG (via cli)")
    ap.add_argument("--preset", help="VibeTrading preset name")
    ap.add_argument("--market", default="all",
                    choices=list(SYMBOL_STRINGS.keys()), help="symbol universe")
    ap.add_argument("--goal", default="", help="override the goal string")
    a = ap.parse_args()

    if a.list:
        for name, m in MAP["presets"].items():
            print(f"{name:28s} -> {m['stage']:12s} | {m['focus']}")
        return 0

    if a.inspect:
        return subprocess.call(
            [sys.executable, "-m", "cli", "--swarm-inspect", a.inspect])

    if not a.preset:
        ap.print_help()
        return 1

    return run_preset(a.preset, a.market, a.goal)


if __name__ == "__main__":
    raise SystemExit(main())
