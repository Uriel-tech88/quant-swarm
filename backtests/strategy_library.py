#!/usr/bin/env python3
"""
STRATEGY LIBRARY — SSRN-derived strategies for the quant swarm.
Gap-closer: moves the swarm from 1 backtested SSRN strategy to 8.

Source paper: "151 Trading Strategies" (Kakushadze & Serur, 2018), SSRN 3247865.
Each strategy has a schema-conforming YAML spec in research/strategies/.

All strategies run on hourly bars resampled from the local 1m feature store,
with 5bps cost per position change. Pairs strategies use the log-spread z-score.
"""
import numpy as np
import pandas as pd

COST_BPS = 5e-4
ANN_FACTOR = np.sqrt(24 * 252)  # hourly bars


# ---------- indicators ----------
def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def load_hourly_close(csv_path) -> pd.Series:
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    return df["Close"].astype(float).resample("1h").last().ffill().dropna()


def load_hourly_ohlc(csv_path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    out = pd.DataFrame(index=df.index)
    out["Close"] = df["Close"].astype(float)
    for col in ("High", "Low"):
        out[col] = df[col].astype(float) if col in df.columns else out["Close"]
    return out.resample("1h").last().ffill().dropna()


# ---------- signal generators: close/ohlc -> position in {-1,0,1} or float ----------
def sig_momentum_sma20(ohlc):
    close = ohlc["Close"]
    sma = close.rolling(20).mean()
    return (close > sma).astype(float).shift(1).fillna(0.0)


def sig_bollinger_zscore(ohlc):
    """Mean reversion: short upper band, long lower band (SSRN §4 mean-reversion family)."""
    close = ohlc["Close"]
    mid = close.rolling(20).mean()
    sd = close.rolling(20).std()
    z = (close - mid) / sd.replace(0, np.nan)
    pos = pd.Series(0.0, index=close.index)
    pos[z < -2] = 1.0    # long when cheap
    pos[z > 2] = -1.0    # short when rich
    pos[(z > -0.5) & (z < 0.5)] = 0.0  # flat near fair value
    return pos.shift(1).fillna(0.0)


def sig_rsi2_reversal(ohlc):
    """RSI(2) reversal (SSRN short-horizon mean-reversion): long <10, exit >50."""
    close = ohlc["Close"]
    r = rsi(close, 2)
    pos = pd.Series(np.nan, index=close.index)
    pos[r < 10] = 1.0
    pos[r > 50] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_macd_trend(ohlc):
    """MACD(12,26,9) trend-following (SSRN §3.1 momentum family)."""
    close = ohlc["Close"]
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    return np.sign(macd - signal).shift(1).fillna(0.0)


def sig_donchian_breakout(ohlc, window=20):
    """Donchian channel breakout (SSRN trend-following / turtle-style)."""
    hi = ohlc["High"].rolling(window).max().shift(1)
    lo = ohlc["Low"].rolling(window).min().shift(1)
    close = ohlc["Close"]
    pos = pd.Series(np.nan, index=close.index)
    pos[close > hi] = 1.0
    pos[close < lo] = -1.0
    mid = (hi + lo) / 2
    pos[(close - mid).abs() < (hi - lo) * 0.1] = 0.0  # exit near mid
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_vol_target_momentum(ohlc, target_vol=0.10):
    """Momentum with inverse-vol sizing (SSRN volatility-targeting overlay)."""
    close = ohlc["Close"]
    sma = close.rolling(20).mean()
    direction = (close > sma).astype(float) * 2 - 1  # +1 / -1
    realized = close.pct_change().rolling(48).std() * ANN_FACTOR
    scale = (target_vol / realized.replace(0, np.nan)).clip(upper=3.0).fillna(0.0)
    return (direction * scale).shift(1).fillna(0.0)


SINGLE_STRATEGIES = {
    "momentum_sma20": sig_momentum_sma20,
    "bollinger_zscore": sig_bollinger_zscore,
    "rsi2_reversal": sig_rsi2_reversal,
    "macd_trend": sig_macd_trend,
    "donchian_breakout": sig_donchian_breakout,
    "vol_target_momentum": sig_vol_target_momentum,
}

PAIR_STRATEGIES = {
    "pairs_gld_slv": ("GLD", "SLV"),        # gold vs silver cointegration proxy
    "pairs_tlt_ixic": ("TLT", "^IXIC"),     # bonds vs tech mean reversion
}


def _metrics(net: pd.Series, pos: pd.Series) -> dict:
    cum = (1 + net).cumprod()
    sharpe = float(net.mean() / net.std() * ANN_FACTOR) if net.std() > 0 else 0.0
    return {
        "pnl": float(cum.iloc[-1] - 1) if len(cum) else 0.0,
        "sharpe": round(sharpe, 2),
        "max_drawdown": float((cum / cum.cummax() - 1).min()) if len(cum) else 0.0,
        "n_trades": int(pos.diff().abs().gt(1e-9).sum()),
        "bars": len(net),
    }


def backtest_single(ohlc: pd.DataFrame, sig_fn) -> dict:
    close = ohlc["Close"]
    pos = sig_fn(ohlc)
    rets = close.pct_change().fillna(0.0) * pos
    costs = pos.diff().abs().fillna(0.0) * COST_BPS
    return _metrics(rets - costs, pos)


def backtest_pair(csv_a, csv_b) -> dict:
    """Log-spread z-score mean reversion on a pair (SSRN stat-arb family)."""
    a, b = load_hourly_close(csv_a), load_hourly_close(csv_b)
    df = pd.concat([a, b], axis=1, keys=["a", "b"]).ffill().dropna()
    if len(df) < 60:
        return {"error": f"too few overlapping bars ({len(df)})"}
    spread = np.log(df["a"]) - np.log(df["b"])
    z = (spread - spread.rolling(48).mean()) / spread.rolling(48).std().replace(0, np.nan)
    pos = pd.Series(0.0, index=df.index)   # +1 = long spread (long A short B)
    pos[z < -1.5] = 1.0
    pos[z > 1.5] = -1.0
    pos[z.abs() < 0.25] = 0.0
    pos = pos.shift(1).fillna(0.0)
    spread_ret = spread.diff().fillna(0.0)
    costs = pos.diff().abs().fillna(0.0) * COST_BPS * 2  # two legs
    return _metrics(spread_ret * pos - costs, pos)


def run_all(csv_resolver) -> dict:
    """Run every strategy. csv_resolver(sym) -> Path or None (handles GC=F etc.)."""
    out = {"single": {}, "pairs": {}}
    symbols = [s for s in csv_resolver.symbols if csv_resolver(s) is not None]
    for name, fn in SINGLE_STRATEGIES.items():
        out["single"][name] = {}
        for sym in symbols:
            try:
                ohlc = load_hourly_ohlc(csv_resolver(sym))
                out["single"][name][sym] = backtest_single(ohlc, fn)
            except Exception as e:
                out["single"][name][sym] = {"error": str(e)[:100]}
    for name, (sa, sb) in PAIR_STRATEGIES.items():
        ca, cb = csv_resolver(sa), csv_resolver(sb)
        try:
            out["pairs"][name] = backtest_pair(ca, cb) if ca and cb else {"error": "missing csv"}
        except Exception as e:
            out["pairs"][name] = {"error": str(e)[:100]}
    return out


def summarize(results: dict) -> dict:
    """Per-strategy aggregate across symbols + leaderboard."""
    agg = {}
    for name, per_sym in results["single"].items():
        sharpes = [r["sharpe"] for r in per_sym.values() if "sharpe" in r]
        pnls = [r["pnl"] for r in per_sym.values() if "pnl" in r]
        if sharpes:
            agg[name] = {
                "n_symbols": len(sharpes),
                "mean_sharpe": round(float(np.mean(sharpes)), 2),
                "best_sharpe": round(float(np.max(sharpes)), 2),
                "total_pnl": round(float(np.sum(pnls)) * 100, 2),
            }
    for name, r in results["pairs"].items():
        if "sharpe" in r:
            agg[name] = {"n_symbols": 1, "mean_sharpe": r["sharpe"],
                         "best_sharpe": r["sharpe"], "total_pnl": round(r["pnl"] * 100, 2)}
    leaderboard = sorted(agg.items(), key=lambda kv: -kv[1]["mean_sharpe"])
    return {"per_strategy": agg, "leaderboard": leaderboard}
