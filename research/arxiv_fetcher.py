#!/usr/bin/env python3
"""
Enhanced arXiv Fetcher for Quant Swarm
Fetches q-fin.TR, q-fin.PM, q-fin.CP, cs.LG, stat.ML papers with full metadata
"""

import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET
import warnings
warnings.filterwarnings("ignore")

# Configuration
PAPERS_DIR = Path(__file__).resolve().parent / "papers"
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
ARXIV_DIR = PAPERS_DIR / "arxiv"
ARXIV_DIR.mkdir(parents=True, exist_ok=True)

# arXiv categories for quant finance
ARXIV_CATEGORIES = {
    "q-fin.TR": "Trading and Market Microstructure",
    "q-fin.PM": "Portfolio Management",
    "q-fin.CP": "Computational Finance",
    "q-fin.RM": "Risk Management",
    "q-fin.ST": "Statistical Finance",
    "q-fin.EC": "Econometrics",
    "q-fin.GN": "General Finance",
    "cs.LG": "Machine Learning",
    "stat.ML": "Machine Learning (Statistics)",
    "cs.CV": "Computer Vision (for chart pattern)",
    "cs.AI": "Artificial Intelligence",
    "econ.GN": "General Economics",
    "physics.data-an": "Data Analysis (HFT)",
}

# arXiv API
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_ABS_URL = "https://arxiv.org/abs/"

# Cache
CACHE_FILE = ARXIV_DIR / "arxiv_cache.json"


def load_cache() -> Dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {"papers": {}, "last_fetch": None}


def save_cache(cache: Dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_arxiv_category(
    category: str,
    max_results: int = 50,
    days_back: int = 30,
    start_date: Optional[str] = None
) -> List[Dict]:
    """Fetch papers from a single arXiv category with retry logic"""
    papers = []
    
    # Build search query
    if start_date:
        # Format: YYYYMMDD
        search_query = f"cat:{category} AND submittedDate:[{start_date} TO *]"
    else:
        search_query = f"cat:{category}"
    
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    
    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
    
    # Retry logic with exponential backoff
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "QuantSwarm/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read().decode("utf-8")
            
            # Parse XML
            root = ET.fromstring(data)
            
            # Namespace
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            
            for entry in root.findall("atom:entry", ns):
                # Extract basic info
                arxiv_id = entry.find("atom:id", ns).text.split("/")[-1]
                title = entry.find("atom:title", ns).text.strip()
                summary = entry.find("atom:summary", ns).text.strip()
                published = entry.find("atom:published", ns).text
                updated = entry.find("atom:updated", ns).text
                
                # Authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns).text
                    authors.append(name)
                
                # Categories
                categories = []
                for cat in entry.findall("atom:category", ns):
                    categories.append(cat.get("term"))
                
                # Links
                pdf_url = ""
                abs_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href")
                    elif link.get("rel") == "alternate":
                        abs_url = link.get("href")
                
                # Comment (often contains journal ref)
                comment_elem = entry.find("arxiv:comment", ns)
                comment = comment_elem.text if comment_elem is not None else ""
                
                # Journal ref
                journal_ref_elem = entry.find("arxiv:journal_ref", ns)
                journal_ref = journal_ref_elem.text if journal_ref_elem is not None else ""
                
                # DOI
                doi_elem = entry.find("arxiv:doi", ns)
                doi = doi_elem.text if doi_elem is not None else ""
                
                paper = {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "authors": authors,
                    "abstract": summary,
                    "categories": categories,
                    "primary_category": category,
                    "published": published,
                    "updated": updated,
                    "pdf_url": pdf_url,
                    "abs_url": abs_url or f"{ARXIV_ABS_URL}{arxiv_id}",
                    "comment": comment,
                    "journal_ref": journal_ref,
                    "doi": doi,
                    "source": "arxiv",
                }
                papers.append(paper)
            
            # Success - break out of retry loop
            break
            
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{max_retries} for {category} after {delay}s: {e}")
                time.sleep(delay)
            else:
                print(f"Error fetching arXiv {category} after {max_retries} attempts: {e}")
    
    return papers


def fetch_arxiv_multiple(
    categories: List[str] = None,
    max_per_category: int = 30,
    days_back: int = 7,
    keywords: List[str] = None
) -> List[Dict]:
    """Fetch from multiple arXiv categories with keyword filtering"""
    if categories is None:
        categories = list(ARXIV_CATEGORIES.keys())
    
    # Calculate start date
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
    
    all_papers = []
    cache = load_cache()
    seen_ids = set()
    
    print(f"Fetching arXiv papers from {len(categories)} categories (last {days_back} days)...")
    
    for i, category in enumerate(categories):
        papers = fetch_arxiv_category(category, max_per_category, days_back, start_date)
        
        # Filter by keywords if provided
        if keywords:
            filtered = []
            for p in papers:
                text = (p["title"] + " " + p["abstract"]).lower()
                if any(kw.lower() in text for kw in keywords):
                    filtered.append(p)
            papers = filtered
        
        for p in papers:
            if p["arxiv_id"] not in seen_ids:
                seen_ids.add(p["arxiv_id"])
                all_papers.append(p)
        
        print(f"  {category} ({ARXIV_CATEGORIES.get(category, category)}): {len(papers)} papers")
        
        # Longer delay between requests to avoid rate limiting
        if i < len(categories) - 1:
            time.sleep(3)  # 3 seconds between categories
    
    # If no papers fetched, try to use cached papers
    if len(all_papers) == 0:
        print("  No papers fetched from API, falling back to cache...")
        cached = get_cached_papers(days_back=days_back)
        if cached:
            # Filter cached by keywords if provided
            if keywords:
                filtered = []
                for p in cached:
                    text = (p.get("title", "") + " " + p.get("abstract", "")).lower()
                    if any(kw.lower() in text for kw in keywords):
                        filtered.append(p)
                cached = filtered
            all_papers = cached
            print(f"  Using {len(all_papers)} papers from cache")
    
    # Update cache with new papers
    for p in all_papers:
        cache["papers"][p["arxiv_id"]] = p
    cache["last_fetch"] = datetime.now().isoformat()
    save_cache(cache)
    
    # Save raw
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = ARXIV_DIR / f"arxiv_raw_{timestamp}.json"
    with open(raw_file, "w") as f:
        json.dump(all_papers, f, indent=2)
    
    print(f"\nTotal arXiv papers: {len(all_papers)}")
    print(f"Saved to: {raw_file}")
    return all_papers


def search_arxiv_by_keywords(
    keywords: List[str],
    max_results: int = 100,
    days_back: int = 30
) -> List[Dict]:
    """Search arXiv by keywords across all quant categories"""
    # Combine keywords with OR
    keyword_query = " OR ".join([f'all:"{kw}"' for kw in keywords])
    category_query = " OR ".join([f'cat:{cat}' for cat in ARXIV_CATEGORIES.keys()])
    search_query = f"({keyword_query}) AND ({category_query})"
    
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    
    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "QuantSwarm/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode("utf-8")
        
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        
        papers = []
        for entry in root.findall("atom:entry", ns):
            arxiv_id = entry.find("atom:id", ns).text.split("/")[-1]
            title = entry.find("atom:title", ns).text.strip()
            summary = entry.find("atom:summary", ns).text.strip()
            published = entry.find("atom:published", ns).text
            
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            categories = [c.get("term") for c in entry.findall("atom:category", ns)]
            
            pdf_url = ""
            abs_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                elif link.get("rel") == "alternate":
                    abs_url = link.get("href")
            
            papers.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": authors,
                "abstract": summary,
                "categories": categories,
                "published": published,
                "pdf_url": pdf_url,
                "abs_url": abs_url or f"{ARXIV_ABS_URL}{arxiv_id}",
                "source": "arxiv_keyword_search",
            })
        
        return papers
    
    except Exception as e:
        print(f"Keyword search error: {e}")
        return []


def download_pdf(arxiv_id: str, output_dir: Path = None) -> Optional[Path]:
    """Download PDF for a paper"""
    if output_dir is None:
        output_dir = ARXIV_DIR / "pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    output_path = output_dir / f"{arxiv_id}.pdf"
    
    if output_path.exists():
        return output_path
    
    try:
        urllib.request.urlretrieve(pdf_url, output_path)
        return output_path
    except Exception as e:
        print(f"PDF download failed for {arxiv_id}: {e}")
        return None


def get_cached_papers(days_back: int = 7) -> List[Dict]:
    """Get papers from cache within date range"""
    cache = load_cache()
    cutoff = datetime.now() - timedelta(days=days_back)
    papers = []
    for arxiv_id, paper in cache["papers"].items():
        try:
            pub_date = datetime.fromisoformat(paper.get("published", "").replace("Z", "+00:00"))
            if pub_date >= cutoff:
                papers.append(paper)
        except:
            papers.append(paper)
    return papers


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        print("arXiv Fetcher: Dependencies check")
        print("  ✓ urllib, xml.etree, json available (stdlib)")
        print("  ✓ Output directory:", ARXIV_DIR)
        sys.exit(0)
    
    # Default keywords for quant trading
    keywords = [
        "trading", "portfolio", "reinforcement learning", "deep learning",
        "forex", "foreign exchange", "execution", "market making",
        "risk parity", "black litterman", "hierarchical risk",
        "factor investing", "alpha", "market microstructure"
    ]
    
    papers = fetch_arxiv_multiple(
        categories=["q-fin.TR", "q-fin.PM", "q-fin.CP", "cs.LG", "stat.ML"],
        max_per_category=30,
        days_back=7,
        keywords=keywords
    )
    print(f"\nDone. Fetched {len(papers)} relevant papers from arXiv.")