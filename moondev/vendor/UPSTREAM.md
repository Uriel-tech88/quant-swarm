# MoonDev Vendored Code — Provenance

- Source repo: https://github.com/daydy-dev/moon-dev-ai-agents-for-trading
- Upstream commit: 96885ef9f478d1543a4a1dc7d13aee05f0304bd5 (fetched 2026-11-03)
- Files vendored unchanged:
  - trading_agent.py (391 lines, the LLM decision agent)
  - config.py (70 lines, upstream config template)
- LICENSE: upstream repo ships NO license file. Treat as all-rights-reserved:
  personal/local use and study only; do not redistribute publicly.
- NOT vendored (Solana execution layer, out of scope):
  - src/core/nice_funcs.py (needs solders/Birdeye, 1169 lines)
  - src/core/bot.py (Solana trading loop)
  - src/data/ohlcv_collector.py (Birdeye data source)
  - data CSVs, examples/, docs/
- Adaptation layer (our code, repo-licensed): ../openrouter_client.py,
  ../data_adapter.py, ../agent.py, ../run_moondev.py
