"""
MoonDev-style trading agent adapted for the quant swarm.

Keeps the upstream decision logic (prompts, BUY/SELL/NOTHING first line,
confidence extraction, allocation pass) from
vendor/trading_agent.py (daydy-dev/moon-dev-ai-agents-for-trading @96885ef),
but swaps:
  - Anthropic paid API  -> OpenRouter free models (openrouter_client.py)
  - Birdeye/Solana data -> our existing features/*.csv (data_adapter.py)
  - Solana execution    -> removed entirely (analysis + allocation only)

Prompts below are verbatim Moon Dev prompts (see vendor/), with the
allocation placeholders filled via .replace() — the upstream f-string
never actually expanded them (latent upstream bug, fixed here).
"""

import json
import re

import pandas as pd

from .openrouter_client import OpenRouterClient, DEFAULT_MODEL
from .data_adapter import build_market_data

# --- Prompts verbatim from Moon Dev's trading_agent.py (attribution) ---

TRADING_PROMPT = """
You are Moon Dev's AI Trading Assistant 🌙

Analyze the provided market data and make a trading decision based on these criteria:
1. Price action relative to MA20 and MA40
2. RSI levels and trend
3. Volume patterns
4. Recent price movements

Respond in this exact format:
1. First line must be one of: BUY, SELL, or NOTHING (in caps)
2. Then explain your reasoning, including:
   - Technical analysis
   - Risk factors
   - Market conditions
   - Confidence level (as a percentage, e.g. 75%)

Remember: Moon Dev always prioritizes risk management! 🛡️
"""

ALLOCATION_PROMPT = """
You are Moon Dev's Portfolio Allocation Assistant 🌙

Given the total portfolio size and trading recommendations, allocate capital efficiently.
Consider:
1. Position sizing based on confidence levels
2. Risk distribution
3. Keep cash buffer as specified
4. Maximum allocation per position

Format your response as a Python dictionary:
{
    "token_address": allocated_amount,  # In USD
    ...
    "USDC_ADDRESS": remaining_cash  # Always use USDC_ADDRESS for cash
}

Remember:
- Total allocations must not exceed total_size
- Higher confidence should get larger allocations
- Never allocate more than {MAX_POSITION_PERCENTAGE}% to a single position
- Keep at least {CASH_PERCENTAGE}% in USDC as safety buffer
- Only allocate to BUY recommendations
- Cash must be stored as USDC using USDC_ADDRESS: {USDC_ADDRESS}
"""

# Allocation constants (from upstream config.py; cash label adapted)
MAX_POSITION_PERCENTAGE = 30
CASH_PERCENTAGE = 20
CASH_LABEL = "CASH_USD"  # upstream uses Solana USDC mint address

AI_MAX_TOKENS = 1024
AI_TEMPERATURE = 0.7


def _extract_text(message):
    response = message.content
    if isinstance(response, list):
        response = "\n".join(
            item.text if hasattr(item, "text") else str(item) for item in response
        )
    return response


class MoonDevAgent:
    """Analysis + allocation only. No execution, no exchange keys."""

    def __init__(self, model=None):
        self.model = model or DEFAULT_MODEL
        self.client = OpenRouterClient()
        self.recommendations_df = pd.DataFrame(
            columns=["symbol", "action", "confidence", "reasoning"]
        )

    def analyze(self, symbol, market_data):
        message = self.client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            temperature=AI_TEMPERATURE,
            messages=[
                {
                    "role": "user",
                    "content": f"{TRADING_PROMPT}\n\nMarket Data to Analyze:\n{market_data}",
                }
            ],
        )
        response = _extract_text(message)

        lines = response.split("\n")
        action = lines[0].strip().upper() if lines else "NOTHING"
        if action not in ("BUY", "SELL", "NOTHING"):
            # model didn't follow format; scan for a standalone action line
            for ln in lines:
                if ln.strip().upper() in ("BUY", "SELL", "NOTHING"):
                    action = ln.strip().upper()
                    break
            else:
                action = "NOTHING"

        confidence = 0
        for line in lines:
            if "confidence" in line.lower():
                # upstream grabbed ALL digits in the line ("70% ... MA20/MA40"
                # -> 70204040); take only the number attached to a % or the
                # first small int after the word "confidence"
                m = re.search(r"(\d{1,3})\s*%", line)
                if not m:
                    m = re.search(r"confidence[^\d]{0,25}(\d{1,3})\b", line, re.I)
                if m:
                    confidence = min(100, int(m.group(1)))
                    break

        reasoning = "\n".join(lines[1:]).strip() or "No detailed reasoning provided"
        self.recommendations_df = pd.concat(
            [
                self.recommendations_df,
                pd.DataFrame(
                    [
                        {
                            "symbol": symbol,
                            "action": action,
                            "confidence": confidence,
                            "reasoning": reasoning,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        return response

    def allocate(self, total_size):
        buy_df = self.recommendations_df[
            self.recommendations_df["action"] == "BUY"
        ].copy()
        if buy_df.empty:
            return {CASH_LABEL: total_size}

        max_position_size = total_size * MAX_POSITION_PERCENTAGE / 100
        prompt = (
            ALLOCATION_PROMPT.replace(
                "{MAX_POSITION_PERCENTAGE}", str(MAX_POSITION_PERCENTAGE)
            )
            .replace("{CASH_PERCENTAGE}", str(CASH_PERCENTAGE))
            .replace("{USDC_ADDRESS}", CASH_LABEL)
            .replace("USDC_ADDRESS", CASH_LABEL)
        )
        # free models ramble and get truncated mid-dict; force compact output
        prompt += (
            "\n\nCRITICAL: Respond with ONLY the Python dictionary on a "
            "SINGLE line. No reasoning, no markdown fences, no other text."
        )
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max(AI_MAX_TOKENS, 2048),
            temperature=AI_TEMPERATURE,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\nTotal Size: ${total_size}\n"
                        f"Max Position Size: ${max_position_size}\n\n"
                        f"Recommendations:\n{buy_df.to_string()}"
                    ),
                }
            ],
        )
        allocation_str = _extract_text(message)
        start = allocation_str.find("{")
        end = allocation_str.rfind("}") + 1
        if start == -1 or end <= start:
            return {CASH_LABEL: total_size, "_parse_error": allocation_str[:200]}
        try:
            return json.loads(allocation_str[start:end])
        except json.JSONDecodeError:
            # tolerate python-dict style single quotes
            cleaned = re.sub(r"'", '"', allocation_str[start:end])
            return json.loads(cleaned)

    def run_once(self, symbols):
        for sym in symbols:
            try:
                market_data = build_market_data(sym)
                self.analyze(sym, market_data)
            except Exception as e:
                # one bad symbol (rate limit, data gap) must not kill the batch
                self.recommendations_df = pd.concat(
                    [
                        self.recommendations_df,
                        pd.DataFrame(
                            [{"symbol": sym, "action": "ERROR", "confidence": 0,
                              "reasoning": str(e)[:200]}]
                        ),
                    ],
                    ignore_index=True,
                )
            rec = self.recommendations_df.iloc[-1]
            print(
                f"[{sym}] {rec['action']} ({rec['confidence']}% conf) — "
                f"{rec['reasoning'][:120].replace(chr(10), ' ')}"
            )
        return self.recommendations_df
