@echo off
REM Local Quant Swarm Runner - Private, no GitHub, no cloud
REM Runs every 5 minutes via Windows Task Scheduler or manual loop

cd /d "C:\Users\gqama\AppData\Local\hermes\quant_swarm"

echo [%date% %time%] Starting Quant Swarm multi-symbol pipeline...

python - << 'EOF'
import sys
sys.path.insert(0, '.')
from quant_swarm.data.pipeline_finmlkit import run_enhanced_pipeline, validate_tick_continuity
import pandas as pd

multi = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    "^GSPC", "^DJI", "^IXIC",
    "GLD", "SLV", "USO", "TLT"
]

print(f"Running multi-symbol pipeline: {len(multi)} symbols")
features, data = run_enhanced_pipeline(symbols=multi, interval="1m", period="7d")

# Validate data quality (Free Data Trap)
from pathlib import Path
for sym in multi:
    safe_name = sym.replace("=", "").replace("/", "_")
    csv_path = Path("data/features/dollar_bars_" + safe_name + ".csv")
    if csv_path.exists():
        df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
        validate_tick_continuity(df, sym)

print("Pipeline complete. Feature files in data/features/")
EOF

echo [%date% %time%] Pipeline complete. Logs in logs/
