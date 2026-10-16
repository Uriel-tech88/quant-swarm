#!/usr/bin/env python3
"""
LIVE TICK FEED — real-time streaming ticks, 100% free, no API keys.

Source: Binance public WebSocket (wss://stream.binance.com:9443)
  Every live trade for any pair — millisecond timestamps, price, quantity.
  This is TRUE tick data, streaming in real time.

Writes:
  raw/live/{SYMBOL}_{YYYYMMDD}.csv   — append-only tick log (ts_ms, datetime, price, qty, side)
  raw/live/latest.json               — last price per symbol (for the ticker dashboard)

Usage:
  python ticker/live_feed.py                          # BTCUSDT + ETHUSDT, run forever
  python ticker/live_feed.py --symbols btcusdt xrpusdt --duration 60
  python ticker/live_feed.py --duration 0             # 0 = run forever (daemon)

Stop with Ctrl+C. Designed to run in its own terminal window:
  start "Live Ticks" cmd /k "python C:/Users/gqama/AppData/Local/hermes/quant_swarm/ticker/live_feed.py"
"""
import asyncio, json, argparse, time, sys
from datetime import datetime, timezone
from pathlib import Path

import websockets
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "raw" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
WS_URL = "wss://stream.binance.com:9443/stream"


def csv_path(symbol: str) -> Path:
    return LIVE / f"{symbol.upper()}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"


def append_tick(symbol: str, ts_ms: int, price: float, qty: float, is_buyer_maker: bool):
    p = csv_path(symbol)
    new = not p.exists()
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("ts_ms,datetime,price,qty,side\n")
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
        f.write(f"{ts_ms},{dt},{price},{qty},{'sell' if is_buyer_maker else 'buy'}\n")


async def stream(symbols, duration_s: int, stats_every: int = 30):
    streams = "/".join(f"{s.lower()}@trade" for s in symbols)
    url = f"{WS_URL}?streams={streams}"
    counts = {s.upper(): 0 for s in symbols}
    latest = {}
    t_start = time.time()
    t_last_stats = t_start

    while True:  # auto-reconnect forever
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                print(f"● LIVE: connected to Binance stream: {', '.join(symbols)}", flush=True)
                async for msg in ws:
                    evt = json.loads(msg)
                    d = evt.get("data", {})
                    sym = d.get("s", "").upper()
                    if not sym:
                        continue
                    ts = int(d["T"]); price = float(d["p"]); qty = float(d["q"])
                    append_tick(sym, ts, price, qty, bool(d.get("m")))
                    counts[sym] = counts.get(sym, 0) + 1
                    latest[sym] = {"price": price, "ts": ts,
                                   "dt": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()}
                    (LIVE / "latest.json").write_text(
                        json.dumps({"updated": datetime.now(timezone.utc).isoformat(),
                                    "ticks_total": sum(counts.values()), "symbols": latest}, indent=2))
                    now = time.time()
                    if now - t_last_stats >= stats_every:
                        el = now - t_start
                        rate = sum(counts.values()) / el if el else 0
                        print(f"  [{datetime.now().strftime('%H:%M:%S')}] "
                              + " | ".join(f"{s}: {latest[s]['price']:.2f}" for s in latest)
                              + f"  ({sum(counts.values()):,} ticks, {rate:.0f}/s)", flush=True)
                        t_last_stats = now
                    if duration_s and (now - t_start) >= duration_s:
                        print(f"\n✓ Duration reached. Total ticks captured: {sum(counts.values()):,}")
                        for s, c in counts.items():
                            print(f"  {s}: {c:,} ticks -> {csv_path(s).name}")
                        return
        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
            print(f"  ↻ connection lost ({str(e)[:50]}), reconnecting in 3s...", flush=True)
            await asyncio.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=["BTCUSDT", "ETHUSDT"])
    ap.add_argument("--duration", type=int, default=0, help="seconds (0 = forever)")
    args = ap.parse_args()
    try:
        asyncio.run(stream(args.symbols, args.duration))
    except KeyboardInterrupt:
        print("\n■ Live feed stopped by user.")


if __name__ == "__main__":
    main()
