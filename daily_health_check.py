#!/usr/bin/env python3
"""
DAILY SWARM HEALTH CHECK + SYMBOL ROTATION
Runs 2x/day (8am and 8pm). Checks dashboard, ticker, gateway, pipeline.
If anything breaks -> Telegram alert. If OK -> rotates 2 FX / 2 index / 2 synthetic symbols,
fetches tick data, runs backtest, updates dashboard.
"""

import os
import sys
import json
import subprocess
import requests
import time
import datetime
from datetime import datetime, date
from pathlib import Path

# Paths
QUANT_DIR = Path("/c/Users/gqama/AppData/Local/hermes/quant_swarm")
BACKTESTS_DIR = QUANT_DIR / "backtests"
DATA_DIR = QUANT_DIR / "data"
FEATURES_DIR = DATA_DIR / "features"
RAW_DIR = DATA_DIR / "raw"
LOG_DIR = QUANT_DIR / "logs"
DASHBOARD_PATH = BACKTESTS_DIR / "cyberpunk_dashboard.html"
GATEWAY_STATE_FILE = "/c/Users/gqama/AppData/Local/hermes/gateway_state.json"
ENV_PATH = Path("/c/Users/gqama/AppData/Local/hermes/.env")

# Telegram credentials from .env
def load_telegram_credentials():
    token = None
    chat_id = None
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                if "TELEGRAM_BOT_TOKEN" in line:
                    token = line.split("=")[1].strip().strip('"')
                if "TELEGRAM_CHAT_ID" in line:
                    chat_id = line.split("=")[1].strip().strip('"')
    return token, chat_id

def send_telegram_alert(token, chat_id, message):
    """Send Telegram message."""
    if not token or not chat_id:
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        requests.post(url, json=payload, timeout=10)
        return True
    except Exception:
        return False

def check_dashboard():
    """Check if dashboard server is responding."""
    try:
        import requests
        resp = requests.get("http://127.0.0.1:9119/cyberpunk_dashboard.html", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def check_ticker():
    """Check if ticker server is responding."""
    try:
        import requests
        resp = requests.get("http://127.0.0.1:9118/", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def check_gateway():
    """Check gateway state."""
    try:
        with open(GATEWAY_STATE_FILE) as f:
            state = json.load(f)
        return state.get("state", "").lower() == "connected"
    except Exception:
        return False

def check_pipeline():
    """Check if pipeline script runs without error."""
    try:
        result = subprocess.run(
            [sys.executable, str(DATA_DIR / "pipeline_finmlkit.py")],
            capture_output=True, timeout=120, cwd=str(QUANT_DIR)
        )
        return result.returncode == 0
    except Exception:
        return False

def rotate_symbols():
    """Rotate symbols for the day (2 FX, 2 index, 2 synthetic)."""
    # Define symbol pools
    FX_POOL = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "USDSEK=X", "USDNOK=X", "GBPJPY=X", "EURJPY=X", "AUDJPY=X"]
    INDEX_POOL = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^FTSE", "^GDAXI", "^N225", "^HSI"]
    SYNTH_POOL = ["GLD", "SLV", "USO", "TLT", "XLF", "XLE", "XLV", "XLI", "XLK", "XLU", "XLB", "XLRE", "XLY", "XLP"]
    
    # Load rotation state
    state_file = QUANT_DIR / "rotation_state.json"
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
    else:
        state = {"last_date": None, "fx_idx": 0, "idx_idx": 0, "synth_idx": 0, "symbols": []}
    
    today = date.today().isoformat()
    
    # If same day, return existing symbols
    if state.get("last_date") == today:
        return state["symbols"]
    
    # Rotate symbols
    fx_idx = state.get("fx_idx", 0)
    idx_idx = state.get("idx_idx", 0)
    synth_idx = state.get("synth_idx", 0)
    
    fx_symbols = [FX_POOL[fx_idx % len(FX_POOL)], FX_POOL[(fx_idx + 1) % len(FX_POOL)]]
    idx_symbols = [INDEX_POOL[idx_idx % len(INDEX_POOL)], INDEX_POOL[(idx_idx + 1) % len(INDEX_POOL)]]
    synth_symbols = [SYNTH_POOL[synth_idx % len(SYNTH_POOL)], SYNTH_POOL[(synth_idx + 1) % len(SYNTH_POOL)]]
    
    symbols = fx_symbols + idx_symbols + synth_symbols
    
    # Update state
    state["last_date"] = today
    state["fx_idx"] = (fx_idx + 2) % len(FX_POOL)
    state["idx_idx"] = (idx_idx + 2) % len(INDEX_POOL)
    state["synth_idx"] = (synth_idx + 2) % len(SYNTH_POOL)
    state["symbols"] = symbols
    
    # Save state
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)
    
    return symbols

def run_backtest_for_symbols(symbols):
    """Run backtest for the given symbols."""
    try:
        import sys
        sys.path.insert(0, str(BACKTESTS_DIR))
        from strategy_library import run_all, summarize
        
        # Create a custom resolver that points to the data directory
        class QuantResolver:
            def __init__(self):
                self.symbols = symbols
                
            def __call__(self, sym):
                # Map symbol to file path
                safe_sym = sym.replace("=", "").replace("/", "_")
                file_path = BACKTESTS_DIR / f"{safe_sym}_1m.csv"
                return file_path if file_path.exists() else None
        
        # Create resolver instance
        resolver = QuantResolver()
        results = run_all(resolver)
        summary = summarize(results)
        return {"summary": summary, "success": True}
    
    except Exception as e:
        return {"error": str(e)[:200], "success": False}

def update_dashboard():
    """Regenerate the dashboard HTML."""
    try:
        result = subprocess.run(
            [sys.executable, str(BACKTESTS_DIR / "generate_dashboard.py")],
            capture_output=True, timeout=60, cwd=str(BACKTESTS_DIR)
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    print(f"=== Quant Swarm Health Check & Rotation - {datetime.now().isoformat()} ===")
    
    # Load Telegram credentials
    token, chat_id = load_telegram_credentials()
    if not token or not chat_id:
        print("❌ Missing Telegram credentials")
        return False
    
    # Run health checks
    checks = {
        "Dashboard": check_dashboard(),
        "Ticker": check_ticker(),
        "Gateway": check_gateway(),
        "Pipeline": check_pipeline(),
    }
    
    failed = [name for name, ok in checks.items() if not ok]
    
    if failed:
        # Send Telegram alert for failures
        msg = "❌ QUANT SWARM HEALTH CHECK FAILED:\n"
        for name in failed:
            msg += f"- {name}\n"
        msg += "Check logs and restart services if needed."
        send_telegram_alert(token, chat_id, msg)
        print(f"❌ ALERT sent: {msg}")
        return False
    
    # All checks passed - rotate symbols
    print("All checks passed. Rotating symbols...")
    symbols = rotate_symbols()
    print(f"Rotated symbols: {symbols}")
    
    # Run pipeline for new symbols
    print("Running pipeline for new symbols...")
    feature_files, reports = run_pipeline_for_symbols(symbols)
    
    # Run backtest for new symbols
    print("Running backtest for new symbols...")
    backtest_result = run_backtest_for_symbols(symbols)
    
    # Update dashboard
    print("Updating dashboard...")
    if update_dashboard(symbols, backtest_result):
        # Send success message
        msg = f"✅ Quant Swarm OK at {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"New symbols: {', '.join(symbols)}\n"
        msg += f"Pipeline: {len(feature_files) if feature_files else 0} symbols processed\n"
        msg += f"Backtest: {backtest_result.get('error', 'OK')}"
        send_telegram_alert(token, chat_id, msg)
        print("✅ SUCCESS: Dashboard updated and Telegram notified")
        return True
    else:
        msg = "❌ Dashboard update failed. Check logs."
        send_telegram_alert(token, chat_id, msg)
        print(f"❌ FAILED: {msg}")
        return False

if __name__ == "__main__":
    main()