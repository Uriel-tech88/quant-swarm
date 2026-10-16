---
# SKILL: quant-swarm-synthesis
# Trigger: Use when creating a new project that requires automated skill generation for quantitative trading with Phase 4 integration.
# Behavior: Generates complete SKILL.md with Phase 3 RL results, Phase 2 backtest analysis, Telegram briefing, and memory persistence.
---

SKILL.md

---
# SKILL: quant-swarm-synthesis

**Trigger:** Phase 4 synthesis — use when integrating Phase 3 RL results (PPO model) with Phase 2 backtests (11/11 symbols) to generate a complete project deliverable.

**Behavior:** Creates a comprehensive SKILL.md file that includes:
- Phase 3 model summary (trained PPO on EURUSD, 20k timesteps, 5 checkpoints)
- Phase 2 multi-symbol verification results (11/11 verified)
- Backtest chart reference (`backtests/eurusd_1m_interactive.html` — 6MB interactive chart)
- Portfolio optimization references (`black_litterman.py`, `hrp_optimizer.py`)
- Telegram briefing format with top 3 strategies + risk metrics
- Memory persistence instructions
- Complete file structure and verification steps

## <operations>:
- Read: `models/rl_checkpoints/ppo_EURUSDX_final.zip` (Phase 3 results)
- Read: `backtests/eurusd_1m_interactive.html` (backtest chart)
- Read: `multi_symbol_verification.md` (11/11 symbols)
- Read: `portfolio/black_litterman.py` (portfolio optimization)
- Read: `portfolio/hrp_optimizer.py` (HRP optimization)
- Write: `skills/quant-swarm-synthesis/SKILL.md` (complete documentation)
- Verify: Check generated SKILL.md has frontmatter + body + linked files

## <target>:
'user' profile — applies to `default` profile (current working directory: `/c/Users/gqama/AppData/Local/hermes/quant_swarm/`)

Note: The user wants the dashboard and ticker to work. The dashboard (port 9119) is initializing after gateway restart; ticker (port 9118) runs independently. Phase 4 synthesis creates the final deliverable; it does not affect the gateway or ticker operation.
