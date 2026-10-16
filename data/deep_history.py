#!/usr/bin/env python3
"""
DEEP HISTORY — extend the swarm's data beyond the 7-day window (all free, yfinance).

Per symbol (12):
  - 30 days of 1m bars  (chunked 7-day requests; Yahoo hard-limits 1m to ~30d back)
  - 730 days of 1h bars (single request; Yahoo allows 2y for 1h)
Saved to raw/deep/ as CSV. Strategies can backtest on 1h/2y immediately;
1m/30d quadruples the high-resolution window vs the old 7d.

For tick data older than 30 days (free, manual download):
  - HistData.com      — FX 1-min/tick, years of history
  - Dukascopy         — FX tick data via dukascopy-node (npm), back to 2003
  - Kaggle datasets   — see skills/quant-data-sources SKILL.md

Usage: python data/deep_history.py [--symbols EURUSD=X ...]
"""
import sys, time, argparse
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "deep"
OUT.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    "GC=F", "^GSPC", "^DJI", "^IXIC",
    "GLD", "SLV", "USO", "TLT",
]


def safe_name(sym: str) -> str:
    return sym.replace("=", "").replace("^", "").replace("/", "_")


def chunked_1m(sym: str, days: int = 30, chunk: int = 7) -> pd.DataFrame:
    """1m bars are limited to ~30d lookback and ~8d per request — chunk it."""
    frames = []
    end = pd.Timestamp.now(tz="UTC")
    start_total = end - pd.Timedelta(days=days)
    cur_end = end
    while cur_end > start_total:
        cur_start = max(cur_end - pd.Timedelta(days=chunk), start_total)
        try:
            df = yf.download(sym, start=cur_start.strftime("%Y-%m-%d"),
                             end=cur_end.strftime("%Y-%m-%d"), interval="1m",
                             progress=False, auto_adjust=False)
            if df is not None and len(df):
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                frames.append(df)
        except Exception as e:
            print(f"  ⚠ {sym} 1m chunk {cur_start.date()}→{cur_end.date()}: {str(e)[:60]}")
        cur_end = cur_start
        time.sleep(1.0)  # be polite to Yahoo
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    return out[~out.index.duplicated(keep="first")]


def fetch_simple(sym: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(sym, period=period, interval=interval, progress=False, auto_adjust=False)
    if df is not None and len(df) and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df if df is not None else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    args = ap.parse_args()

    summary = []
    for sym in args.symbols:
        name = safe_name(sym)
        row = {"symbol": sym}

        df1m = chunked_1m(sym, days=30)
        if len(df1m):
            df1m.to_csv(OUT / f"{name}_1m_30d.csv")
            row["1m_rows"] = len(df1m)
            row["1m_from"] = str(df1m.index.min().date())
        else:
            row["1m_rows"] = 0

        df1h = fetch_simple(sym, "1h", "730d")
        if len(df1h):
            df1h.to_csv(OUT / f"{name}_1h_730d.csv")
            row["1h_rows"] = len(df1h)
            row["1h_from"] = str(df1h.index.min().date())
        else:
            row["1h_rows"] = 0

        df1d = fetch_simple(sym, "1d", "max")
        if len(df1d):
            df1d.to_csv(OUT / f"{name}_1d_max.csv")
            row["1d_rows"] = len(df1d)
            row["1d_from"] = str(df1d.index.min().date())
        else:
            row["1d_rows"] = 0

        summary.append(row)
        print(f"✓ {sym}: 1m={row.get('1m_rows',0)} (from {row.get('1m_from','-')}), "
              f"1h={row.get('1h_rows',0)} (from {row.get('1h_from','-')}), "
              f"1d={row.get('1d_rows',0)} (from {row.get('1d_from','-')})", flush=True)

    pd.DataFrame(summary).to_csv(OUT / "_deep_history_summary.csv", index=False)
    print(f"\n✓ Deep history saved to {OUT}")
    print(f"  Summary: {OUT / '_deep_history_summary.csv'}")


if __name__ == "__main__":
    main()
