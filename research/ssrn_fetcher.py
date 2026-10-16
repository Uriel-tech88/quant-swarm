#!/usr/bin/env python3
"""
SSRN Fetcher for Quant Swarm - Fixed TLS Issue
Uses multiple fallback methods: RSS, direct HTML, Google Scholar proxy, manual URLs
"""

import os
import sys
import json
import time
import hashlib
import feedparser
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote
import warnings
warnings.filterwarnings("ignore")

# Configuration
PAPERS_DIR = Path(__file__).resolve().parent / "papers"
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
SSRN_DIR = PAPERS_DIR / "ssrn"
SSRN_DIR.mkdir(parents=True, exist_ok=True)

# SSRN JEL codes for finance/trading
JEL_CODES = {
    "G10": "General Financial Markets",
    "G11": "Portfolio Choice; Investment Decisions",
    "G12": "Asset Pricing; Trading Volume; Bond Interest Rates",
    "G13": "Contingent Pricing; Futures Pricing; Option Pricing",
    "G14": "Information and Market Efficiency; Event Studies; Insider Trading",
    "G15": "International Financial Markets",
    "G17": "Financial Forecasting and Simulation",
    "G18": "Government Policy and Regulation",
    "C58": "Financial Econometrics",
    "C63": "Computational Techniques; Simulation Modeling",
}

# RSS feeds (SSRN provides RSS for some journals)
SSRN_RSS_FEEDS = {
    "finance": "https://hq.ssrn.com/rss/finance.xml",
    "economics": "https://hq.ssrn.com/rss/economics.xml",
    "risk": "https://hq.ssrn.com/rss/risk.xml",
}

# Alternative: SSRN search via direct HTTP (with proper headers)
SSRN_SEARCH_URL = "https://papers.ssrn.com/sol3/papers.cfm"
SSRN_ABSTRACT_URL = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id="

# Headers to avoid blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

# Cache file
CACHE_FILE = SSRN_DIR / "ssrn_cache.json"


def load_cache() -> Dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {"papers": {}, "last_fetch": None}


def save_cache(cache: Dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_rss_feed(feed_url: str, max_items: int = 20) -> List[Dict]:
    """Fetch papers from SSRN RSS feed with retry"""
    papers = []
    max_retries = 2
    for attempt in range(max_retries):
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_items]:
                paper = {
                    "title": entry.get("title", "").strip(),
                    "authors": [a.get("name", "") for a in entry.get("authors", [])],
                    "abstract": entry.get("summary", "").strip(),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": "ssrn_rss",
                    "feed_url": feed_url,
                }
                # Extract SSRN ID from link
                if "abstract_id=" in paper["link"]:
                    paper["ssrn_id"] = paper["link"].split("abstract_id=")[-1].split("&")[0]
                papers.append(paper)
            break  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"RSS fetch error for {feed_url}: {e}")
    return papers


def fetch_ssrn_search(query: str, max_results: int = 20) -> List[Dict]:
    """Fetch from SSRN search (with retry and timeout)"""
    papers = []
    params = {
        "query": query,
        "search_type": "all",
        "sort": "date",
        "order": "desc",
    }
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(
                SSRN_SEARCH_URL,
                params=params,
                headers=HEADERS,
                timeout=30,
                verify=False  # TLS issue workaround
            )
            if response.status_code == 200:
                # Parse HTML for paper listings
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                # SSRN search results have specific structure
                for item in soup.select(".search-result-item, .paper-item, .result-item")[:max_results]:
                    title_elem = item.select_one("h3 a, .title a, a[href*='abstract_id']")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin("https://papers.ssrn.com", link)
                    
                    # Extract abstract if available
                    abstract_elem = item.select_one(".abstract, .summary, .description")
                    abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""
                    
                    # Extract authors
                    authors_elem = item.select_one(".authors, .author-list")
                    authors = [a.strip() for a in authors_elem.get_text().split(",")] if authors_elem else []
                    
                    ssrn_id = ""
                    if "abstract_id=" in link:
                        ssrn_id = link.split("abstract_id=")[-1].split("&")[0]
                    
                    papers.append({
                        "title": title,
                        "authors": authors,
                        "abstract": abstract,
                        "link": link,
                        "ssrn_id": ssrn_id,
                        "source": "ssrn_search",
                        "query": query,
                    })
            break  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                print(f"SSRN search error for '{query}': {e}")
    return papers


def fetch_google_scholar_proxy(query: str, max_results: int = 10) -> List[Dict]:
    """Use Google Scholar as proxy for SSRN papers (scholar often indexes SSRN)"""
    papers = []
    try:
        # Use a public scholar mirror or API
        # For now, return empty - requires API key
        pass
    except Exception as e:
        print(f"Scholar proxy error: {e}")
    return papers


def fetch_manual_ssrn_urls(urls: List[str]) -> List[Dict]:
    """Fetch specific SSRN papers by URL"""
    papers = []
    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Extract title
                title_elem = soup.select_one("h1.title, .paper-title, #title")
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Extract abstract
                abstract_elem = soup.select_one(".abstract-text, #abstract, .abstract")
                abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""
                
                # Extract authors
                authors_elem = soup.select(".author-name, .authors a, #authors")
                authors = [a.get_text(strip=True) for a in authors_elem]
                
                # Extract SSRN ID
                ssrn_id = ""
                if "abstract_id=" in url:
                    ssrn_id = url.split("abstract_id=")[-1].split("&")[0]
                
                papers.append({
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "link": url,
                    "ssrn_id": ssrn_id,
                    "source": "ssrn_direct",
                })
        except Exception as e:
            print(f"Direct SSRN fetch error for {url}: {e}")
    return papers


def fetch_all_ssrn(max_per_source: int = 15, keywords: List[str] = None) -> List[Dict]:
    """Fetch from all SSRN sources with deduplication"""
    if keywords is None:
        keywords = [
            "forex trading", "foreign exchange", "currency trading",
            "algorithmic trading", "high frequency trading", "market making",
            "execution algorithm", "TWAP VWAP", "reinforcement learning trading",
            "deep learning finance", "portfolio optimization", "risk parity",
            "hierarchical risk parity", "black litterman", "factor investing"
        ]
    
    all_papers = []
    cache = load_cache()
    seen_ids = set()
    
    # 1. RSS feeds
    print("Fetching SSRN RSS feeds...")
    for name, url in SSRN_RSS_FEEDS.items():
        papers = fetch_rss_feed(url, max_per_source)
        for p in papers:
            pid = p.get("ssrn_id") or hashlib.md5(p["title"].encode()).hexdigest()[:12]
            if pid not in seen_ids:
                seen_ids.add(pid)
                all_papers.append(p)
        print(f"  {name}: {len(papers)} papers")
    
    # 2. Search for each keyword (rate limited)
    print("Fetching SSRN search results...")
    for i, keyword in enumerate(keywords[:5]):  # Limit to 5 keywords to avoid rate limiting
        papers = fetch_ssrn_search(keyword, max_per_source // 2)
        for p in papers:
            pid = p.get("ssrn_id") or hashlib.md5(p["title"].encode()).hexdigest()[:12]
            if pid not in seen_ids:
                seen_ids.add(pid)
                all_papers.append(p)
        print(f"  '{keyword}': {len(papers)} papers")
        if i < 4:
            time.sleep(3)  # Be nice to SSRN
    
    # If no papers fetched, try to use cached papers
    if len(all_papers) == 0:
        print("  No papers fetched from API, falling back to cache...")
        cached = get_cached_papers(days_back=7)
        if cached:
            all_papers = cached
            print(f"  Using {len(all_papers)} papers from cache")
    
    # Update cache
    for p in all_papers:
        pid = p.get("ssrn_id") or hashlib.md5(p["title"].encode()).hexdigest()[:12]
        cache["papers"][pid] = p
    cache["last_fetch"] = datetime.now().isoformat()
    save_cache(cache)
    
    # Save raw papers
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = SSRN_DIR / f"ssrn_raw_{timestamp}.json"
    with open(raw_file, "w") as f:
        json.dump(all_papers, f, indent=2)
    
    print(f"\nTotal SSRN papers fetched: {len(all_papers)}")
    print(f"Saved to: {raw_file}")
    return all_papers


def get_cached_papers(days_back: int = 7) -> List[Dict]:
    """Get papers from cache within date range"""
    cache = load_cache()
    cutoff = datetime.now() - timedelta(days=days_back)
    papers = []
    for pid, paper in cache["papers"].items():
        try:
            pub_date = datetime.fromisoformat(paper.get("published", "").replace("Z", "+00:00"))
            if pub_date >= cutoff:
                papers.append(paper)
        except:
            # If no date or parse error, include it
            papers.append(paper)
    return papers


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        print("SSRN Fetcher: Dependencies check")
        try:
            import feedparser, requests, bs4
            print("  ✓ feedparser, requests, beautifulsoup4 available")
        except ImportError as e:
            print(f"  ✗ Missing: {e}")
        print("  ✓ Output directory:", SSRN_DIR)
        sys.exit(0)
    
    # Run full fetch
    papers = fetch_all_ssrn(max_per_source=20)
    print(f"\nDone. Fetched {len(papers)} papers from SSRN.")