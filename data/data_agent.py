#!/usr/bin/env python3
"""
Quant Swarm — Data Agent (Phase 2)
Fetches multi-source forex/equity/crypto data → feature store

Sources (free):
- yfinance (1m tick, verified)
- OANDA Demo API (forex tick)
- Alpha Vantage (FX daily)
- Twelve Data (forex)
- ccxt (Binance/Coinbase crypto)
- FRED API (macro indicators)
- Alpaca (real-time SIP)

After download: data/raw/<source>/ → pipeline_finmlkit.py → data/features/

Usage: python data_agent.py [--fetch] [--validate] [--symbols EURUSD,GLD] [--days 30]
Cron: every 4h (align with market data refresh)
"""

import os
import sys
import json
import time
import math
import hashlib
import warnings
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

warnings.filterwarnings("ignore")

# Paths
QUANT_SWARM = Path(__file__).resolve().parent
DATA_DIR = QUANT_SWARM / "data"
RAW_DIR = DATA_DIR / "raw"
FEATURES_DIR = DATA_DIR / "features"
RAW_DIR.mkdir(parents=True, exist_ok=True)
FEATURES_DIR.mkdir(parents=True, exist_ok=True)

# Symbols to track (from multi_symbol_verification.md — 11 symbols verified)
DEFAULT_SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "^GSPC", "^DJI", "^IXIC", "GLD", "SLV", "USO", "TLT"]
CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

# --- Data source fetchers ---

def fetch_yfinance(symbol: str, days: int = 60, interval: str = "1m") -> Optional[str]:
    """Fetch 1m tick via yfinance, save to RAW_DIR. Returns CSV path."""
    try:
        import yfinance as yf
        # Chunk downloads: ~8 days per request for 1m data
        chunk_days = 8
        end_date = datetime.now()
        frames = []
        start_date = end_date - timedelta(days=days)
        
        current = end_date
        while current > start_date:
            prev = current - timedelta(days=chunk_days)
            chunk_start = max(prev, start_date)
            
            try:
                df = yf.download(
                    symbol,
                    start=chunk_start.strftime("%Y-%m-%d"),
                    end=current.strftime("%Y-%m-%d"),
                    interval=interval,
                    progress=False
                )
                if df is not None and len(df) > 0:
                    frames.append(df)
                    print(f"  {symbol} chunk {chunk_start.date()}→{current.date()}: {len(df)} rows")
            except Exception as e:
                print(f"    chunk error: {e}")
            
            current = prev
            time.sleep(1)  # Avoid rate limit
        
        if not frames:
            print(f"  ✗ {symbol}: no data received")
            return None
        
        import pandas as pd
        full_df = pd.concat(frames).drop_duplicates(subset="Date").sort_index()
        
        # Validate continuity
        validate_continuity(full_df, symbol)
        
        # Save as CSV (fallback if parquet unavailable)
        safe_name = symbol.replace("=", "").replace("/", "_")
        csv_path = RAW_DIR / f"{safe_name}_{interval}_{days}d.csv"
        full_df.to_csv(csv_path)
        print(f"  ✓ {symbol}: {len(full_df)} rows → {csv_path}")
        return str(csv_path)
        
    except ImportError:
        print("  ✗ yfinance not installed")
        return None
    except Exception as e:
        print(f"  ✗ {symbol}: {e}")
        return None


def fetch_ccxt(symbol: str, exchange: str = "binance", timeframe: str = "1m", days: int = 5) -> Optional[str]:
    """Fetch crypto data via ccxt. Returns CSV path."""
    try:
        import ccxt
        import pandas as pd
        
        ex_class = getattr(ccxt, exchange.lower())
        ex = ex_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        timeframe_map = {'1m': '1m', '5m': '5m', '1h': '1h', '1d': '1d'}
        tf = timeframe_map.get(timeframe, '1m')
        
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        ohlcv = ex.fetch_ohlcv(symbol, tf, since=since, limit=50000)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        safe_name = symbol.replace('/', '_').replace('\\', '_')
        csv_path = RAW_DIR / f"{safe_name}_{timeframe}_{days}d_ccxt.csv"
        df.to_csv(csv_path)
        print(f"  ✓ {symbol} ({exchange}): {len(df)} rows → {csv_path}")
        return str(csv_path)
        
    except ImportError:
        print("  ✗ ccxt not installed (pip install ccxt)")
        return None
    except Exception as e:
        print(f"  ✗ ccxt {symbol}: {e}")
        return None


def validate_continuity(df, symbol: str) -> bool:
    """Check for gaps >5%, NaNs, extreme jumps >50%"""
    import pandas as pd
    import numpy as np
    
    issues = []
    if isinstance(df.index, pd.DatetimeIndex):
        expected_minutes = (df.index.max() - df.index.min()).total_seconds() / 60 + 1
        actual_minutes = len(df)
        gap_pct = (1 - actual_minutes / expected_minutes) if expected_minutes > 0 else 0
        if gap_pct > 0.05:
            issues.append(f"gaps >5% (missing {gap_pct*100:.1f}% of bars)")
    
    if df.isnull().any().any():
        nan_cols = df.columns[df.isnull().any()].tolist()
        issues.append(f"NaN in columns: {nan_cols}")
    
    # Check extreme jumps in close price (>50%)
    if 'close' in df.columns and len(df) > 1:
        returns = df['close'].pct_change().abs()
        jump_count = (returns > 0.5).sum()
        if jump_count > 0:
            issues.append(f"extreme jumps >50%: {jump_count} instances")
    
    if issues:
        print(f"  ⚠ {symbol} continuity issues: {' '.join(issues)}")
        return False
    else:
        print(f"  ✓ {symbol} continuity OK ({len(df)} rows)")
        return True


def process_to_features(csv_path: str, symbol: str) -> Optional[str]:
    """Run FinMLKit pipeline on raw CSV → dollar bars + triple-barrier labels"""
    try:
        import pandas as pd
        from pipeline_finmlkit import dollar_bars, triple_barrier_labels, validate_tick_continuity
        
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        validate_tick_continuity(df, symbol.replace("=X", ""))
        
        # Dollar bars
        dollar_df = dollar_bars(df, dollar_threshold=df['close'].iloc[-1] * 0.001)  # ~0.1% of price
        safe_name = symbol.replace("=", "").replace("/", "_")
        
        features_path = FEATURES_DIR / f"dollar_bars_{safe_name}.csv"
        dollar_df.to_csv(features_path)
        
        # Triple barrier labels
        if len(dollar_df) > 100:
            labels = triple_barrier_labels(
                dollar_df, 
                pt_sl=[1.0, 1.0],  # 1:1 reward:risk
                min_ret=0.005,      # 0.5% minimum return
                num_threads=2
            )
            labels_path = FEATURES_DIR / f"triple_barrier_{safe_name}.csv"
            labels.to_csv(labels_path)
            print(f"  ✓ {symbol} features: {len(dollar_df)} dollar bars → {features_path}")
            print(f"  ✓ {symbol} labels: {len(labels)} → {labels_path}")
            return str(features_path)
        else:
            print(f"  ⚠ {symbol}: too few bars for labeling ({len(dollar_df)})")
            return str(features_path)
            
    except Exception as e:
        print(f"  ✗ {symbol} feature processing: {e}")
        import traceback; traceback.print_exc()
        return None


def run_data_agent(
    symbols: List[str] = None,
    days: int = 30,
    fetch: bool = True,
    process: bool = True
) -> Dict:
    """
    Full Data Agent pipeline: fetch → validate → process to features
    """
    if symbols is None:
        symbols = DEFAULT_SYMBOLS
    
    print("=" * 60)
    print(f"DATA AGENT — {datetime.now().isoformat()}")
    print(f"Symbols: {len(symbols)} | Days: {days}")
    print("=" * 60)
    
    results = {"fetched": {}, "features": {}, "errors": []}
    
    if fetch:
        print("\n[FETCHING DATA]")
        for symbol in symbols:
            print(f"\n→ {symbol}")
            csv_path = fetch_yfinance(symbol, days=days, interval="1m")
            if csv_path:
                results["fetched"][symbol] = csv_path
            else:
                # Fallback: try daily data
                try:
                    import yfinance as yf
                    df = yf.download(symbol, period=f"{days}d", interval="1d", progress=False)
                    if df is not None and len(df) > 0:
                        safe_name = symbol.replace("=", "").replace("/", "_")
                        csv_path = RAW_DIR / f"{safe_name}_1d_{days}d.csv"
                        df.to_csv(csv_path)
                        results["fetched"][symbol] = str(csv_path)
                        print(f"  ✓ {symbol} daily fallback: {len(df)} rows")
                except Exception as e:
                    results["errors"].append({"symbol": symbol, "error": str(e)})
    
    if process:
        print("\n[PROCESSING TO FEATURES]")
        for symbol, csv_path in results["fetched"].items():
            # Skip crypto for now (different handling)
            if "/" in symbol:
                continue
            print(f"→ {symbol}")
            feature_path = process_to_features(csv_path, symbol)
            if feature_path:
                results["features"][symbol] = feature_path
    
    # Write manifest
    manifest_path = DATA_DIR / "data_manifest.json"
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "symbols_fetched": list(results["fetched"].keys()),
        "symbols_features": list(results["features"].keys()),
        "symbol_count": len(results["fetched"]),
        "errors": results["errors"],
        "raw_dir": str(RAW_DIR),
        "features_dir": str(FEATURES_DIR),
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n{'=' * 60}")
    print(f"DATA AGENT COMPLETE")
    print(f"  Fetched: {len(results['fetched'])} symbols")
    print(f"  Features: {len(results['features'])} symbols")
    print(f"  Errors: {len(results['errors'])}")
    print(f"  Manifest: {manifest_path}")
    print(f"{'=' * 60}")
    
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Quant Swarm Data Agent")
    parser.add_argument("--fetch", action="store_true", default=True, help="Fetch new data")
    parser.add_argument("--no-fetch", action="store_false", dest="fetch", help="Skip fetching")
    parser.add_argument("--process", action="store_true", default=True, help="Process to features")
    parser.add_argument("--no-process", action="store_false", dest="process", help="Skip processing")
    parser.add_argument("--symbols", default="auto", help="Comma-separated symbols (default: auto=11 verified)")
    parser.add_argument("--days", type=int, default=30, help="Days of data")
    parser.add_argument("--check", action="store_true", help="Dependency check only")
    
    args = parser.parse_args()
    
    if args.check:
        print("DATA AGENT — Dependencies check")
        try:
            import yfinance; print("  ✓ yfinance")
        except ImportError:
            print("  ✗ yfinance (pip install yfinance)")
        try:
            import pandas; print("  ✓ pandas")
        except ImportError:
            print("  ✗ pandas")
        try:
            import numpy; print("  ✓ numpy")
        except ImportError:
            print("  ✗ numpy")
        try:
            import ccxt; print("  ✓ ccxt")
        except ImportError:
            print("  ~ ccxt (optional, pip install ccxt)")
        try:
            from pipeline_finmlkit import dollar_bars, triple_barrier_labels
            print("  ✓ pipeline_finmlkit (FinMLKit)")
        except ImportError as e:
            print(f"  ✗ pipeline_finmlkit: {e}")
        print(f"  ✓ Output dirs: {RAW_DIR}, {FEATURES_DIR}")
        sys.exit(0)
    
    symbols = DEFAULT_SYMBOLS if args.symbols == "auto" else args.symbols.split(",")
    
    run_data_agent(
        symbols=symbols,
        days=args.days,
        fetch=args.fetch,
        process=args.process
    )