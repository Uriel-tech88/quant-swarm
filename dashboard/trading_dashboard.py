"""
Quant Swarm Trading Dashboard — stdlib HTTP server, port 9120.

Panels:
  1. MoonDev Signals   — latest LLM recommendations (BUY/SELL/NOTHING,
                         confidence bars, reasoning), run history
  2. Performance       — Strategy Forge champions + challengers
                         (OOS Sharpe, PnL, max DD, trades)
  3. Agent Monitor     — gateway state, service ports, data freshness,
                         cron observability from disk artifacts
  4. Market Strip      — 12-symbol last price + sparkline + session move

Data: read live from disk on every request (features/*.csv,
moondev/runs/*.csv, research/strategies/registry.json,
gateway_state.json) + TCP probes. No framework, no deps beyond pandas.

Run (persistent):  python dashboard/trading_dashboard.py  (from repo root)
"""

import glob
import json
import socket
import html as html_mod
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
FEATURES = REPO / "features"
RUNS = REPO / "moondev" / "runs"
REGISTRY = REPO / "research" / "strategies" / "registry.json"
GATEWAY_STATE = Path(r"C:\Users\gqama\AppData\Local\hermes\gateway_state.json")

PORT = 9120
REFRESH_SEC = 30
SPARK_BARS = 60

SYMBOL_LABELS = {
    "EURUSDX": "EUR/USD", "GBPUSDX": "GBP/USD", "USDJPYX": "USD/JPY",
    "AUDUSDX": "AUD/USD", "^GSPC": "S&P 500", "^DJI": "Dow Jones",
    "^IXIC": "Nasdaq", "GLD": "Gold ETF", "SLV": "Silver ETF",
    "USO": "Oil ETF", "TLT": "20Y Treasuries", "GCF": "Gold Futures",
}

ACTION_COLORS = {
    "BUY": "#00ff9f", "SELL": "#ff2e63", "NOTHING": "#8a8f98",
    "ERROR": "#ffb800",
}

# ---------------------------------------------------------------- data


def probe_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def load_moondev():
    runs = sorted(glob.glob(str(RUNS / "*_recommendations.csv")))
    latest, history = None, []
    for path in runs:
        try:
            df = pd.read_csv(path)
            df["run"] = Path(path).stem.split("_recommendations")[0]
            history.append(df)
        except Exception:
            continue
    if history:
        latest = history[-1]
    return latest, history


def load_registry():
    if not REGISTRY.exists():
        return {"champions": [], "challengers": []}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {"champions": [], "challengers": []}


def load_features():
    rows = []
    for path in sorted(glob.glob(str(FEATURES / "features_*.csv"))):
        key = Path(path).stem.replace("features_", "")
        try:
            df = pd.read_csv(path, usecols=["Datetime", "Close"])
            closes = df["Close"].dropna()
            if closes.empty:
                continue
            last = float(closes.iloc[-1])
            ref = float(closes.iloc[-97]) if len(closes) > 97 else float(closes.iloc[0])
            chg = (last / ref - 1) * 100 if ref else 0.0
            spark = closes.tail(SPARK_BARS).tolist()
            ts = pd.to_datetime(df["Datetime"].iloc[-1], format="mixed", utc=True)
            age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
            rows.append({
                "key": key, "label": SYMBOL_LABELS.get(key, key),
                "last": last, "chg": chg, "spark": spark, "age_min": age_min,
            })
        except Exception:
            continue
    return rows


def monitor_rows():
    rows = []
    try:
        gs = json.loads(GATEWAY_STATE.read_text(encoding="utf-8"))
        gstate = gs.get("gateway_state", "unknown")
        gpid = gs.get("pid", "?")
    except Exception:
        gstate, gpid = "unreadable", "?"
    rows.append(("Telegram gateway", gstate == "running",
                 f"state={gstate} pid={gpid}"))
    for name, port in [("Ticker server :9118", 9118),
                       ("Hermes dashboard :9119", 9119),
                       ("Trading dashboard :9120", 9120)]:
        rows.append((name, probe_port(port),
                     "listening" if probe_port(port) else "DOWN"))
    feats = sorted(glob.glob(str(FEATURES / "features_*.csv")),
                   key=lambda p: Path(p).stat().st_mtime, reverse=True)
    if feats:
        age = (datetime.now() - datetime.fromtimestamp(
            Path(feats[0]).stat().st_mtime)).total_seconds() / 3600
        rows.append(("Feature store", age < 26,
                     f"{len(feats)} symbol files, freshest {age:.1f}h ago"))
    runs = sorted(glob.glob(str(RUNS / "*_recommendations.csv")),
                  key=lambda p: Path(p).stat().st_mtime, reverse=True)
    if runs:
        age = (datetime.now() - datetime.fromtimestamp(
            Path(runs[0]).stat().st_mtime)).total_seconds() / 3600
        rows.append(("MoonDev runs", age < 26,
                     f"{len(runs)} run files, latest {age:.1f}h ago"))
    reg = load_registry()
    rows.append(("Strategy Forge", len(reg.get("champions", [])) > 0,
                 f"{len(reg.get('champions', []))} champions, "
                 f"{len(reg.get('challengers', []))} challengers"))
    return rows

# ---------------------------------------------------------------- render


def esc(s):
    return html_mod.escape(str(s))


def sparkline_svg(values, width=140, height=34, color="#00e5ff"):
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1e-12
    pts = " ".join(
        f"{i / (len(values) - 1) * width:.1f},"
        f"{height - (v - lo) / rng * (height - 4) - 2:.1f}"
        for i, v in enumerate(values)
    )
    return (f'<svg width="{width}" height="{height}" class="spark">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1.5"/></svg>')


def render_moondev(latest, history):
    if latest is None:
        return '<div class="card"><h2>MoonDev Signals</h2><p class="dim">No runs yet.</p></div>'
    rows = []
    for _, r in latest.iterrows():
        action = str(r["action"]).upper()
        color = ACTION_COLORS.get(action, "#8a8f98")
        conf = int(r["confidence"]) if pd.notna(r["confidence"]) else 0
        reasoning = esc(str(r.get("reasoning", ""))[:400])
        rows.append(f"""
        <div class="sig">
          <div class="sig-head">
            <span class="sym">{esc(r['symbol'])}</span>
            <span class="badge" style="background:{color}22;color:{color};
                  border:1px solid {color}">{action}</span>
            <span class="conf">{conf}%</span>
          </div>
          <div class="bar"><div style="width:{conf}%;background:{color}"></div></div>
          <details><summary>reasoning</summary><p>{reasoning}</p></details>
        </div>""")
    run_id = esc(str(latest["run"].iloc[0]))
    hist_rows = ""
    for df in reversed(history[-6:]):
        rid = esc(str(df["run"].iloc[0]))
        buys = int((df["action"] == "BUY").sum())
        sells = int((df["action"] == "SELL").sum())
        noth = int((df["action"] == "NOTHING").sum())
        hist_rows += (f"<tr><td>{rid}</td><td class='buy'>{buys}</td>"
                      f"<td class='sell'>{sells}</td><td>{noth}</td></tr>")
    return f"""
    <div class="card">
      <h2>MoonDev Signals <span class="dim">run {run_id} UTC</span></h2>
      <div class="sig-grid">{''.join(rows)}</div>
      <h3>Run history</h3>
      <table><tr><th>run</th><th>BUY</th><th>SELL</th><th>NOTHING</th></tr>
      {hist_rows}</table>
    </div>"""


def render_perf(reg):
    def row(s, champion):
        return (f"<tr><td>{esc(s.get('id','?'))}</td>"
                f"<td>{s.get('oos_sharpe','?'):+}</td>"
                f"<td>{s.get('oos_pnl_pct','?')}%</td>"
                f"<td>{s.get('oos_maxdd','?')}</td>"
                f"<td>{s.get('n_trades','?')}</td>"
                f"<td>{s.get('n_symbols','?')}</td>"
                f"<td>{'CHAMPION' if champion else 'challenger'}</td></tr>")
    champs = "".join(row(s, True) for s in reg.get("champions", []))
    challs = "".join(row(s, False) for s in reg.get("challengers", [])[:8])
    return f"""
    <div class="card">
      <h2>Performance — Strategy Forge</h2>
      <table>
        <tr><th>strategy</th><th>OOS Sharpe</th><th>PnL</th>
            <th>max DD</th><th>trades</th><th>symbols</th><th>status</th></tr>
        {champs}{challs}
      </table>
    </div>"""


def render_monitor(rows):
    trs = "".join(
        f"<tr><td>{esc(n)}</td>"
        f"<td class={'ok' if ok else 'bad'}"
        f">{'UP' if ok else 'DOWN'}</td><td class='dim'>{esc(d)}</td></tr>"
        for n, ok, d in rows
    )
    return f'<div class="card"><h2>Agent Monitor</h2><table>{trs}</table></div>'


def render_market(rows):
    cards = []
    for r in rows:
        chg = r["chg"]
        color = "#00ff9f" if chg >= 0 else "#ff2e63"
        prec = 5 if r["last"] < 20 else 2
        stale = " stale" if r["age_min"] > 90 else ""
        cards.append(f"""
        <div class="mkt{stale}">
          <div class="dim">{esc(r['label'])}</div>
          <div class="price">{r['last']:.{prec}f}</div>
          <div style="color:{color}">{chg:+.2f}%</div>
          {sparkline_svg(r['spark'])}
        </div>""")
    return f'<div class="card"><h2>Market Strip</h2><div class="mkt-grid">{"".join(cards)}</div></div>'


CSS = """
* {box-sizing: border-box; margin: 0; padding: 0;}
body {background:#0a0e14; color:#c8d0dc; font-family:'Segoe UI',Arial,sans-serif;
      padding:18px; }
h1 {color:#00e5ff; font-size:22px; letter-spacing:2px;}
h2 {color:#00e5ff; font-size:15px; margin-bottom:10px; letter-spacing:1px;}
h3 {color:#7a8494; font-size:12px; margin:12px 0 6px;}
.card {background:#11161f; border:1px solid #1e2635; border-radius:8px;
       padding:14px; margin-bottom:16px;}
.dim {color:#7a8494; font-weight:normal; font-size:12px;}
.grid2 {display:grid; grid-template-columns:1fr 1fr; gap:16px;}
@media (max-width:1100px){.grid2{grid-template-columns:1fr;}}
.sig-grid {display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
           gap:10px;}
.sig {background:#0d1220; border:1px solid #1e2635; border-radius:6px; padding:10px;}
.sig-head {display:flex; justify-content:space-between; align-items:center;
           margin-bottom:6px;}
.sym {font-weight:bold; color:#e6ecf3;}
.badge {padding:2px 10px; border-radius:4px; font-weight:bold; font-size:12px;}
.conf {color:#c8d0dc; font-size:12px;}
.bar {height:5px; background:#1e2635; border-radius:3px; overflow:hidden;}
.bar div {height:100%;}
details {margin-top:6px;} summary {color:#7a8494; cursor:pointer; font-size:11px;}
details p {font-size:11px; color:#9aa3b0; margin-top:4px; white-space:pre-wrap;}
table {width:100%; border-collapse:collapse; font-size:12px;}
th {text-align:left; color:#7a8494; border-bottom:1px solid #1e2635; padding:4px;}
td {padding:4px; border-bottom:1px solid #161c28;}
.ok {color:#00ff9f; font-weight:bold;} .bad {color:#ff2e63; font-weight:bold;}
.buy {color:#00ff9f;} .sell {color:#ff2e63;}
.mkt-grid {display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
           gap:10px;}
.mkt {background:#0d1220; border:1px solid #1e2635; border-radius:6px;
      padding:8px; text-align:center;}
.mkt.stale {opacity:.5;} .price {font-size:18px; color:#e6ecf3; margin:2px 0;}
.spark {display:block; margin:4px auto 0;}
.ts {color:#525a68; font-size:11px; text-align:right;}
"""


def render():
    latest, history = load_moondev()
    reg = load_registry()
    market = load_features()
    mon = monitor_rows()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html><html><head>
<meta http-equiv="refresh" content="{REFRESH_SEC}">
<meta charset="utf-8"><title>Quant Swarm — Trading Dashboard</title>
<style>{CSS}</style></head><body>
<h1>QUANT SWARM // TRADING DASHBOARD</h1>
<p class="ts">rendered {now} local — auto-refresh {REFRESH_SEC}s</p>
{render_market(market)}
<div class="grid2">
{render_moondev(latest, history)}
{render_perf(reg)}
</div>
{render_monitor(mon)}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"Trading dashboard on http://127.0.0.1:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
