#!/usr/bin/env python3
"""
QUANT SWARM ORCHESTRATOR — one command runs the full 7-agent swarm end-to-end.

Stages:
  1. DATA      — fetch fresh 1m ticks (11 symbols), build dollar bars + features, validate continuity
  2. BACKTEST  — vectorbt momentum backtest across all symbols (PnL, Sharpe, max DD)
  3. RL        — evaluate/train PPO agent (skipped gracefully if torch unavailable)
  4. PORTFOLIO — HRP risk-parity weights from REAL cross-asset returns
  5. SYNTHESIS — combined markdown report -> telegram_briefs/ + telegram_status.md
  6. TELEGRAM  — push summary to your phone via direct Bot API (no gateway needed)

Usage:
  python swarm_run.py            # full run (RL eval only)
  python swarm_run.py --rl-train # include a short PPO training session
  python swarm_run.py --no-telegram  # skip the Telegram push
"""
import sys, os, json, time, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

SYMBOLS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    "^GSPC", "^DJI", "^IXIC",
    "GLD", "SLV", "USO", "TLT",
]

SAST = timezone(timedelta(hours=2))
results = {}   # stage -> payload
timings = {}   # stage -> seconds


def stage(name):
    """Decorator: time + isolate each agent stage so one failure never kills the run."""
    def deco(fn):
        def wrapper(*a, **kw):
            t0 = time.time()
            print(f"\n{'='*60}\n>>> STAGE: {name}\n{'='*60}")
            try:
                out = fn(*a, **kw)
                results[name] = {"status": "ok", "data": out}
            except Exception as e:
                import traceback; traceback.print_exc()
                results[name] = {"status": "error", "error": str(e)[:300]}
            timings[name] = round(time.time() - t0, 1)
            print(f"<<< {name} finished in {timings[name]}s — {results[name]['status']}")
        return wrapper
    return deco


def _csv_for(sym):
    """Resolve the most recent local CSV for a symbol across both feature dirs."""
    dirs = [ROOT / "data" / "features", ROOT / "features"]
    variants = [
        sym.replace("=", "").replace("/", "_"),                    # keeps ^
        sym.replace("=", "").replace("^", "").replace("/", "_"),   # strips ^
    ]
    candidates = []
    for d in dirs:
        for stem in ("features_", "dollar_bars_"):
            for v in variants:
                p = d / f"{stem}{v}.csv"
                if p.exists():
                    candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ---------------- STAGE 1: DATA AGENT ----------------
@stage("data")
def run_data():
    from data.pipeline_finmlkit import run_enhanced_pipeline, validate_tick_continuity
    import pandas as pd
    feature_files, data_dict = run_enhanced_pipeline(symbols=SYMBOLS, interval="1m", period="7d")
    quality = {}
    for sym in SYMBOLS:
        csv = _csv_for(sym)
        if csv:
            df = pd.read_csv(csv, index_col=0, parse_dates=True)
            try:
                rep = validate_tick_continuity(df, sym)
                quality[sym] = {"rows": rep["rows"], "ok": rep["ok"], "file": csv.name}
            except Exception as e:
                quality[sym] = {"warning": str(e)[:120], "file": csv.name}
    return {"symbols_fetched": len(data_dict), "feature_files": len(feature_files), "quality": quality}


# ---------------- STAGE 2: BACKTEST AGENT ----------------
def _pandas_backtest(symbol, sma_period=20):
    """Pure-pandas SMA-momentum backtest on the local dollar-bar CSV (no vectorbt needed)."""
    import pandas as pd, numpy as np
    csv = _csv_for(symbol)
    if not csv:
        return {"symbol": symbol, "error": "no local data"}
    df = pd.read_csv(csv, index_col=0, parse_dates=True)
    close = df["Close"].astype(float).resample("1h").last().ffill().dropna()
    if len(close) < sma_period + 5:
        return {"symbol": symbol, "error": f"too few bars ({len(close)})"}
    sma = close.rolling(sma_period).mean()
    pos = (close > sma).astype(float).shift(1).fillna(0.0)   # long above SMA, flat below
    rets = close.pct_change().fillna(0.0) * pos
    # 5 bps cost per position change
    costs = pos.diff().abs().fillna(0.0) * 5e-4
    net = rets - costs
    cum = (1 + net).cumprod()
    sharpe = float(net.mean() / net.std() * np.sqrt(24 * 252)) if net.std() > 0 else 0.0
    max_dd = float((cum / cum.cummax() - 1).min())
    return {
        "symbol": symbol, "strategy": "momentum_sma20", "engine": "pandas",
        "pnl": float(cum.iloc[-1] - 1), "sharpe": sharpe, "max_drawdown": max_dd,
        "n_trades": int(pos.diff().abs().gt(0).sum()),
    }


@stage("backtest")
def run_backtests():
    try:
        from backtests.vectorbt_harness import multi_symbol
        out = multi_symbol(symbols=SYMBOLS, period="7d")
        if all("error" in r for r in out.values()):
            raise RuntimeError("vectorbt returned errors for all symbols")
        return out
    except Exception:
        print("vectorbt unavailable — using built-in pandas backtest engine")
        return {s: _pandas_backtest(s) for s in SYMBOLS}


# ---------------- STAGE 3: RL AGENT ----------------
@stage("rl")
def run_rl(train=False):
    ckpt = ROOT / "models" / "rl_checkpoints" / "ppo_EURUSDX_final.zip"
    payload = {"checkpoint": str(ckpt) if ckpt.exists() else None}
    try:
        import torch  # noqa
    except ImportError:
        payload["note"] = "torch not installed — RL stage skipped (checkpoint preserved)"
        return payload
    if train:
        from rl_envs.train_ppo import train_ppo
        payload["trained"] = train_ppo(symbol="EURUSD=X", total_timesteps=5000, save_interval=5000)
    else:
        payload["note"] = "eval-only mode (use --rl-train for a training session)"
    return payload


# ---------------- STAGE 4: PORTFOLIO AGENT ----------------
@stage("portfolio")
def run_portfolio():
    import pandas as pd
    from portfolio.hrp_optimizer import run_hrp_optimization
    frames = {}
    for sym in SYMBOLS:
        csv = _csv_for(sym)
        if csv:
            s = pd.read_csv(csv, index_col=0, parse_dates=True)["Close"].astype(float)
            frames[sym.replace("=", "").replace("^", "")] = s.resample("1h").last().ffill().pct_change().dropna()
    if len(frames) < 3:
        raise RuntimeError(f"only {len(frames)} symbols with data — need >=3 for HRP")
    returns = pd.DataFrame(frames).dropna(how="all").fillna(0.0)
    out = run_hrp_optimization(returns=returns.tail(24 * 7))  # last 7 days of hourly returns
    diag = out["diagnostics"]
    return {
        "assets": out["asset_names"],
        "weights": {k: round(float(v), 4) for k, v in zip(out["asset_names"], out["weights"])},
        "effective_assets": round(float(diag["effective_assets"]), 2),
        "annualized_vol": round(float(diag["annualized_volatility"]) * 100, 2),
    }


# ---------------- STAGE 5: SYNTHESIS AGENT ----------------
@stage("synthesis")
def run_synthesis():
    now = datetime.now(SAST).strftime("%Y-%m-%d %H:%M SAST")
    lines = [f"# Quant Swarm Report — {now}", ""]
    for name, res in results.items():
        if name == "synthesis":
            continue
        icon = "✅" if res["status"] == "ok" else "❌"
        lines.append(f"## {icon} {name.upper()} ({timings.get(name, '?')}s)")
        if res["status"] != "ok":
            lines.append(f"- error: {res['error']}")
            continue
        d = res["data"]
        if name == "data":
            if "note" in d:
                lines.append(f"- {d['note']}")
            else:
                lines.append(f"- {d['symbols_fetched']} symbols fetched, {d['feature_files']} feature files")
                bad = [s for s, q in d.get("quality", {}).items() if q.get("ok") is False or "warning" in q]
                lines.append(f"- quality: {len(d.get('quality', {}))} checked, {len(bad)} with warnings" + (f" ({', '.join(bad)})" if bad else ""))
        elif name == "backtest":
            best = None
            for sym, r in d.items():
                if "error" in r:
                    lines.append(f"- {sym}: ⚠ {r['error']}")
                else:
                    lines.append(f"- {sym}: PnL {r['pnl']*100:+.2f}% | Sharpe {r['sharpe']:.2f} | MaxDD {r['max_drawdown']*100:.2f}% | {r['n_trades']} trades")
                    if best is None or r["sharpe"] > best[1]["sharpe"]:
                        best = (sym, r)
            if best:
                lines.append(f"- 🏆 best Sharpe: {best[0]} ({best[1]['sharpe']:.2f})")
        elif name == "portfolio":
            lines.append(f"- HRP over {len(d['assets'])} assets | eff.N {d['effective_assets']} | ann.vol {d['annualized_vol']}%")
            top = sorted(d["weights"].items(), key=lambda kv: -kv[1])[:5]
            for a, w in top:
                lines.append(f"  - {a}: {w*100:.1f}%")
        elif name == "rl":
            lines.append(f"- {d.get('note') or d.get('trained') or 'checkpoint present'}")
    report = "\n".join(lines)
    briefs = ROOT / "telegram_briefs"
    briefs.mkdir(exist_ok=True)
    path = briefs / f"swarm_report_{datetime.now(SAST).strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text(report, encoding="utf-8")
    (ROOT / "telegram_status.md").write_text(report, encoding="utf-8")
    print(report)
    return {"report": str(path)}


# ---------------- STAGE 6: TELEGRAM PUSH ----------------
def push_telegram():
    import urllib.request
    env = {}
    envfile = Path(os.environ.get("HERMES_HOME", str(Path.home() / "AppData/Local/hermes"))) / ".env"
    if envfile.exists():
        for line in envfile.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID", "")
    if not token or "*" in token or not chat:
        print("Telegram: token/chat not available — skipping push (report saved locally)")
        return
    ok = sum(1 for r in results.values() if r["status"] == "ok")
    total = len(results)
    bt = results.get("backtest", {}).get("data", {})
    best = ""
    for sym, r in (bt.items() if isinstance(bt, dict) else []):
        if isinstance(r, dict) and "sharpe" in r:
            if not best or r["sharpe"] > bt[best].get("sharpe", -99):
                best = sym
    msg = (f"🐝 QUANT SWARM RUN — {ok}/{total} stages OK\n"
           f"🏆 Best Sharpe: {best}\n"
           f"⏱ Total: {sum(timings.values()):.0f}s\n"
           f"Full report: telegram_status.md")
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": msg}).encode(),
            headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        print(f"Telegram push: {'sent' if resp.get('ok') else 'failed ' + str(resp)}")
    except Exception as e:
        print(f"Telegram push failed: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rl-train", action="store_true", help="run a short PPO training session")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--skip-data", action="store_true", help="reuse local CSVs, skip fresh yfinance fetch")
    args = ap.parse_args()

    t0 = time.time()
    if args.skip_data:
        results["data"] = {"status": "ok", "data": {"note": "reused local feature store (--skip-data)"}}
        timings["data"] = 0.0
    else:
        run_data()
    run_backtests()
    run_rl(train=args.rl_train)
    run_portfolio()
    run_synthesis()
    if not args.no_telegram:
        push_telegram()
    print(f"\n🐝 SWARM RUN COMPLETE in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
