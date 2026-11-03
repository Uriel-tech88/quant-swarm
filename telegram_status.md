# Quant Swarm Report — 2026-11-03 07:57 SAST

## ✅ DATA (0.0s)
- reused local feature store (--skip-data)
## ✅ BACKTEST (5.6s)
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
## ✅ STRATEGIES (40.4s)
- 22 SSRN-derived strategies benchmarked:
  - kalman_gld_slv: mean Sharpe +10.23 | best +10.23 | totPnL +3.44% (1 symbols)
  - pairs_gld_slv: mean Sharpe +6.67 | best +6.67 | totPnL +1.34% (1 symbols)
  - xsec_lowvol_bab: mean Sharpe +1.90 | best +1.90 | totPnL +0.79% (12 symbols)
  - rsi14_classic: mean Sharpe -0.80 | best +3.14 | totPnL -2.57% (12 symbols)
  - xsec_momentum_top3bot3: mean Sharpe -0.95 | best -0.95 | totPnL -1.28% (12 symbols)
  - ou_ar1_residual: mean Sharpe -1.66 | best +0.00 | totPnL -8.96% (12 symbols)
  - macd_trend: mean Sharpe -2.34 | best +2.39 | totPnL -20.01% (12 symbols)
  - keltner_squeeze: mean Sharpe -2.55 | best +3.54 | totPnL -3.95% (12 symbols)
  - atr_trailing_stop: mean Sharpe -3.01 | best +4.34 | totPnL -16.71% (12 symbols)
  - williams_r_reversal: mean Sharpe -3.49 | best +7.02 | totPnL -4.90% (12 symbols)
  - breakout_vol_filter: mean Sharpe -3.50 | best +4.05 | totPnL -9.54% (12 symbols)
  - cci_breakout: mean Sharpe -3.64 | best +4.70 | totPnL -9.89% (12 symbols)
  - rsi2_reversal: mean Sharpe -3.76 | best +9.19 | totPnL -5.58% (12 symbols)
  - ema_crossover: mean Sharpe -4.15 | best +0.16 | totPnL -23.44% (12 symbols)
  - short_term_reversal: mean Sharpe -4.68 | best +7.19 | totPnL -21.43% (12 symbols)
  - donchian_breakout: mean Sharpe -4.76 | best +6.25 | totPnL -19.66% (12 symbols)
  - momentum_sma20: mean Sharpe -6.52 | best +1.55 | totPnL -32.19% (12 symbols)
  - tsmom_vol_scaled: mean Sharpe -6.74 | best +0.59 | totPnL -31.18% (12 symbols)
  - bollinger_zscore: mean Sharpe -7.45 | best +3.76 | totPnL -11.80% (12 symbols)
  - pairs_tlt_ixic: mean Sharpe -7.74 | best -7.74 | totPnL -5.88% (1 symbols)
  - vol_target_momentum: mean Sharpe -8.01 | best -2.48 | totPnL -41.17% (12 symbols)
  - stochastic_cross: mean Sharpe -14.41 | best -3.65 | totPnL -53.92% (12 symbols)
## ✅ RL (0.0s)
- torch not installed — RL stage skipped (checkpoint preserved)
## ✅ PORTFOLIO (5.4s)
- HRP over 12 assets | eff.N 2.74 | ann.vol 0.49%
  - USO: 45.2%
  - GBPUSDX: 39.4%
  - GSPC: 5.2%
  - AUDUSDX: 4.8%
  - DJI: 2.7%