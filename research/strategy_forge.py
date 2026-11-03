#!/usr/bin/env python3
"""
STRATEGY FORGE — continuous search for elite-edge quantitative strategies.

Pipeline (daily, after the data-agent fetch):
  1. GENERATE  — parameterized candidate grid across SSRN/classic strategy families
  2. SHORTLIST — walk-forward train split (first 60% of bars) on 3 benchmark symbols
  3. VALIDATE  — out-of-sample split (last 40%) across the full 12-symbol universe
  4. PROMOTE   — elite gate: OOS Sharpe >= 1.0, OOS maxDD >= -10%, >= 8 trades,
                 positive OOS PnL, positive train Sharpe
  5. DECAY     — existing champions re-validated each run; OOS Sharpe < 0 -> retired
  6. REPORT    — Telegram only when a champion is promoted or demoted (no spam);
                 full results always saved to research/strategies/

Paper provenance: reads research/papers/latest_papers.json (strategy-ingestion
cron output) and tags candidate families referenced by newly discovered papers.
"""
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent          # quant_swarm/
if not (ROOT / "backtests").exists():                  # fallback when run from scripts/
    ROOT = Path(r"C:/Users/gqama/AppData/Local/hermes/quant_swarm")
sys.path.insert(0, str(ROOT / "backtests"))

import strategy_library as sl                           # noqa: E402
from strategy_library import backtest_single, load_hourly_ohlc  # noqa: E402

SAST = timezone(timedelta(hours=2))
RAW = ROOT / "raw"
STRAT_DIR = ROOT / "research" / "strategies"
PAPERS = ROOT / "research" / "papers" / "latest_papers.json"
REGISTRY = STRAT_DIR / "registry.json"
ENV_PATH = Path(r"C:/Users/gqama/AppData/Local/hermes/.env")

SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "GC=F",
           "^GSPC", "^DJI", "^IXIC", "GLD", "SLV", "USO", "TLT"]
BENCH = ["EURUSD=X", "GC=F", "^GSPC"]
TRAIN_FRAC = 0.60
SHORTLIST_N = 8
ELITE = dict(min_oos_sharpe=1.0, max_oos_dd=-0.10, min_trades=8,
             min_oos_pnl=0.0, min_train_sharpe=0.0)

FAMILY_TAGS = {  # paper keyword -> family provenance
    "momentum": ["momentum", "trend"],
    "mean reversion": ["bollinger", "ou_", "rsi", "williams", "reversal"],
    "volatility": ["vol_", "breakout_vol", "keltner", "atr_"],
    "statistical arbitrage": ["pairs_", "kalman_"],
    "machine learning": ["ou_", "kalman_"],
}


def raw_for(sym):
    safe = sym.replace("=", "").replace("/", "_")
    p = RAW / f"{safe}_1m.csv"
    return p if p.exists() else None


def build_candidates():
    """Parameterized candidate grid. Each entry: (id, family, params, sig_fn)."""
    c = []
    c.append(("rsi2_reversal#base", "rsi2_reversal", {}, sl.sig_rsi2_reversal))
    for lb in (12, 24, 48):
        c.append((f"short_term_reversal#lb{lb}", "short_term_reversal", {"lookback": lb},
                  partial(sl.sig_short_term_reversal, lookback=lb)))
    c.append(("bollinger_zscore#base", "bollinger_zscore", {}, sl.sig_bollinger_zscore))
    for w, z in ((40, 1.0), (60, 1.25)):
        c.append((f"ou_ar1_residual#w{w}z{z}", "ou_ar1_residual", {"window": w, "z_in": z},
                  partial(sl.sig_ou_ar1_residual, window=w, z_in=z)))
    c.append(("macd_trend#base", "macd_trend", {}, sl.sig_macd_trend))
    for f, s in ((5, 34), (9, 21), (12, 48)):
        c.append((f"ema_crossover#{f}x{s}", "ema_crossover", {"fast": f, "slow": s},
                  partial(sl.sig_ema_crossover, fast=f, slow=s)))
    for lb in (48, 72, 120):
        c.append((f"tsmom_vol_scaled#lb{lb}", "tsmom_vol_scaled", {"lookback": lb},
                  partial(sl.sig_tsmom_vol_scaled, lookback=lb)))
    for w in (20, 40):
        c.append((f"donchian_breakout#w{w}", "donchian_breakout", {"window": w},
                  partial(sl.sig_donchian_breakout, window=w)))
    c.append(("rsi14_classic#base", "rsi14_classic", {}, sl.sig_rsi14_classic))
    for k, d in ((14, 3), (21, 5)):
        c.append((f"stochastic_cross#{k}_{d}", "stochastic_cross", {"k": k, "d": d},
                  partial(sl.sig_stochastic_cross, k=k, d=d)))
    for p in (20, 30):
        c.append((f"cci_breakout#p{p}", "cci_breakout", {"period": p},
                  partial(sl.sig_cci_breakout, period=p)))
    for w in (20, 40):
        c.append((f"breakout_vol_filter#w{w}", "breakout_vol_filter", {"window": w},
                  partial(sl.sig_breakout_vol_filter, window=w)))
    for p in (14, 21):
        c.append((f"williams_r#p{p}", "williams_r", {"period": p},
                  partial(sl.sig_williams_r, period=p)))
    return c


def paper_provenance():
    """Map recently ingested papers to strategy families they reference."""
    if not PAPERS.exists():
        return {}
    try:
        papers = json.loads(PAPERS.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    provenance = {}
    for p in papers[:200]:
        text = (p.get("title", "") + " " + p.get("abstract", "")).lower()
        for kw, families in FAMILY_TAGS.items():
            if kw in text:
                for fam in families:
                    provenance.setdefault(fam, p.get("title", "")[:90])
    return provenance


def bt_on_slice(ohlc, sig_fn, slc):
    sub = ohlc.iloc[slc]
    if len(sub) < 30:
        return None
    return backtest_single(sub, sig_fn)


def run_forge(send_telegram=True):
    t0 = time.time()
    now = datetime.now(SAST)
    print(f"=== STRATEGY FORGE — {now.isoformat()} ===")

    provenance = paper_provenance()
    cands = build_candidates()
    print(f"Candidates: {len(cands)} | paper-tagged families: {len(provenance)}")

    ohlc_bench = {}
    for sym in BENCH:
        p = raw_for(sym)
        if p:
            ohlc_bench[sym] = load_hourly_ohlc(p)
    if len(ohlc_bench) < 2:
        raise RuntimeError("not enough benchmark data")

    # 1) shortlist on train slice
    scored = []
    for cid, fam, params, fn in cands:
        sharpes = []
        for sym, ohlc in ohlc_bench.items():
            cut = int(len(ohlc) * TRAIN_FRAC)
            m = bt_on_slice(ohlc, fn, slice(0, cut))
            if m and m["n_trades"] >= 3:
                sharpes.append(m["sharpe"])
        if sharpes:
            scored.append((cid, fam, params, fn, float(np.mean(sharpes))))
    scored.sort(key=lambda t: -t[4])
    shortlist = [s for s in scored if s[4] > ELITE["min_train_sharpe"]][:SHORTLIST_N]
    print(f"Shortlisted {len(shortlist)}/{len(cands)} (train Sharpe > {ELITE['min_train_sharpe']})")

    # 2) OOS validation across the universe
    registry = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {
        "champions": [], "challengers": [], "retired": [], "runs": []}
    champion_ids = {c["id"] for c in registry["champions"]}
    new_champions, challengers = [], []

    for cid, fam, params, fn, train_sharpe in shortlist:
        oos_sharpes, oos_pnls, oos_dds, trades = [], [], [], 0
        for sym in SYMBOLS:
            p = raw_for(sym)
            if not p:
                continue
            ohlc = load_hourly_ohlc(p)
            cut = int(len(ohlc) * TRAIN_FRAC)
            m = bt_on_slice(ohlc, fn, slice(cut, len(ohlc)))
            if m:
                oos_sharpes.append(m["sharpe"])
                oos_pnls.append(m["pnl"])
                oos_dds.append(m["max_drawdown"])
                trades += m["n_trades"]
        if len(oos_sharpes) < 5:
            continue
        rec = {
            "id": cid, "family": fam, "params": params,
            "train_sharpe": round(train_sharpe, 2),
            "oos_sharpe": round(float(np.mean(oos_sharpes)), 2),
            "oos_pnl_pct": round(float(np.sum(oos_pnls)) * 100, 2),
            "oos_maxdd": round(float(np.min(oos_dds)), 4),
            "n_trades": trades, "n_symbols": len(oos_sharpes),
            "promoted": now.strftime("%Y-%m-%d %H:%M SAST"),
            "source": provenance.get(fam, "template-grid"),
        }
        elite = (rec["oos_sharpe"] >= ELITE["min_oos_sharpe"]
                 and rec["oos_maxdd"] >= ELITE["max_oos_dd"]
                 and trades >= ELITE["min_trades"]
                 and rec["oos_pnl_pct"] > ELITE["min_oos_pnl"])
        if elite:
            rec["status"] = "champion"
            if cid not in champion_ids:
                new_champions.append(rec)
                registry["champions"].append(rec)
            else:
                for i, c in enumerate(registry["champions"]):
                    if c["id"] == cid:
                        registry["champions"][i] = rec
        else:
            rec["status"] = "challenger"
            challengers.append(rec)

    # 3) decay check on existing champions not refreshed this run
    demoted = []
    refreshed = {c["id"] for c in new_champions} | champion_ids & {s[0] for s in shortlist}
    keep = []
    for c in registry["champions"]:
        if c["id"] in refreshed:
            keep.append(c)
            continue
        # re-validate on current OOS window
        try:
            fn = dict((cid, f) for cid, _, _, f in build_candidates())[c["id"]]
            ohlc = load_hourly_ohlc(raw_for("EURUSD=X"))
            cut = int(len(ohlc) * TRAIN_FRAC)
            m = bt_on_slice(ohlc, fn, slice(cut, len(ohlc)))
            if m and m["sharpe"] < 0:
                c["status"] = "retired"
                c["retired_reason"] = f"decayed OOS sharpe {m['sharpe']:.2f}"
                c["retired"] = now.strftime("%Y-%m-%d %H:%M SAST")
                demoted.append(c)
                registry["retired"].append(c)
                continue
        except Exception:
            pass
        keep.append(c)
    registry["champions"] = keep

    # merge challengers (keep latest per id, top 20 by oos sharpe)
    chal = {c["id"]: c for c in registry.get("challengers", [])}
    chal.update({c["id"]: c for c in challengers})
    registry["challengers"] = sorted(chal.values(), key=lambda r: -r["oos_sharpe"])[:20]

    registry["runs"].append({
        "ts": now.isoformat(), "candidates": len(cands),
        "shortlisted": len(shortlist), "new_champions": [c["id"] for c in new_champions],
        "demoted": [c["id"] for c in demoted], "secs": round(time.time() - t0, 1)})
    registry["updated"] = now.isoformat()
    STRAT_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    # 4) report
    print(f"\nChampions: {len(registry['champions'])} | new: {len(new_champions)} | demoted: {len(demoted)}")
    for c in registry["champions"]:
        print(f"  🏆 {c['id']:28s} OOS Sharpe {c['oos_sharpe']:+.2f} | PnL {c['oos_pnl_pct']:+.2f}% | DD {c['oos_maxdd']*100:.1f}% | {c['n_trades']} trades")

    report_path = STRAT_DIR / f"forge_{now.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps({
        "champions": registry["champions"], "new_champions": new_champions,
        "demoted": demoted, "top_challengers": registry["challengers"][:10],
    }, indent=2), encoding="utf-8")
    print(f"Saved: {report_path.name} + registry.json")

    if send_telegram and (new_champions or demoted):
        send_forge_telegram(new_champions, demoted, len(cands), time.time() - t0)
    return registry


def send_forge_telegram(new_champions, demoted, n_cands, secs):
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    token, chat = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", "")
    if not token or "*" in token or not chat:
        print("Telegram: credentials unavailable — skipped")
        return
    lines = [f"🏭 STRATEGY FORGE — {len(new_champions)} new elite strateg{'y' if len(new_champions)==1 else 'ies'}",
             f"Screened {n_cands} candidates in {secs:.0f}s (walk-forward OOS, 12 symbols)"]
    for c in new_champions:
        lines.append(f"\n🏆 {c['id']}\n  OOS Sharpe {c['oos_sharpe']:+.2f} | PnL {c['oos_pnl_pct']:+.2f}% | DD {c['oos_maxdd']*100:.1f}% | {c['n_trades']} trades\n  src: {c['source'][:60]}")
    for c in demoted:
        lines.append(f"\n⚠️ demoted {c['id']}: {c.get('retired_reason','decayed')}")
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": "\n".join(lines)[:3900]}).encode(),
            headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        print(f"Telegram: {'sent' if resp.get('ok') else resp}")
    except Exception as e:
        print(f"Telegram failed: {e}")


if __name__ == "__main__":
    run_forge(send_telegram="--no-telegram" not in sys.argv)
