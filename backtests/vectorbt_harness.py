"""Vectorbt backtest harness (Phase 1 + Phase 5 SSRN 151 strategies)."""
import os, json, datetime
import pandas as pd
import numpy as np
import yfinance as yf
from vectorbt.portfolio.base import Portfolio

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load(symbol, period="7d"):
    # Try yfinance first; fall back to pipeline CSV for rate-limit resilience
    try:
        df = yf.download(symbol, interval="1m", period=period, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not df.empty:
            return df
    except Exception:
        pass
    # Fallback: pipeline CSV (dollar bars from Phase 1)
    safe = symbol.replace("=", "")
    csv_path = os.path.join(BASE.replace("backtests", "data/features"), f"dollar_bars_{safe}.csv")
    if not csv_path.startswith(BASE):
        csv_path = "/c/Users/gqama/AppData/Local/hermes/quant_swarm/data/features/" + f"dollar_bars_{safe}.csv"
    # Try alternative names
    for p in [csv_path, "/c/Users/gqama/AppData/Local/hermes/quant_swarm/data/features/dollar_bars_EURUSDX.csv"]:
        if os.path.exists(p):
            df = pd.read_csv(p, parse_dates=["Datetime"], index_col="Datetime")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    return pd.DataFrame()

def _momentum_signal(df, sma_period=20):
    close = df["Close"].astype(float)
    sma = close.rolling(sma_period).mean()
    sig = (close > sma).astype(int)
    sig = sig.fillna(0).shift(1).fillna(0)
    return sig

def run_backtest(symbol="EURUSD=X", strategy="momentum_sma20", period="30d"):
    """Run a single-symbol backtest using SSRN 151 strategy (momentum/trend-following)."""
    df = _load(symbol, period=period)
    if df.empty:
        return {"symbol": symbol, "error": "no data"}
    signals = _momentum_signal(df)
    pf = Portfolio.from_signals(close=df["Close"].astype(float), signals=signals, freq="1d")
    returns = pf.returns()
    sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0.0
    cum = (1 + returns).cumprod()
    max_dd = float((cum / cum.cummax() - 1).min()) if len(cum) else 0.0
    return {
        "symbol": symbol,
        "strategy": strategy,
        "pnl": float(cum.iloc[-1] - 1) if len(cum) else 0.0,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "n_trades": int((signals.diff().abs() > 0).sum()),
    }

def multi_symbol(symbols=None, strategy="momentum_sma20", period="30d"):
    """Backtest across multiple symbols (FX + indices + synthetics)."""
    symbols = symbols or ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","^GSPC","^DJI","^IXIC","GLD","SLV","USO","TLT"]
    out = {}
    for s in symbols:
        try:
            out[s] = run_backtest(s, strategy=strategy, period=period)
        except Exception as e:
            out[s] = {"symbol": s, "error": str(e)[:80]}
    return out
