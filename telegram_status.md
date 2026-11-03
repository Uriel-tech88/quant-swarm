# Quant Swarm Report — 2026-11-03 07:23 SAST

## ✅ DATA (0.0s)
- reused local feature store (--skip-data)
## ✅ BACKTEST (5.5s)
- EURUSD=X: PnL -0.21% | Sharpe -2.09 | MaxDD -0.60% | 12 trades
- GBPUSD=X: PnL -0.44% | Sharpe -3.95 | MaxDD -0.84% | 16 trades
- USDJPY=X: PnL -4.18% | Sharpe -14.84 | MaxDD -4.24% | 57 trades
- AUDUSD=X: PnL +0.16% | Sharpe 1.26 | MaxDD -0.63% | 7 trades
- GC=F: PnL -1.71% | Sharpe -7.65 | MaxDD -2.01% | 13 trades
- ^GSPC: PnL -2.31% | Sharpe -11.52 | MaxDD -2.58% | 8 trades
- ^DJI: PnL -1.46% | Sharpe -12.42 | MaxDD -1.72% | 7 trades
- ^IXIC: PnL -7.80% | Sharpe -7.95 | MaxDD -7.80% | 32 trades
- GLD: PnL -4.94% | Sharpe -11.03 | MaxDD -4.96% | 9 trades
- SLV: PnL -11.65% | Sharpe -11.04 | MaxDD -11.65% | 9 trades
- USO: PnL +1.07% | Sharpe 1.55 | MaxDD -3.65% | 13 trades
- TLT: PnL +1.28% | Sharpe 1.43 | MaxDD -1.84% | 38 trades
- 🏆 best Sharpe: USO (1.55)
## ✅ STRATEGIES (46.2s)
- 9 SSRN-derived strategies benchmarked:
  - atr_trailing_stop: mean Sharpe -0.60 | best +4.34 | totPnL +2.47% (5 symbols)
  - macd_trend: mean Sharpe -0.97 | best +1.14 | totPnL -1.44% (5 symbols)
  - momentum_sma20: mean Sharpe -2.18 | best +1.55 | totPnL -1.12% (5 symbols)
  - keltner_squeeze: mean Sharpe -3.75 | best -1.20 | totPnL -3.13% (5 symbols)
  - rsi2_reversal: mean Sharpe -4.25 | best +9.19 | totPnL -0.40% (5 symbols)
  - ema_crossover: mean Sharpe -4.57 | best -1.67 | totPnL -6.95% (5 symbols)
  - donchian_breakout: mean Sharpe -5.90 | best -0.22 | totPnL -9.78% (5 symbols)
  - vol_target_momentum: mean Sharpe -8.60 | best -4.72 | totPnL -9.33% (5 symbols)
  - bollinger_zscore: mean Sharpe -10.19 | best +3.76 | totPnL -1.97% (5 symbols)
## ✅ RL (0.0s)
- torch not installed — RL stage skipped (checkpoint preserved)
## ✅ PORTFOLIO (4.8s)
- HRP over 12 assets | eff.N 2.74 | ann.vol 0.49%
  - USO: 45.2%
  - GBPUSDX: 39.4%
  - GSPC: 5.2%
  - AUDUSDX: 4.8%
  - DJI: 2.7%