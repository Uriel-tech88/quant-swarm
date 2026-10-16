"""Phase 3: RL Training Agent — PPO on Forex Trading Environment.
Trains Stable-Baselines3 PPO agent on the custom forex gym environment.
Saves checkpoints to models/rl_checkpoints/.
"""
import os
import json
from pathlib import Path
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback
from rl_envs.forex_env import ForexTradingEnv

BASE = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = BASE / "models" / "rl_checkpoints"
LOG_DIR = BASE / "logs" / "orchestrator"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def make_env(symbol="EURUSD=X"):
    def _init():
        return ForexTradingEnv(symbol=symbol, window_size=60, initial_capital=10000.0)
    return _init

def train_ppo(symbol="EURUSD=X", total_timesteps=20000, save_interval=5000):
    """Train PPO agent on forex environment."""
    print(f"=== Phase 3: RL Training Agent ===")
    print(f"Symbol: {symbol}, Timesteps: {total_timesteps}")
    
    # Create vectorized environment
    env = DummyVecEnv([make_env(symbol)])
    
    # Initialize PPO model
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=0.0003,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=1,
    )
    
    # Checkpoint callback
    checkpoint_callback = CheckpointCallback(
        save_freq=save_interval,
        save_path=str(CHECKPOINT_DIR),
        name_prefix=f"ppo_{symbol.replace('=', '').replace('/', '_')}",
    )
    
    # Train
    model.learn(total_timesteps=total_timesteps, callback=checkpoint_callback, progress_bar=True)
    
    # Save final model
    model_path = CHECKPOINT_DIR / f"ppo_{symbol.replace('=', '').replace('/', '_')}_final"
    model.save(model_path)
    print(f"Model saved to: {model_path}")
    
    return model

if __name__ == "__main__":
    # Train on EURUSD
    model = train_ppo(symbol="EURUSD=X", total_timesteps=20000, save_interval=5000)
    print("\n✓ Phase 3 RL training complete for EURUSD=X")