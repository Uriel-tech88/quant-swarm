#!/usr/bin/env python3
"""
Strict Data Protection Protocol — Prompt Scanner
Checks Hermes prompts BEFORE sending to OpenRouter.
Prints WARNING if sensitive quant data detected.
Usage: python backtests/check_sensitive_prompt.py "your prompt text here"
"""
import sys, re, os

# Sensitive patterns that should NEVER leave the machine
SENSITIVE_PATTERNS = [
    # Tick data values (4-5 decimal places, common FX/price format)
    (r'\b1\.[0-9]{4,5}\b', 'Tick price value (e.g. EURUSD 1.08540)'),
    (r'\b0\.[0-9]{4,6}\b', 'Tick price value (e.g. GBPJPY 0.0073)'),
    (r'\b[0-9]{2,5}\.[0-9]{4,6}\b', 'Price with volume pattern'),
    # Pipeline output
    (r'dollar_bars_', 'Dollar-bar CSV reference'),
    (r'triple.?barrier', 'Triple-barrier label reference'),
    # Strategy code
    (r'def momentum_signal', 'Strategy function definition'),
    (r'Portfolio\.from_signals', 'Portfolio construction code'),
    # Credentials
    (r'ghp_[A-Za-z0-9]{20,}', 'GitHub PAT token'),
    (r'[0-9]{8,10}:[A-Za-z0-9_-]{30,}', 'Telegram bot token'),
    (r'\.env', 'Environment file reference'),
    # Portfolio / RL
    (r'HRP\b', 'HRP portfolio allocation'),
    (r'ppo_EURUSDX', 'RL checkpoint filename'),
    # Exact PnL / Sharpe
    (r'Sharpe\s*[=:]\s*[0-9]+\.[0-9]+', 'Sharpe ratio value'),
    (r'PnL\s*[=:]\s*[\$]?[-0-9.]+', 'PnL value'),
    (r'11/11\s*symbol', 'Multi-symbol verification table'),
]

# Allowed patterns (file paths are OK to mention)
ALLOWED_PATTERNS = [
    r'^.*\.py$',          # File paths
    r'^.*\.csv$',         # CSV paths
    r'^.*\.html$',        # HTML paths
    r'^.*\.md$',          # Markdown paths
    r'^.*\.yaml$',       # YAML paths
    r'^.*\.json$',        # JSON paths
]

def check_prompt(text: str) -> tuple:
    """Returns (ok: bool, warnings: list[str])."""
    warnings = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Skip file paths (allowed)
        if any(re.search(pat, line) for pat in ALLOWED_PATTERNS):
            continue
        for pattern, label in SENSITIVE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                warnings.append(f"Line {i}: {label} — {line.strip()[:80]}")
    
    return (len(warnings) == 0, warnings)

def main():
    if len(sys.argv) < 2:
        print("Usage: python backtests/check_sensitive_prompt.py 'your prompt text'")
        sys.exit(2)
    
    text = sys.argv[1]
    ok, warnings = check_prompt(text)
    
    if ok:
        print("✓ OK — No sensitive data detected. Safe to send to OpenRouter.")
        sys.exit(0)
    else:
        print("⚠️  WARNING — Sensitive data detected. DO NOT SEND TO OPENROUTER.")
        print(f"   Found {len(warnings)} issue(s):")
        for w in warnings:
            print(f"   • {w}")
        print("\n   Options:")
        print("   1. Remove the sensitive values from your prompt.")
        print("   2. Reference files by path instead of content.")
        print("   3. Switch to local model (ollama) for this task.")
        sys.exit(1)

if __name__ == "__main__":
    main()