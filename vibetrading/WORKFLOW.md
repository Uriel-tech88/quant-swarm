# VibeTrading ↔ Quant Swarm Integration

## What VibeTrading adds that the quant swarm doesn't have

The HKUDS/Vibe-Trading repo (35K stars) is a full finance research platform.
Its workflow is: **Route → Ground → Test → Deliver**, backed by **30 swarm
presets** (multi-agent DAGs), **11 backtesting engines**, **18 data sources**,
and a **React/FastAPI Web UI** with live charts.

Your 7-agent swarm already covers: research (SSRN), data, quant dev, RL,
backtest, portfolio (HRP), synthesis. VibeTrading adds the *agent teams* and
the *charting/UI layer* on top.

---

## The 30 swarm presets (agent teams)

Source: `vibe-trading --swarm-presets`. Mapped to your swarm's stages:

| # | Preset | Workflow | Maps to your agent |
|---|--------|----------|--------------------|
| 1 | investment_committee | Bull/bear debate → risk review → PM call | synthesis |
| 2 | macro_rates_fx_desk | Rates + FX + commodity → macro PM | research (FX focus) |
| 3 | quant_strategy_desk | Screener + factor → backtest → risk audit | quant dev + backtest |
| 4 | risk_committee | Drawdown + tail risk + regime → sign-off | portfolio |
| 5 | technical_analysis_panel | TA + Ichimoku + harmonic + Elliott + SMC → consensus | quant dev |
| 6 | global_allocation_committee | Cross-market allocation | portfolio |
| 7 | global_equities_desk | A-share + HK/US + crypto → strategist | research |
| 8 | earnings_research_desk | Fundamental + revision + options | research |
| 9 | crypto_trading_desk | Funding/basis + liquidation + flow | (crypto ext) |
| 10 | etf_allocation_desk | ETF screening + macro → risk parity/MVO | portfolio |
| 11 | sector_rotation_team | Cycle mapping → rotation backtest | backtest |
| 12 | sentiment_intelligence_team | News/social/flow → sentiment score | research |
| 13 | value_investing_committee | Buffett/Munger/Duan/Li Lu + chair | synthesis |
| 14 | ml_strategy_desk | Feature eng → ML train → perf audit | RL + quant dev |
| 15 | pairs_trading_desk | Cointegration mining → mean-reversion | quant dev |
| 16-30 | +15 specialist presets | (run `--swarm-presets` for the rest) | — |

## The VibeTrading research loop (4 stages)

```
01 Route     — pick skills, data sources, tools, swarm team from the request
02 Ground    — fetch market data, docs, URLs, broker journals, local files
03 Test      — backtests, factor analysis, options checks, validation
04 Deliver   — run cards, exports, reports, tool traces, caveats
```

## Integration points (what's wired)

1. **Data bridge** — your `raw/*.csv` and `features/*.csv` feed VibeTrading's
   `local` loader (reads CSV/Parquet/DuckDB directly). No re-download.
2. **MT5 forex data** — VibeTrading's MetaTrader 5 connector adds tick-level
   FX data alongside your yfinance 1m pipeline.
3. **Swarm bridge** — `bridge.py` invokes any VibeTrading preset against your
   12 symbols (4 FX + 3 indices + 5 synthetics).
4. **Web UI** — VibeTrading's React dashboard (candlestick charts, Run Detail,
   correlation matrix, Portfolio Studio) replaces the static
   `cyberpunk_dashboard.html`.

## Commands

```sh
# list all 30 presets (CLI module is `cli`, not a standalone binary)
python -m cli --swarm-presets

# inspect a preset's agents + DAG
python -m cli --swarm-inspect macro_rates_fx_desk

# run the quant desk against your FX universe
python vibetrading/bridge.py --preset quant_strategy_desk --market forex

# run the macro FX desk
python vibetrading/bridge.py --preset macro_rates_fx_desk

# run the full committee
python vibetrading/bridge.py --preset investment_committee

# launch the Web UI (charts)
python -m cli init && python -m cli dev
```

## Preset → quant-swarm agent mapping (JSON)

See `presets_map.json` for the machine-readable mapping used by `bridge.py`.
