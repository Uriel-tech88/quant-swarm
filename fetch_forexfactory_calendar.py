#!/usr/bin/env python3
"""ForexFactory Economic Calendar Fetch — improves data quality (news filtering)."""
import requests, pandas as pd, os
from datetime import datetime

url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
try:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    # Handle variable column names
    if 'date' in df.columns and 'time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    elif len(df.columns) >= 2:
        df['timestamp'] = pd.to_datetime(df.iloc[:, 0] + ' ' + df.iloc[:, 1])
    # Filter high-impact events
    if 'impact' in df.columns:
        df = df[df['impact'].isin(['High', 'Medium'])]
    os.makedirs('data/raw/forexfactory', exist_ok=True)
    df.to_parquet(f"data/raw/forexfactory/calendar_{datetime.now():%Y%m%d}.parquet")
    print(f"✓ ForexFactory calendar fetched: {len(df)} events (High/Medium)")
except Exception as e:
    print(f"✗ ForexFactory fetch failed (will retry): {e}")
