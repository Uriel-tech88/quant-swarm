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


def _read_csv_dated(csv_path) -> pd.DataFrame:
    """Read a pipeline CSV with a guaranteed UTC DatetimeIndex.

    parse_dates=True silently keeps a string Index on the tz-aware and
    mixed-offset timestamps yfinance writes, and every .resample() downstream
    then fails with 'Only valid with DatetimeIndex'. That knocked 7 of 12
    symbols out of the strategy stage.
    """
    df = pd.read_csv(csv_path, index_col=0)
    try:
        df.index = pd.to_datetime(df.index, format="mixed", utc=True)
    except (TypeError, ValueError):
        df.index = pd.to_datetime(df.index, utc=True)
    return df


def load_hourly_close(csv_path) -> pd.Series:
    df = _read_csv_dated(csv_path)
    return df["Close"].astype(float).resample("1h").last().ffill().dropna()


def load_hourly_ohlc(csv_path) -> pd.DataFrame:
    df = _read_csv_dated(csv_path)
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


def atr(ohlc: pd.DataFrame, period: int = 14) -> pd.Series:
    hi, lo, cl = ohlc["High"], ohlc["Low"], ohlc["Close"]
    tr = pd.concat([hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def sig_ema_crossover(ohlc, fast=9, slow=21):
    """EMA fast/slow crossover trend-following (SSRN §3.1 moving-average family)."""
    close = ohlc["Close"]
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    return np.sign(ema_f - ema_s).shift(1).fillna(0.0)


def sig_keltner_squeeze(ohlc, ema_period=20, atr_period=14, mult=2.0):
    """Keltner channel breakout (SSRN §3.2 channel-breakout family)."""
    close = ohlc["Close"]
    mid = close.ewm(span=ema_period, adjust=False).mean()
    a = atr(ohlc, atr_period)
    upper, lower = mid + mult * a, mid - mult * a
    pos = pd.Series(np.nan, index=close.index)
    pos[close > upper] = 1.0
    pos[close < lower] = -1.0
    pos[(close < mid) & (close > mid - mult * a * 0.25)] = 0.0  # exit on reversion to mid
    pos[(close > mid) & (close < mid + mult * a * 0.25)] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_atr_trailing_stop(ohlc, atr_period=14, mult=3.0):
    """Long-on-strength with chandelier ATR trailing stop (SSRN risk-overlay family)."""
    close = ohlc["Close"].values
    a = atr(ohlc, atr_period).values
    sma = ohlc["Close"].rolling(20).mean().values
    pos = np.zeros(len(close))
    in_pos = False
    stop = 0.0
    for i in range(1, len(close)):
        if np.isnan(a[i]) or np.isnan(sma[i]):
            pos[i] = 1.0 if in_pos else 0.0
            continue
        if not in_pos and close[i] > sma[i]:
            in_pos, stop = True, close[i] - mult * a[i]
        elif in_pos:
            stop = max(stop, close[i] - mult * a[i])
            if close[i] < stop:
                in_pos = False
        pos[i] = 1.0 if in_pos else 0.0
    return pd.Series(pos, index=ohlc.index).shift(1).fillna(0.0)


# ---------- batch 2: classic quant + SSRN-cited strategies ----------
def sig_tsmom_vol_scaled(ohlc, lookback=72, target_vol=0.10):
    """Time-series momentum (Moskowitz, Ooi & Pedersen 2012, JFE):
    sign of the past `lookback`-hour return, sized by target/realized vol."""
    close = ohlc["Close"]
    direction = np.sign(close.pct_change(lookback))
    realized = close.pct_change().rolling(48).std() * ANN_FACTOR
    scale = (target_vol / realized.replace(0, np.nan)).clip(upper=3.0).fillna(0.0)
    return (direction * scale).shift(1).fillna(0.0)


def sig_short_term_reversal(ohlc, lookback=24):
    """Short-term reversal (Jegadeesh 1990; Lehmann 1990): fade the past day's move."""
    close = ohlc["Close"]
    return (-np.sign(close.pct_change(lookback))).shift(1).fillna(0.0)


def sig_rsi14_classic(ohlc):
    """Wilder RSI(14): long <30, short >70, flat mid-band (classic oscillator MR)."""
    close = ohlc["Close"]
    r = rsi(close, 14)
    pos = pd.Series(np.nan, index=close.index)
    pos[r < 30] = 1.0
    pos[r > 70] = -1.0
    pos[(r > 45) & (r < 55)] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_stochastic_cross(ohlc, k=14, d=3):
    """Stochastic %K/%D crossover (Lane): trade the oscillator cross direction."""
    hi = ohlc["High"].rolling(k).max()
    lo = ohlc["Low"].rolling(k).min()
    pct_k = (ohlc["Close"] - lo) / (hi - lo).replace(0, np.nan) * 100
    pct_d = pct_k.rolling(d).mean()
    return np.sign(pct_k - pct_d).shift(1).fillna(0.0)


def sig_williams_r(ohlc, period=14):
    """Williams %R reversal: long oversold (<-80), short overbought (>-20)."""
    hi = ohlc["High"].rolling(period).max()
    lo = ohlc["Low"].rolling(period).min()
    wr = (hi - ohlc["Close"]) / (hi - lo).replace(0, np.nan) * -100
    pos = pd.Series(np.nan, index=wr.index)
    pos[wr < -80] = 1.0
    pos[wr > -20] = -1.0
    pos[(wr < -45) & (wr > -55)] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_cci_breakout(ohlc, period=20):
    """CCI(20) breakout (Lambert): trend on +/-100 extremes, flat in the chop zone."""
    tp = (ohlc["High"] + ohlc["Low"] + ohlc["Close"]) / 3
    sma = tp.rolling(period).mean()
    mad = (tp - sma).abs().rolling(period).mean()
    cci = (tp - sma) / (0.015 * mad.replace(0, np.nan))
    pos = pd.Series(np.nan, index=cci.index)
    pos[cci > 100] = 1.0
    pos[cci < -100] = -1.0
    pos[cci.abs() < 25] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_ou_ar1_residual(ohlc, window=60, z_in=1.25, z_out=0.25):
    """OU/AR(1) residual mean reversion (SSRN mean-reversion family):
    rolling OLS of log-price on its lag; trade the residual z-score.
    window/z_in sized for the 7d hourly horizon (168 bars)."""
    x0 = np.log(ohlc["Close"])
    x1 = x0.shift(1)
    mx0 = x0.rolling(window).mean()
    mx1 = x1.rolling(window).mean()
    cov = ((x0 - mx0) * (x1 - mx1)).rolling(window).mean()
    var = ((x1 - mx1) ** 2).rolling(window).mean()
    beta = cov / var.replace(0, np.nan)
    alpha = mx0 - beta * mx1
    resid = x0 - (alpha + beta * x1)
    z = resid / resid.rolling(window).std().replace(0, np.nan)
    pos = pd.Series(np.nan, index=x0.index)
    pos[z < -z_in] = 1.0
    pos[z > z_in] = -1.0
    pos[z.abs() < z_out] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


def sig_breakout_vol_filter(ohlc, window=20):
    """Donchian breakout with ATR-expansion filter (SSRN vol-breakout family):
    only enter when volatility is expanding vs its own baseline."""
    hi = ohlc["High"].rolling(window).max().shift(1)
    lo = ohlc["Low"].rolling(window).min().shift(1)
    a = atr(ohlc, 14)
    expanding = a > a.rolling(50).mean()
    close = ohlc["Close"]
    pos = pd.Series(np.nan, index=close.index)
    pos[(close > hi) & expanding] = 1.0
    pos[(close < lo) & expanding] = -1.0
    mid = (hi + lo) / 2
    pos[(close - mid).abs() < (hi - lo) * 0.1] = 0.0
    return pos.ffill().fillna(0.0).shift(1).fillna(0.0)


SINGLE_STRATEGIES = {
    "momentum_sma20": sig_momentum_sma20,
    "bollinger_zscore": sig_bollinger_zscore,
    "rsi2_reversal": sig_rsi2_reversal,
    "macd_trend": sig_macd_trend,
    "donchian_breakout": sig_donchian_breakout,
    "vol_target_momentum": sig_vol_target_momentum,
    "ema_crossover": sig_ema_crossover,
    "keltner_squeeze": sig_keltner_squeeze,
    "atr_trailing_stop": sig_atr_trailing_stop,
    # batch 2: classic quant + SSRN-cited
    "tsmom_vol_scaled": sig_tsmom_vol_scaled,
    "short_term_reversal": sig_short_term_reversal,
    "rsi14_classic": sig_rsi14_classic,
    "stochastic_cross": sig_stochastic_cross,
    "williams_r_reversal": sig_williams_r,
    "cci_breakout": sig_cci_breakout,
    "ou_ar1_residual": sig_ou_ar1_residual,
    "breakout_vol_filter": sig_breakout_vol_filter,
}

PAIR_STRATEGIES = {
    "pairs_gld_slv": ("GLD", "SLV"),        # gold vs silver cointegration proxy
    "pairs_tlt_ixic": ("TLT", "^IXIC"),     # bonds vs tech mean reversion
    "kalman_gld_slv": ("GLD", "SLV"),       # Kalman-filter dynamic hedge ratio
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


def backtest_kalman_pair(csv_a, csv_b, delta=1e-4, R=1e-3) -> dict:
    """Kalman-filter dynamic hedge-ratio stat-arb (SSRN Kalman/stat-arb family).
    Estimates beta_t of log(A) on log(B) online, trades the residual spread z-score."""
    a, b = load_hourly_close(csv_a), load_hourly_close(csv_b)
    df = pd.concat([np.log(a), np.log(b)], axis=1, keys=["y", "x"]).ffill().dropna()
    if len(df) < 120:
        return {"error": f"too few overlapping bars ({len(df)})"}
    y = df["y"].values
    x = df["x"].values
    beta, P = 0.0, 1.0
    betas = np.zeros(len(y))
    for t in range(len(y)):
        P = P + delta
        K = P * x[t] / (x[t] * x[t] * P + R)
        beta = beta + K * (y[t] - beta * x[t])
        P = (1 - K * x[t]) * P
        betas[t] = beta
    beta_s = pd.Series(betas, index=df.index)
    spread = df["y"] - beta_s * df["x"]
    z = (spread - spread.rolling(48).mean()) / spread.rolling(48).std().replace(0, np.nan)
    pos = pd.Series(0.0, index=df.index)
    pos[z < -1.5] = 1.0
    pos[z > 1.5] = -1.0
    pos[z.abs() < 0.25] = 0.0
    pos = pos.shift(1).fillna(0.0)
    spread_ret = spread.diff().fillna(0.0)
    costs = pos.diff().abs().fillna(0.0) * COST_BPS * 2
    return _metrics(spread_ret * pos - costs, pos)


# pairs strategies with their own engine (default: backtest_pair)
PAIR_ENGINES = {
    "kalman_gld_slv": backtest_kalman_pair,
}


def backtest_xsec_momentum(csv_resolver, lookback=48, top_n=3) -> dict:
    """Cross-sectional momentum (SSRN §3.3): hourly, rank all symbols by past
    `lookback`-hour return; long top N, short bottom N, equal-weighted."""
    closes = {}
    for sym in csv_resolver.symbols:
        p = csv_resolver(sym)
        if p is not None:
            try:
                closes[sym] = load_hourly_close(p)
            except Exception:
                pass
    if len(closes) < 2 * top_n + 1:
        return {"error": f"need >= {2*top_n+1} symbols, have {len(closes)}"}
    px = pd.DataFrame(closes).ffill().dropna(how="all")
    fwd = px.pct_change().fillna(0.0)
    mom = px.pct_change(lookback)
    pos = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for ts in mom.dropna(how="all").index:
        row = mom.loc[ts].dropna()
        if len(row) < 2 * top_n:
            continue
        ranked = row.sort_values()
        pos.loc[ts, ranked.index[-top_n:]] = 1.0 / top_n    # long winners
        pos.loc[ts, ranked.index[:top_n]] = -1.0 / top_n    # short losers
    pos = pos.shift(1).fillna(0.0)
    gross = (fwd * pos).sum(axis=1)
    turnover = pos.diff().abs().sum(axis=1).fillna(0.0)
    net = gross - turnover * COST_BPS
    return _metrics(net, pos.sum(axis=1))


def backtest_xsec_lowvol(csv_resolver, lookback=168, n=3) -> dict:
    """Low-volatility anomaly / betting-against-beta style (Frazzini & Pedersen 2014):
    rank the universe by past-week realized vol; long the N quietest, short the N wildest."""
    closes = {}
    for sym in csv_resolver.symbols:
        p = csv_resolver(sym)
        if p is not None:
            try:
                closes[sym] = load_hourly_close(p)
            except Exception:
                pass
    if len(closes) < 2 * n + 1:
        return {"error": f"need >= {2*n+1} symbols, have {len(closes)}"}
    px = pd.DataFrame(closes).ffill().dropna(how="all")
    fwd = px.pct_change().fillna(0.0)
    vol = px.pct_change().rolling(lookback).std()
    pos = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for ts in vol.dropna(how="all").index:
        row = vol.loc[ts].dropna()
        if len(row) < 2 * n:
            continue
        ranked = row.sort_values()
        pos.loc[ts, ranked.index[:n]] = 1.0 / n    # long low-vol
        pos.loc[ts, ranked.index[-n:]] = -1.0 / n  # short high-vol
    pos = pos.shift(1).fillna(0.0)
    gross = (fwd * pos).sum(axis=1)
    turnover = pos.diff().abs().sum(axis=1).fillna(0.0)
    net = gross - turnover * COST_BPS
    return _metrics(net, pos.sum(axis=1))


XSEC_STRATEGIES = {
    "xsec_momentum_top3bot3": backtest_xsec_momentum,
    "xsec_lowvol_bab": backtest_xsec_lowvol,
}


def run_all(csv_resolver) -> dict:
    """Run every strategy. csv_resolver(sym) -> Path or None (handles GC=F etc.)."""
    out = {"single": {}, "pairs": {}, "xsec": {}}
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
        engine = PAIR_ENGINES.get(name, backtest_pair)
        try:
            out["pairs"][name] = engine(ca, cb) if ca and cb else {"error": "missing csv"}
        except Exception as e:
            out["pairs"][name] = {"error": str(e)[:100]}
    for name, fn in XSEC_STRATEGIES.items():
        try:
            out["xsec"][name] = fn(csv_resolver)
        except Exception as e:
            out["xsec"][name] = {"error": str(e)[:150]}
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
    for name, r in results.get("xsec", {}).items():
        if "sharpe" in r:
            agg[name] = {"n_symbols": 12, "mean_sharpe": r["sharpe"],
                         "best_sharpe": r["sharpe"], "total_pnl": round(r["pnl"] * 100, 2)}
    leaderboard = sorted(agg.items(), key=lambda kv: -kv[1]["mean_sharpe"])
    return {"per_strategy": agg, "leaderboard": leaderboard}
