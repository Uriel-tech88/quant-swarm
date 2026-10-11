#!/usr/bin/env python3
"""
Local Quant Swarm Continuous Runner - Private, no cloud dependencies.
Runs the multi-symbol pipeline every 5 minutes locally.
"""
import sys, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def run_pipeline():
    from quant_swarm.data.pipeline_finmlkit import run_enhanced_pipeline, validate_tick_continuity
    import pandas as pd

    multi = [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
        "^GSPC", "^DJI", "^IXIC",
        "GLD", "SLV", "USO", "TLT"
    ]

    print(f"[{time.ctime()}] Running multi-symbol pipeline: {len(multi)} symbols")
    features, data = run_enhanced_pipeline(symbols=multi, interval="1m", period="7d")

    for sym in multi:
        safe_name = sym.replace("=", "").replace("/", "_")
        csv_path = Path("data/features/dollar_bars_" + safe_name + ".csv")
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
            validate_tick_continuity(df, sym)

    print(f"[{time.ctime()}] Pipeline complete.")

if __name__ == "__main__":
    print("=== Quant Swarm Local Continuous Runner (Private) ===")
    print("Press Ctrl+C to stop")
    while True:
        try:
            run_pipeline()
            time.sleep(300)  # 5 minutes
        except KeyboardInterrupt:
            print("\nStopped by user")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)
