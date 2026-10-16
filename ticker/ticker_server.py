#!/usr/bin/env python3
"""Live ticker server for quant swarm symbols (11 symbols, yfinance)."""
import os, time, json, threading
from flask import Flask, jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

data = {"symbols": {}, "updated": None}

def refresh():
    try:
        import yfinance as yf
        symbols = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","GC=F","^GSPC","^DJI","^IXIC","GLD","SLV","USO","TLT"]
        tick = yf.Tickers(symbols).tickers
        out = {}
        for s in symbols:
            try:
                t = tick[s].info
                out[s] = {"price": t.get("regularMarketPrice"), "chg": t.get("regularMarketChangePercent")}
            except Exception:
                out[s] = {"price":"N/A","chg":"N/A"}
        data["symbols"] = out
        data["updated"] = time.strftime("%H:%M:%S")
    except Exception as e:
        data["updated"] = "error: " + str(e)[:60]

threading.Thread(target=lambda: [refresh(), time.sleep(30), refresh()], daemon=True).start()

@app.route("/")
def home(): return '<a href="/ticker">Ticker JSON</a>'
@app.route("/ticker")
def ticker(): return jsonify(data)

if __name__ == "__main__":
    refresh()
    app.run(host="0.0.0.0", port=9118, threaded=True)
