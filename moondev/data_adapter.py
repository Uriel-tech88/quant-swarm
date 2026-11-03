"""
Data adapter: feeds the quant swarm's existing feature store to the
MoonDev-style agent. Zero new data downloads — reuses features/*.csv
produced by pipeline_finmlkit.py (12 symbols already on disk).

Applies the repo's tz-parsing lesson: yfinance CSVs carry tz-aware /
mixed-offset timestamps, so always parse with
pd.to_datetime(idx, format='mixed', utc=True).
"""

import glob
from pathlib import Path

import pandas as pd

FEATURES_DIR = Path(__file__).resolve().parents[1] / "features"


def available_symbols():
    keys = []
    for p in sorted(glob.glob(str(FEATURES_DIR / "features_*.csv"))):
        keys.append(Path(p).stem.replace("features_", ""))
    return keys


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-12)
    return 100 - 100 / (1 + rs)


def load_bars(symbol_key):
    path = FEATURES_DIR / f"features_{symbol_key}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Available: {', '.join(available_symbols())}"
        )
    df = pd.read_csv(path)
    df["Datetime"] = pd.to_datetime(df["Datetime"], format="mixed", utc=True)
    df = df.sort_values("Datetime").reset_index(drop=True)
    return df


def build_market_data(symbol_key, n_bars=60):
    """Compact text block for the trading prompt: price vs MAs, RSI,
    recent returns, volume pattern, last 10 bars."""
    df = load_bars(symbol_key).tail(n_bars).copy()
    close = df["Close"]

    ma20 = close.rolling(20).mean().iloc[-1]
    ma40 = close.rolling(40).mean().iloc[-1]
    rsi = _rsi(close).iloc[-1]
    last = close.iloc[-1]

    def ret(n):
        if len(close) > n and close.iloc[-n - 1]:
            return (close.iloc[-1] / close.iloc[-n - 1] - 1) * 100
        return float("nan")

    vol_txt = "volume unavailable for this symbol"
    if "Volume" in df and df["Volume"].sum() > 0:
        v_recent = df["Volume"].tail(10).mean()
        v_prior = df["Volume"].tail(40).head(30).mean()
        trend = "rising" if v_recent > v_prior * 1.05 else (
            "falling" if v_recent < v_prior * 0.95 else "flat")
        vol_txt = (f"avg volume last 10 bars {v_recent:.0f} vs prior 30 "
                   f"{v_prior:.0f} ({trend})")

    bars = df.tail(10)[["Datetime", "Open", "High", "Low", "Close"]]
    bars_txt = "\n".join(
        f"  {r.Datetime:%Y-%m-%d %H:%M}  O={r.Open:.5f} H={r.High:.5f} "
        f"L={r.Low:.5f} C={r.Close:.5f}"
        for r in bars.itertuples()
    )

    return f"""Symbol: {symbol_key}  (bars: {len(df)}, source: quant-swarm feature store)
Last close: {last:.5f}
MA20: {ma20:.5f}  (price {'ABOVE' if last > ma20 else 'BELOW'} MA20)
MA40: {ma40:.5f}  (price {'ABOVE' if last > ma40 else 'BELOW'} MA40)
MA20 vs MA40: {'BULLISH (MA20 > MA40)' if ma20 > ma40 else 'BEARISH (MA20 < MA40)'}
RSI(14): {rsi:.1f}
Returns: last 5 bars {ret(5):+.3f}%  |  10 bars {ret(10):+.3f}%  |  20 bars {ret(20):+.3f}%
Volume: {vol_txt}
Last 10 bars (UTC):
{bars_txt}"""
