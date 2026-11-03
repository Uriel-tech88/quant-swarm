"""
OpenRouter client with an anthropic-SDK-compatible interface.

Lets the vendored MoonDev agent pattern (client.messages.create(...))
run on free OpenRouter models instead of a paid Anthropic key.

Provider routing is configurable because it interacts with model choice:
  - :free models (e.g. nemotron:free) are served only by endpoints that
    train on prompts -> data_collection="deny" returns HTTP 404 for them.
  - Paid models (e.g. moonshotai/kimi-k3) work fine with deny.
Default: no explicit routing (inherits OpenRouter account settings).
Set MOONDEV_PROVIDER_DENY=1 to force {"data_collection": "deny",
"sort": "price"} — use only with paid models.

Key resolution order:
  1. OPENROUTER_API_KEY environment variable
  2. Hermes .env at <hermes_home>/.env (repo root is <hermes_home>/quant_swarm)
The key is never printed or logged.
"""

import os
import json
import time
import requests
from pathlib import Path
from types import SimpleNamespace

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

_PROVIDER_ROUTING = (
    {"data_collection": "deny", "sort": "price"}
    if os.getenv("MOONDEV_PROVIDER_DENY") == "1"
    else None
)


def load_api_key():
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("OPENROUTER_API_KEY not found in environment or Hermes .env")


class _Messages:
    def __init__(self, api_key):
        self._key = api_key

    def create(self, model, max_tokens, temperature, messages):
        """Mimics anthropic.messages.create; returns obj.content -> [obj(text=...)]."""
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if _PROVIDER_ROUTING:
            body["provider"] = _PROVIDER_ROUTING
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
        if resp.status_code == 429:
            time.sleep(20)
            resp = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=120,
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return SimpleNamespace(
            content=[SimpleNamespace(text=text)],
            model=data.get("model", model),
            usage=usage,
        )


class OpenRouterClient:
    """Drop-in replacement for anthropic.Anthropic used by the vendored agent."""

    def __init__(self, api_key=None):
        self.messages = _Messages(api_key or load_api_key())
