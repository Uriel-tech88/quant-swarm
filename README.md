# Quant Trading Agent Swarm

A self-improving swarm of Hermes agents for quantitative trading research.

## Features
- Multi-symbol data pipeline (FX, indices, synthetics)
- Data quality validation (Free Data Trap protection)
- ML/Agents: FinMLKit, vectorbt, stable-baselines3, Ray
- Backtesting and stress testing (QuantStats, StrategyQuant)
- Cloud execution via GitHub Actions (free tier)
- Local private execution options

## Quick Start

### Local Execution (Private, no cloud)
```bash
# Run once
python data/pipeline_finmlkit.py

# Or use the local runner (every 5 minutes)
python run_local_continuous.py
```

### GitHub Actions (Public, free cloud execution)
1. Push this repository to GitHub (public or private).
2. Go to Settings > Secrets and add:
   - `TELEGRAM_BOT_TOKEN` (optional, for Telegram notifications)
   - `TELEGRAM_CHAT_ID` (optional, for Telegram notifications)
3. The workflow `.github/workflows/quant_swarm_loop.yml` will run every 5 minutes.
4. Check the Actions tab for runs and download artifacts.

## Data Sources
- Yahoo Finance (via yfinance) - FX, indices, ETFs
- Alpaca Markets API (free developer account) - equities and crypto
- FRED API (St. Louis Fed) - macroeconomic data
- OpenBB Terminal - free Bloomberg alternative
- Plus institutional sources: Kaggle, Firstrate, IB TWS, Databento, OSF, LOBSTER (see quant-data-sources skill)

## Security
- No API keys or secrets are stored in the repository.
- Use GitHub Secrets for any required tokens.
- The `.gitignore` file excludes common sensitive files and directories.

## License
MIT
