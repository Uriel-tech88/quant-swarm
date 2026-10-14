# Strategy Swarm — SSRN 151 Categories Processing & Backtesting

**Created:** 2026-10-11  
**Profile:** default  
**Status:** Draft — extends Quant Swarm Phase 2

---

## 1. Goal

Build a **specialized swarm** that systematically:
- **Ingests** the 151 standard academic trading strategy categories from SSRN
- **Maps** each category to implementable strategy specifications
- **Backtests** every strategy on forex/equity/crypto data via vectorbt
- **Improves** only when statistically significant edge exists (Sharpe > 1.5, DD < 15%)
- **Persists** validated strategies as skills for live trading agents

---

## 2. The 151 Strategy Categories (SSRN Standard)

Based on SSRN's JEL classification and academic literature, the 151 categories map to:

| Super-Category | # Strategies | Examples |
|----------------|--------------|----------|
| **Mean Reversion** | 18 | Bollinger Bands, RSI, Z-score pairs, Ornstein-Uhlenbeck |
| **Momentum/Trend** | 22 | Dual MA, MACD, ADX, Channel breakout, Time-series momentum |
| **Statistical Arbitrage** | 15 | Cointegration, PCA, Kalman filter, Factor models |
| **Market Making** | 12 | Avellaneda-Stoikov, Inventory risk, Adverse selection |
| **Execution Algorithms** | 10 | TWAP, VWAP, POV, Implementation shortfall, Almgren-Chriss |
| **Factor Investing** | 18 | Value, Momentum, Quality, Low vol, Carry, Betting against beta |
| **Portfolio Optimization** | 12 | HRP, Black-Litterman, Risk Parity, CVaR, Max Diversification |
| **Regime Switching** | 8 | HMM, Markov switching, Volatility targeting, CPPI |
| **Machine Learning** | 14 | LSTM, Transformer, Random Forest, XGBoost, RL (PPO/SAC) |
| **Alternative Data** | 8 | News sentiment, Satellite, Order flow, Options flow |
| **Crypto/DeFi** | 8 | Funding rates, Basis trading, MEV, Yield farming |
| **Options/Volatility** | 6 | Dispersion, Variance risk premium, Gamma scalping |

---

## 3. Strategy Swarm Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STRATEGY ORCHESTRATOR                        │
│  (Daily cron → coordinates 151 strategy pipeline)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  INGESTION    │  │  SPECIFICATION│  │  BACKTEST     │
│  AGENT        │  │  AGENT        │  │  AGENT        │
│  (SSRN/arXiv) │  │  (151 cats)   │  │  (vectorbt)   │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  IMPROVEMENT  │  │  VALIDATION   │  │  DEPLOYMENT   │
│  AGENT        │  │  AGENT        │  │  AGENT        │
│  (if needed)  │  │  (stats sig)  │  │  (skill gen)  │
└───────────────┘  └───────────────┘  └───────────────┘
```

---

## 4. Agent Specifications

### 4.1 Ingestion Agent (Daily 5 AM)
**Inputs:** SSRN RSS, arXiv q-fin, SSRN search API, manual PDF uploads  
**Outputs:** `research/papers/ssrn/`, `research/papers/arxiv/` — raw papers with metadata  
**Tools:** `ssrn_fetcher.py`, `arxiv_fetcher.py`, PDF parser (PyMuPDF)

### 4.2 Specification Agent (Daily 6 AM)
**Inputs:** Raw papers from Ingestion  
**Process:** 
1. Classify paper into 1 of 151 categories
2. Extract strategy logic using LLM (openrouter/free)
3. Map to `strategy_schema.yaml`
3. Output: `research/strategies/<category>/<strategy_id>.yaml`
**Model:** `deepseek/deepseek-v4-flash:free` (best for structured extraction)

### 4.3 Backtest Agent (Daily 7 AM — parallel per category)
**Inputs:** Strategy specs from Specification Agent  
**Process:**
1. Generate vectorbt-compatible signal code from spec
2. Run on multi-symbol data (forex: 4 pairs, equity: 10 tickers, crypto: 5)
3. Metrics: Sharpe, Sortino, Calmar, Max DD, Win Rate, Profit Factor, Turnover
4. Statistical significance: t-test vs buy-and-hold, bootstrap confidence intervals
**Outputs:** `backtests/strategies/<category>/<strategy_id>/` — results + HTML tearsheets

### 4.4 Improvement Agent (Weekly)
**Inputs:** Backtest results where `Sharpe ∈ [1.0, 1.5]` or `DD ∈ [15%, 25%]`
**Process:**
1. Identify weakness: high DD → add regime filter, low Sharpe → ensemble, high turnover → execution optimization
2. Generate improved variant spec
3. Re-backtest variant
4. Accept only if: `ΔSharpe > 0.2` AND `ΔDD < -2%` (statistically significant)
**Outputs:** Improved strategy specs in `research/strategies/improved/`

### 4.5 Validation Agent (Weekly)
**Inputs:** All backtested strategies  
**Criteria for "Validated":**
- Out-of-sample Sharpe > 1.5 (p < 0.05 vs benchmark)
- Max DD < 15%
- Win rate > 50%
- Profit factor > 1.3
- Stable across ≥3 asset classes
- Transaction cost robust (survives 2x cost)
**Outputs:** `research/strategies/validated/` — promotion to skills

### 4.6 Deployment Agent (On validation)
**Inputs:** Validated strategies  
**Process:**
1. Generate `SKILL.md` with full implementation
2. Create integration test in Quant Dev Agent
3. Add to orchestrator cron for paper trading
4. Update Telegram briefing with new strategy
**Outputs:** `skills/strategy-<category>-<name>.md`, updated cron

---

## 5. Data Pipeline Integration

```
SSRN/arXiv Papers (151 cats)
        ↓
Strategy Specification (YAML per strategy)
        ↓
Signal Generation (vectorbt-compatible)
        ↓
Multi-Asset Backtest (forex/equity/crypto)
        ↓
Statistical Validation (bootstrap, t-test)
        ↓
Improvement Loop (if near-threshold)
        ↓
Validated → Skill Generation → Orchestrator
```

---

## 6. Directory Structure

```
quant_swarm/
├── research/
│   ├── papers/
│   │   ├── ssrn/           # Raw SSRN papers
│   │   └── arxiv/          # Raw arXiv papers
│   └── strategies/
│       ├── raw/            # Extracted specs (151 cats × N strategies)
│       ├── improved/       # Improved variants
│       └── validated/      # Statistically validated
├── backtests/
│   └── strategies/
│       ├── mean_reversion/
│       ├── momentum/
│       ├── stat_arb/
│       ├── market_making/
│       ├── execution/
│       ├── factor/
│       ├── portfolio_opt/
│       ├── regime/
│       ├── ml/
│       ├── alt_data/
│       ├── crypto/
│       └── options/
├── skills/
│   ├── strategy-mean_reversion-bollinger.md
│   ├── strategy-momentum-dual_ma.md
│   └── ... (one per validated strategy)
└── logs/
    └── strategy_orchestrator.log
```

---

## 7. Cron Jobs (Hermes)

| Job | Schedule | Skills | Deliver |
|-----|----------|--------|---------|
| **Ingestion** | 5 AM daily | `ssrn_fetcher`, `arxiv_fetcher` | `origin` |
| **Specification** | 6 AM daily | `strategy_specifier` | `origin` |
| **Backtest** | 7 AM daily | `vectorbt_backtest` (parallel) | `origin` |
| **Improvement** | Sun 2 AM | `strategy_improver` | `origin` |
| **Validation** | Mon 3 AM | `strategy_validator` | `origin` |
| **Deployment** | On validation | `skill_generator` | `origin` |
| **Orchestrator** | 8 AM daily | `strategy_orchestrator` | `origin` |

---

## 8. Acceptance Criteria

| Criterion | Threshold |
|-----------|-----------|
| 151 categories covered | ≥140 categories have ≥1 strategy |
| Strategies backtested | ≥500 total backtests |
| Validated strategies | ≥25 strategies pass all criteria |
| Skills generated | ≥25 `SKILL.md` files |
| Sharpe (validated) | > 1.5 out-of-sample |
| Max DD (validated) | < 15% |
| Transaction cost robust | Survives 2× slippage |
| Cross-asset stability | Works on ≥3 asset classes |

---

## 9. Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| Overfitting to backtest | Walk-forward analysis, purged K-fold, out-of-sample |
| Data snooping bias | Strict separation: train/validate/test, no peeking |
| SSRN access blocked | Multiple fallback sources (RSS, Google Scholar, manual) |
| Compute time (500+ backtests) | Vectorbt parallelization, GPU, GitHub Actions distributed |
| False positives | Multiple testing correction (Bonferroni), pre-registration |

---

## 10. Integration with Quant Swarm

| Quant Swarm Agent | Strategy Swarm Connection |
|-------------------|---------------------------|
| **Research Agent** | Feeds Strategy Swarm with papers |
| **Data Agent** | Provides clean feature store for backtests |
| **Quant Dev Agent** | Implements validated strategies as skills |
| **RL Training Agent** | Learns execution for validated strategies |
| **Portfolio Agent** | Allocates capital across validated strategies |
| **Backtest Agent** | Shared vectorbt infrastructure |
| **Synthesis Agent** | Creates skills from validated strategies |

---

## 11. Next Steps

1. **Build Ingestion Agent** — Fix SSRN TLS, enhance arXiv fetcher
2. **Build Specification Agent** — LLM-based strategy extraction to schema
3. **Build Backtest Agent** — Vectorbt pipeline for 151 categories
4. **Build Improvement/Validation Agents** — Statistical rigor
5. **Build Deployment Agent** — Skill generation + orchestrator integration
6. **Run pilot** — Test on 10 categories (Mean Reversion + Momentum)

---

## 12. Free Resources

| Tool | Purpose |
|------|---------|
| `feedparser` | SSRN RSS |
| `arxiv` / `urllib` | arXiv API |
| `PyMuPDF` | PDF text extraction |
| `vectorbt` | High-speed backtesting |
| `quantstats` | Tearsheets |
| `scipy/statsmodels` | Statistical tests |
| `openrouter/free` | LLM extraction |

---

**Ready to build?** Say "build strategy swarm" and I'll start with Ingestion + Specification agents.