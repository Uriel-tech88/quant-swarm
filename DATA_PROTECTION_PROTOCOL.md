# STRICT DATA PROTECTION PROTOCOL — Quant Swarm (Thami / gqama)

## RULES (non-negotiable)

1. NEVER paste into a Hermes/OpenRouter prompt:
   - Tick data values (EURUSD=1.0854, GBPJPY, etc.)
   - Pipeline output / dollar-bars CSV rows
   - `pipeline_finmlkit.py` code snippets or logic
   - Strategy specs / `strategy_library.py` contents
   - `backtests/` results with exact PnL/Sharpe numbers
   - `.env` contents (TELEGRAM_BOT_TOKEN, GITHUB_TOKEN, etc.)
   - Portfolio weights / HRP allocations / RL checkpoint details
   - Multi-symbol verification table (11/11 symbols with exact values)

2. ALWAYS reference by file/path, not by content:
   - OK: "Check `data/features/dollar_bars_EURUSDX.csv`"
   - NOT OK: "Euro at 1.085 has sharp drop..."

3. `provider_routing: data_collection: "deny"` is ACTIVE — confirmed.
   - Providers cannot train/store your prompts.
   - They CAN still see prompt text during inference.

4. Telegram gateway (PID 15096) → Telegram only.
   - No bridge to OpenRouter.
   - Your chat messages to @Uriel88Bot stay with Telegram.

## WARNING MECHANISM (before sending to OpenRouter)

Run this check on any prompt BEFORE sending:
```bash
python backtests/check_sensitive_prompt.py "your prompt text"
```
If it prints WARNING → do NOT send. Only send if it prints OK.

## IF YOU ACCIDENTALLY SEND SENSITIVE DATA
- `data_collection: deny` prevents model training, but provider may have processed it.
- No retroactive deletion is guaranteed by OpenRouter.
- Do NOT include exact trading values in future prompts.
- Use local model (`ollama`) if working with sensitive pipeline outputs.

## LOCAL-ONLY ALTERNATIVE (zero external exposure)
```bash
hermes config set model.default "qwen/qwen-2.5-coder:32b"
hermes config set model.provider "ollama"
```

Created: 2026-10-17
Status: ACTIVE — enforce before every OpenRouter prompt.
