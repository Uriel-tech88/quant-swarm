---
name: quant-dev
description: "Quant Development Agent — TWAP/VWAP execution simulation, algorithmic execution patterns."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [quant, trading, execution, algorithms, twap, vwap]
    category: software-development
---

# Quant Dev Agent — Algorithmic Execution

Reusable procedures for implementing and simulating algorithmic execution strategies (TWAP, VWAP) in the Quant Swarm.

## What This Agent Does

The Quant Dev Agent builds, tests, and validates execution algorithms that break large orders into smaller slices to minimize market impact and transaction costs. It outputs validated Python modules under `quant_swarm/skills/quant-dev/` plus runnable simulations with evidence files.

## Scope

| Algorithm | Purpose | Output |
|-----------|---------|--------|
| TWAP (Time-Weighted Average Price) | Slice orders by equal time intervals | `quant_swarm/skills/quant-dev/twap_vwap_simulation.py` |
| VWAP (Volume-Weighted Average Price) | Slice orders by historical volume profile | `quant_swarm/backtests/execution_sim_results/` |
| Implementation Shortfall | Minimize cost vs. decision price | Skill documentation |

## Non-Scope

| Category | Reason |
|----------|--------|
| Live trading execution | Paper/sim only (per plan Section 2) |
| Paid market data | All free sources (Yahoo Finance, ccxt public) |
| Hardware trading bots | Software simulation only |

## Installation (Free Libraries)

```bash
pip install pandas numpy plotly requests yfinance
```

## Usage

```bash
# Run TWAP/VWAP execution simulation
cd quant_swarm
python -m skills.quant-dev.twap_vwap_simulation

# Results: quant_swarm/backtests/execution_sim_results/
```

## File Structure

```
skills/quant-dev/
├── SKILL.md                    # This file
├── twap_vwap_simulation.py     # Executable TWAP/VWAP sim
└── __init__.py
```

## Execution Evidence

Each simulation run produces:
- `execution_trace.csv` — trade-by-trade execution path
- `cost_analysis.json` — VWAP/TWAP implementation shortfall
- `slippage_report.md` — human-readable analysis
- `execution_charts.html` — volume profile + execution path visualization

## Verification Commands

```bash
# Sanity check: simulate execution and validate outputs
python -m skills.quant-dev.twap_vwap_simulation --check

# Validate output files exist and are non-empty
ls -l backtests/execution_sim_results/*.{csv,json,md,html}
```

## Best Practices

1. Always simulate before live deployment
2. Compare against both TWAP and VWAP benchmarks
3. Use walk-forward validation on execution quality
4. Record all execution decisions for memory persistence
5. Respect data rate limits (Yahoo Finance 1 req/sec)

## Related Skills

- `quant-data-sources` — acquire tick data
- `omh-data-pipelines` — ETL workflows
- `vectorbt` — backtesting

## License

MIT — free & open-source, per plan Section 2 (Non-Goals).
