# MoonDev Integration (analysis layer)

MoonDev-style LLM trading agent running on the quant swarm's existing
data, wired to free OpenRouter models. Storage footprint: ~40 KB code,
zero new data downloads (reuses the 12-symbol feature store).

## What this is

- `vendor/` — pristine upstream files from
  [daydy-dev/moon-dev-ai-agents-for-trading](https://github.com/daydy-dev/moon-dev-ai-agents-for-trading)
  @96885ef (726 KB repo, code-only mirror). See `vendor/UPSTREAM.md`.
  Upstream ships no license file: personal/local use only.
- `agent.py` — the upstream decision loop (prompts, BUY/SELL/NOTHING +
  confidence parsing, allocation pass), adapted:
  - Anthropic (paid) -> OpenRouter free models via `openrouter_client.py`
  - Birdeye/Solana data -> our `features/*.csv` via `data_adapter.py`
  - Solana execution (`ai_entry`/`chunk_kill`) -> removed; analysis only
- `openrouter_client.py` — anthropic-interface shim over OpenRouter,
  with provider routing `data_collection=deny, sort=price`.
- `run_moondev.py` — CLI.

## Run it

From repo root, Hermes bundled Python:

```
python -m moondev.run_moondev --list
python -m moondev.run_moondev --symbols EURUSDX GBPUSDX GLD
python -m moondev.run_moondev --symbols EURUSDX --allocate 10000
```

Use the full interpreter path for cron/scripts:
`C:/Users/gqama/AppData/Local/hermes/tools/python-3.14.7+20260901-win32-x64/python.exe`

Model: `MOONDEV_MODEL` env var or `--model` (default
`nvidia/nemotron-3-ultra-550b-a55b:free`). API key is read from the
environment or `../.env` (Hermes `.env`) — never printed.

## Where it fits in the swarm

- Research agent -> strategy_forge continues to find/backtest champions.
- MoonDev layer -> discretionary LLM second opinion per symbol
  (MA20/MA40 + RSI + volume + recent moves), saved to
  `moondev/runs/*.csv` for later comparison against champion signals.
- Execution -> unchanged (none; this repo stays analysis-only).

## Fixes applied vs upstream

- Allocation placeholders ({MAX_POSITION_PERCENTAGE} etc.) were never
  expanded by the upstream f-string — filled via .replace() here.
- Action parsing tolerates models that don't put BUY/SELL/NOTHING on
  line 1.
- tz-aware CSV parsing uses pd.to_datetime(format='mixed', utc=True).
