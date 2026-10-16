# Quant Swarm Report — 2026-10-16 22:50 SAST

## ✅ DATA (0.0s)
- reused local feature store (--skip-data)
## ✅ BACKTEST (3.0s)
- EURUSD=X: PnL +0.12% | Sharpe 1.47 | MaxDD -0.55% | 11 trades
- GBPUSD=X: PnL +0.25% | Sharpe 2.48 | MaxDD -0.62% | 5 trades
- USDJPY=X: PnL -1.34% | Sharpe -18.42 | MaxDD -1.34% | 15 trades
- AUDUSD=X: PnL +0.25% | Sharpe 2.50 | MaxDD -0.62% | 4 trades
- GC=F: PnL -1.76% | Sharpe -9.39 | MaxDD -2.08% | 12 trades
- ^GSPC: PnL -1.46% | Sharpe -12.71 | MaxDD -1.61% | 8 trades
- ^DJI: PnL +0.58% | Sharpe 4.00 | MaxDD -0.69% | 6 trades
- ^IXIC: PnL -3.43% | Sharpe -15.64 | MaxDD -3.43% | 8 trades
- GLD: PnL -0.57% | Sharpe -1.79 | MaxDD -2.09% | 6 trades
- SLV: PnL -2.20% | Sharpe -2.99 | MaxDD -4.92% | 4 trades
- USO: PnL +5.18% | Sharpe 15.45 | MaxDD -0.64% | 5 trades
- TLT: PnL +1.65% | Sharpe 6.12 | MaxDD -1.08% | 6 trades
- 🏆 best Sharpe: USO (15.45)
## ✅ STRATEGIES (11.2s)
- 12 SSRN-derived strategies benchmarked:
  - xsec_momentum_top3bot3: mean Sharpe +0.99 | best +0.99 | totPnL +0.18% (12 symbols)
  - donchian_breakout: mean Sharpe -0.20 | best +13.09 | totPnL +4.65% (12 symbols)
  - vol_target_momentum: mean Sharpe -0.69 | best +9.19 | totPnL -2.89% (12 symbols)
  - keltner_squeeze: mean Sharpe -1.06 | best +9.36 | totPnL +7.12% (12 symbols)
  - atr_trailing_stop: mean Sharpe -1.87 | best +14.41 | totPnL -2.57% (12 symbols)
  - ema_crossover: mean Sharpe -1.96 | best +12.62 | totPnL +5.40% (12 symbols)
  - momentum_sma20: mean Sharpe -2.41 | best +15.45 | totPnL -2.73% (12 symbols)
  - macd_trend: mean Sharpe -3.91 | best +6.31 | totPnL -11.73% (12 symbols)
  - rsi2_reversal: mean Sharpe -5.24 | best +8.99 | totPnL -8.88% (12 symbols)
  - pairs_tlt_ixic: mean Sharpe -7.39 | best -7.39 | totPnL -1.80% (1 symbols)
  - bollinger_zscore: mean Sharpe -9.54 | best +4.63 | totPnL -13.07% (12 symbols)
  - pairs_gld_slv: mean Sharpe -17.65 | best -17.65 | totPnL -1.89% (1 symbols)
## ✅ RL (0.0s)
- torch not installed — RL stage skipped (checkpoint preserved)
## ✅ PORTFOLIO (2.5s)
- HRP over 12 assets | eff.N 8.05 | ann.vol 1.08%
  - GBPUSDX: 21.3%
  - IXIC: 15.0%
  - USDJPYX: 14.7%
  - TLT: 9.8%
  - EURUSDX: 8.1%