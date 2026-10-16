#!/usr/bin/env python3
"""
TICK FETCHER — institutional-grade historical tick data, 100% free, no API keys.

Sources:
  1. DUKASCOPY (Swiss forex bank — the feed hedge funds use for FX backtests)
     Real bid/ask tick stream with volumes, hourly LZMA-compressed bi5 files,
     history back to 2003. Symbols: EURUSD, GBPUSD, USDJPY, AUDUSD, XAUUSD (gold spot!),
     plus CFDs for indices/commodities (USA500.IDX = S&P500 etc.)
  2. BINANCE public data archives (data.binance.vision)
     Every single aggregated trade (price, qty, ms timestamp) for 350+ pairs,
     daily/monthly zips back to 2017.

Output: raw/ticks/{symbol}/{date}.csv  (one row per tick)

Usage:
  python data/tick_fetcher.py --duka EURUSD --days 7
  python data/tick_fetcher.py --duka EURUSD XAUUSD USDJPY --days 3
  python data/tick_fetcher.py --binance BTCUSDT ETHUSDT --days 7
  python data/tick_fetcher.py --duka EURUSD --start 2026-09-01 --end 2026-09-07
"""
import sys, io, time, lzma, struct, zipfile, argparse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "ticks"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# Dukascopy point-value scale per symbol (price = raw_int / scale)
DUKA_SCALE = {
    "EURUSD": 1e5, "GBPUSD": 1e5, "AUDUSD": 1e5, "EURGBP": 1e5,
    "USDJPY": 1e3, "AUDJPY": 1e3, "EURJPY": 1e3, "GBPJPY": 1e3,
    "XAUUSD": 1e2, "XAGUSD": 1e3,
    "USA500.IDX": 1e1, "USATECH100.IDX": 1e1, "USA30.IDX": 1e1,
    "BRENT.CMD": 1e2, "WTI.CMD": 1e2,
}


def http_get(url: str, referer: str = "https://www.dukascopy.com/", timeout=15, retries=3) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": referer,
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def decode_bi5(data: bytes, hour_start: datetime, scale: float) -> pd.DataFrame:
    """Decode one Dukascopy hourly bi5 file -> DataFrame of ticks."""
    if not data or len(data) < 10:
        return pd.DataFrame()
    raw = lzma.decompress(data, format=lzma.FORMAT_AUTO)
    n = len(raw) // 20
    if n == 0:
        return pd.DataFrame()
    rows = []
    base_ms = int(hour_start.timestamp() * 1000)
    for i in range(n):
        ms, ask, bid, avol, bvol = struct.unpack_from(">IIIff", raw, i * 20)
        rows.append((base_ms + ms, bid / scale, ask / scale, bvol, avol))
    df = pd.DataFrame(rows, columns=["ts_ms", "bid", "ask", "bid_vol", "ask_vol"])
    df["datetime"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    df["mid"] = (df["bid"] + df["ask"]) / 2
    return df


def fetch_dukascopy(symbol: str, start: datetime, end: datetime) -> int:
    scale = DUKA_SCALE.get(symbol.upper(), 1e5)
    outdir = OUT / symbol.upper()
    outdir.mkdir(parents=True, exist_ok=True)
    total = 0
    day = start
    while day <= end:
        dayfile = outdir / f"{day.strftime('%Y-%m-%d')}.csv"
        frames = []
        # Dukascopy month in URL is 0-indexed (Jan=00)!
        for hour in range(24):
            url = (f"https://datafeed.dukascopy.com/datafeed/{symbol.upper()}/"
                   f"{day.year}/{day.month - 1:02d}/{day.day:02d}/{hour:02d}h_ticks.bi5")
            try:
                data = http_get(url)
                df = decode_bi5(data, datetime(day.year, day.month, day.day, hour), scale)
                if len(df):
                    frames.append(df)
            except Exception as e:
                msg = str(e)[:60]
                if "404" not in msg and "403" not in msg:
                    print(f"  ⚠ {symbol} {day.date()} {hour:02d}h: {msg}")
            time.sleep(0.15)  # stay under rate limits
        if frames:
            dfd = pd.concat(frames, ignore_index=True)
            dfd.to_csv(dayfile, index=False)
            total += len(dfd)
            print(f"  ✓ {symbol} {day.date()}: {len(dfd):,} ticks -> {dayfile.name}", flush=True)
        else:
            print(f"  - {symbol} {day.date()}: no ticks (weekend/holiday?)", flush=True)
        day += timedelta(days=1)
    return total


def fetch_binance(symbols, start, end) -> int:
    total = 0
    for sym in symbols:
        outdir = OUT / sym.upper()
        outdir.mkdir(parents=True, exist_ok=True)
        day = start
        while day <= end:
            name = f"{sym.upper()}-aggTrades-{day.strftime('%Y-%m-%d')}"
            url = f"https://data.binance.vision/data/spot/daily/aggTrades/{sym.upper()}/{name}.zip"
            try:
                data = http_get(url, referer="https://data.binance.vision/")
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    with z.open(name + ".csv") as f:
                        df = pd.read_csv(f, header=None,
                                         names=["agg_id", "price", "qty", "first_id", "last_id",
                                                "ts_ms", "is_buyer_maker", "is_best_match"])
                df["datetime"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
                out = outdir / f"{day.strftime('%Y-%m-%d')}.csv"
                df[["ts_ms", "datetime", "price", "qty", "is_buyer_maker"]].to_csv(out, index=False)
                total += len(df)
                print(f"  ✓ {sym} {day.date()}: {len(df):,} trades -> {out.name}", flush=True)
            except Exception as e:
                print(f"  ⚠ {sym} {day.date()}: {str(e)[:80]}", flush=True)
            day += timedelta(days=1)
            time.sleep(0.3)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duka", nargs="*", default=[])
    ap.add_argument("--binance", nargs="*", default=[])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    args = ap.parse_args()

    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = datetime.strptime(args.end or args.start, "%Y-%m-%d")
    else:
        end = datetime.utcnow() - timedelta(days=1)  # today is incomplete
        start = end - timedelta(days=args.days - 1)

    grand = 0
    for sym in args.duka:
        print(f"=== DUKASCOPY {sym.upper()} ticks {start.date()}..{end.date()} ===", flush=True)
        grand += fetch_dukascopy(sym, start, end)
    if args.binance:
        print(f"=== BINANCE aggTrades {start.date()}..{end.date()} ===", flush=True)
        grand += fetch_binance(args.binance, start, end)
    print(f"\n✓ TICK FETCH COMPLETE: {grand:,} ticks saved under {OUT}")


if __name__ == "__main__":
    main()
