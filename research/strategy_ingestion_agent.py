#!/usr/bin/env python3
"""
Strategy Ingestion Agent — Combines SSRN + arXiv fetchers for Strategy Swarm
Runs daily 5 AM via cron. Outputs raw papers to research/papers/
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ssrn_fetcher import fetch_all_ssrn
from arxiv_fetcher import fetch_arxiv_multiple
from pathlib import Path
from datetime import datetime
import json

RESEARCH_DIR = Path(__file__).resolve().parent
PAPERS_DIR = RESEARCH_DIR / "papers"

# Keywords for quant trading strategies
QUANT_KEYWORDS = [
    "trading strategy", "mean reversion", "momentum", "statistical arbitrage",
    "market making", "execution algorithm", "TWAP", "VWAP", "implementation shortfall",
    "factor investing", "portfolio optimization", "risk parity", "hierarchical risk parity",
    "black litterman", "regime switching", "hidden markov", "volatility targeting",
    "reinforcement learning", "deep learning", "LSTM", "transformer", "XGBoost",
    "forex", "foreign exchange", "currency trading", "high frequency",
    "news sentiment", "alternative data", "order flow", "options flow",
    "crypto trading", "DeFi", "yield farming", "MEV", "funding rate",
    "variance risk premium", "dispersion trading", "gamma scalping",
]

def main():
    print("=" * 60)
    print("STRATEGY INGESTION AGENT — Daily Paper Fetch")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    all_papers = []
    
    # 1. Fetch SSRN (with TLS workaround)
    print("\n[1/2] Fetching SSRN papers...")
    try:
        ssrn_papers = fetch_all_ssrn(max_per_source=25, keywords=QUANT_KEYWORDS[:8])
        all_papers.extend(ssrn_papers)
        print(f"  ✓ SSRN: {len(ssrn_papers)} papers")
    except Exception as e:
        print(f"  ✗ SSRN error: {e}")
    
    # 2. Fetch arXiv (quant categories)
    print("\n[2/2] Fetching arXiv papers...")
    try:
        arxiv_categories = [
            "q-fin.TR", "q-fin.PM", "q-fin.CP", "q-fin.RM", "q-fin.ST",
            "cs.LG", "stat.ML", "cs.AI", "econ.GN", "physics.data-an"
        ]
        arxiv_papers = fetch_arxiv_multiple(
            categories=arxiv_categories,
            max_per_category=30,
            days_back=7,
            keywords=QUANT_KEYWORDS
        )
        all_papers.extend(arxiv_papers)
        print(f"  ✓ arXiv: {len(arxiv_papers)} papers")
    except Exception as e:
        print(f"  ✗ arXiv error: {e}")
    
    # Deduplicate by title similarity
    print("\n[3/3] Deduplicating...")
    seen = set()
    unique_papers = []
    for p in all_papers:
        title_key = p.get("title", "").lower().strip()[:80]
        if title_key and title_key not in seen:
            seen.add(title_key)
            unique_papers.append(p)
    
    print(f"  Total unique papers: {len(unique_papers)}")
    
    # Save combined output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = PAPERS_DIR / f"combined_papers_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(unique_papers, f, indent=2)
    
    # Also save latest symlink
    latest_file = PAPERS_DIR / "latest_papers.json"
    with open(latest_file, "w") as f:
        json.dump(unique_papers, f, indent=2)
    
    print(f"\n✓ Ingestion complete!")
    print(f"  Papers saved: {output_file}")
    print(f"  Latest: {latest_file}")
    print(f"  Total: {len(unique_papers)} unique papers")
    
    # Summary by source
    sources = {}
    for p in unique_papers:
        src = p.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    for src, count in sources.items():
        print(f"  {src}: {count}")
    
    return {
        "total_papers": len(unique_papers),
        "by_source": sources,
        "output_file": str(output_file),
        "timestamp": timestamp,
    }

if __name__ == "__main__":
    if "--check" in sys.argv:
        print("Strategy Ingestion Agent: Dependencies check")
        try:
            import feedparser, requests, bs4
            print("  ✓ feedparser, requests, beautifulsoup4 available")
        except ImportError as e:
            print(f"  ✗ Missing: {e}")
        try:
            import urllib.request, xml.etree.ElementTree
            print("  ✓ arXiv fetcher deps (stdlib)")
        except ImportError as e:
            print(f"  ✗ Missing: {e}")
        print("  ✓ Output dir:", PAPERS_DIR)
        sys.exit(0)
    
    result = main()
    print(f"\nResult: {result}")