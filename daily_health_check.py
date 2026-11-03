#!/usr/bin/env python3
"""
DAILY SWARM HEALTH CHECK + SYMBOL ROTATION (fixed 2026-11-03)
Runs 2x/day (8am and 8pm). Checks dashboard, ticker, gateway, pipeline.
On failure -> Telegram alert. On success -> rotates 2 FX / 2 index / 2 synthetic
symbols, fetches fresh data, runs backtests, regenerates dashboard, Telegram summary.

Fixes vs previous version:
- Native C:/ paths (old /c/ MSYS paths do not resolve under Windows Python)
- check_gateway reads the real gateway_state.json schema
  (gateway_state + platforms.telegram.state, not a nonexistent top-level "state")
- check_pipeline timeout raised 120s -> 300s (chunked yfinance fetch is slow)
- run_pipeline_for_symbols() implemented (was called but never defined)
- update_dashboard() called with correct signature
- Backtest resolver points at repo-root raw/ where the pipeline actually writes
"""

import sys
import json
import subprocess
from datetime import datetime, date
from pathlib import Path

QUANT_DIR = Path(r"C:/Users/gqama/AppData/Local/hermes/quant_swarm")
BACKTESTS_DIR = QUANT_DIR / "backtests"
RAW_DIR = QUANT_DIR / "raw"
LOG_DIR = QUANT_DIR / "logs"
GATEWAY_STATE_FILE = r"C:/Users/gqama/AppData/Local/hermes/gateway_state.json"
ENV_PATH = Path(r"C:/Users/gqama/AppData/Local/hermes/.env")

PIPELINE_TIMEOUT = 300
DASHBOARD_TIMEOUT = 120


def load_telegram_credentials():
    token = chat_id = None
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip(chr(34))
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip().strip(chr(34))
    return token, chat_id


def send_telegram(token, chat_id, message):
    if not token or not chat_id:
        return False
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        return True
    except Exception:
        return False


def check_dashboard():
    try:
        import requests
        r = requests.get("http://127.0.0.1:9119/cyberpunk_dashboard.html", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def check_ticker():
    try:
        import requests
        r = requests.get("http://127.0.0.1:9118/ticker", timeout=5)
        if r.status_code != 200:
            return False
        data = r.json()
        return bool(data.get("symbols"))
    except Exception:
        return False


def check_gateway():
    """Validate the real gateway_state.json schema."""
    try:
        state = json.loads(Path(GATEWAY_STATE_FILE).read_text(encoding="utf-8"))
        if str(state.get("gateway_state", "")).lower() not in ("running", "connected"):
            return False
        tg = state.get("platforms", {}).get("telegram", {})
        if tg and str(tg.get("state", "")).lower() != "connected":
            return False
        return True
    except Exception:
        return False


def check_pipeline():
    try:
        result = subprocess.run(
            [sys.executable, str(QUANT_DIR / "data" / "pipeline_finmlkit.py")],
            capture_output=True, timeout=PIPELINE_TIMEOUT, cwd=str(QUANT_DIR),
        )
        return result.returncode == 0
    except Exception:
        return False


def rotate_symbols():
    FX_POOL = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X",
               "USDCHF=X", "USDSEK=X", "USDNOK=X", "GBPJPY=X", "EURJPY=X", "AUDJPY=X"]
    INDEX_POOL = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^FTSE", "^GDAXI", "^N225", "^HSI"]
    SYNTH_POOL = ["GLD", "SLV", "USO", "TLT", "XLF", "XLE", "XLV", "XLI", "XLK", "XLU",
                  "XLB", "XLRE", "XLY", "XLP"]

    state_file = QUANT_DIR / "rotation_state.json"
    state = {"last_date": None, "fx_idx": 0, "idx_idx": 0, "synth_idx": 0, "symbols": []}
    if state_file.exists():
        try:
            state.update(json.loads(state_file.read_text()))
        except Exception:
            pass

    today = date.today().isoformat()
    if state.get("last_date") == today and state.get("symbols"):
        return state["symbols"]

    fx_i, ix_i, sy_i = state.get("fx_idx", 0), state.get("idx_idx", 0), state.get("synth_idx", 0)
    symbols = (
        [FX_POOL[fx_i % len(FX_POOL)], FX_POOL[(fx_i + 1) % len(FX_POOL)]]
        + [INDEX_POOL[ix_i % len(INDEX_POOL)], INDEX_POOL[(ix_i + 1) % len(INDEX_POOL)]]
        + [SYNTH_POOL[sy_i % len(SYNTH_POOL)], SYNTH_POOL[(sy_i + 1) % len(SYNTH_POOL)]]
    )
    state.update({
        "last_date": today,
        "fx_idx": (fx_i + 2) % len(FX_POOL),
        "idx_idx": (ix_i + 2) % len(INDEX_POOL),
        "synth_idx": (sy_i + 2) % len(SYNTH_POOL),
        "symbols": symbols,
    })
    state_file.write_text(json.dumps(state, indent=2))
    return symbols


def run_pipeline_for_symbols(symbols, period="7d"):
    """Fetch fresh data + build features for the rotated symbols via the pipeline module."""
    sys.path.insert(0, str(QUANT_DIR))
    from data.pipeline_finmlkit import run_enhanced_pipeline
    feature_files, _ = run_enhanced_pipeline(symbols=symbols, interval="1m", period=period)
    return feature_files


def run_backtest_for_symbols(symbols):
    try:
        sys.path.insert(0, str(BACKTESTS_DIR))
        from strategy_library import run_all, summarize

        class QuantResolver:
            def __init__(self, syms):
                self.symbols = syms

            def __call__(self, sym):
                safe = sym.replace("=", "").replace("/", "_")
                p = RAW_DIR / f"{safe}_1m.csv"
                return p if p.exists() else None

        results = run_all(QuantResolver(symbols))
        return {"summary": summarize(results), "success": True}
    except Exception as e:
        return {"error": str(e)[:300], "success": False}


def update_dashboard():
    try:
        result = subprocess.run(
            [sys.executable, str(BACKTESTS_DIR / "generate_dashboard.py")],
            capture_output=True, timeout=DASHBOARD_TIMEOUT, cwd=str(BACKTESTS_DIR),
        )
        return result.returncode == 0
    except Exception:
        return False


def log_line(msg):
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    with open(LOG_DIR / f"health_check_{stamp}.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")


def main():
    print(f"=== Quant Swarm Health Check & Rotation - {datetime.now().isoformat()} ===")
    token, chat_id = load_telegram_credentials()
    if not token or not chat_id:
        print("Missing Telegram credentials in .env")
        log_line("FAIL: missing telegram credentials")
        return False

    checks = {
        "Dashboard": check_dashboard(),
        "Ticker": check_ticker(),
        "Gateway": check_gateway(),
        "Pipeline": check_pipeline(),
    }
    print("Checks:", json.dumps(checks))
    failed = [name for name, ok in checks.items() if not ok]

    if failed:
        msg = "QUANT SWARM HEALTH CHECK FAILED:\n" + "\n".join(f"- {n}" for n in failed)
        msg += "\nCheck logs and restart services if needed."
        send_telegram(token, chat_id, msg)
        print(f"ALERT sent: {msg}")
        log_line(f"FAIL: {failed}")
        return False

    print("All checks passed. Rotating symbols...")
    symbols = rotate_symbols()
    print(f"Symbols: {symbols}")

    print("Running pipeline for symbols (7d refresh)...")
    try:
        feature_files = run_pipeline_for_symbols(symbols)
        n_ok = len(feature_files)
    except Exception as e:
        n_ok = 0
        print(f"Pipeline warning: {e}")

    print("Running backtests...")
    backtest = run_backtest_for_symbols(symbols)

    print("Updating dashboard...")
    if update_dashboard():
        msg = f"Quant Swarm OK at {datetime.now().strftime(chr(37)+'Y-'+chr(37)+'m-'+chr(37)+'d '+chr(37)+'H:'+chr(37)+'M')}\n"
        msg += f"Symbols: {', '.join(symbols)}\n"
        msg += f"Pipeline: {n_ok}/{len(symbols)} symbols processed\n"
        msg += f"Backtest: {backtest.get('error', 'OK')}"
        send_telegram(token, chat_id, msg)
        print("SUCCESS: dashboard updated, Telegram notified")
        log_line(f"OK: {symbols}, pipeline {n_ok}/{len(symbols)}")
        return True

    msg = "Dashboard update failed. Check logs."
    send_telegram(token, chat_id, msg)
    print(f"FAILED: {msg}")
    log_line("FAIL: dashboard update")
    return False


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
