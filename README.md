# Quant Trading Agent Swarm

A self-improving Hermés agents for quant trading — multi-symbol pipeline (FX + indices + synthetics) with free data sources, data quality validation, stress testing, and cloud execution.

## Essentials
- FinMLKit pipeline: dollar bars + triple-barrier labels
- Multi-source data: yfinance + simulated OANDA ticks
- RL training: FinRL + Stable-Baselines3
- Backtesting: vectorbt, QuantStats, StrategyQuant EA Analyzer
- Cloud: GitHub Actions (every 5 min, free tier)
- Local: run_local_continuous.py (private, no cloud)

## Files
- `.github/workflows/quant_swarm_loop.yml` — GitHub Actions workflow
- `quant_swarm/data/pipeline_finmlkit.py` — data pipeline
- `quant_swarm/skills/quant-data-sources/SKILL.md` — free data sources
- `.gitignore` — ignores raw data + generated files
- `README.md` — this file

## How to use

### Local
```bash
python quant_swarm/data/pipeline_finmlkit.py
```

### GitHub Actions
Push to GitHub — workflow auto-runs every 5 min.

## Security
No API keys or secrets in repo. Add as GitHub secrets if needed.
