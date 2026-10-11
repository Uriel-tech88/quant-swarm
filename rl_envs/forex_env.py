"""FinRL Forex Environment — Phase 3.
Simple gym environment wrapper for forex/indices data for RL trading.
Provides observation: Close prices + technical indicators, action: [-1, 1] for position.
"""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from pathlib import Path
import pandas as pd

class ForexTradingEnv(gym.Env):
    """Gym environment for forex/indices trading with step-based position sizing.
    
    Observation: last N rows of [close, rsi, macd, bb_upper, bb_lower, volume]
    Action: sell=-1, hold=0, buy=+1
    Reward: PnL change per step
    """
    metadata = {"render_modes": ["human"], "render_fps": 30}
    
    def __init__(self, symbol="EURUSD=X", window_size=60, initial_capital=10000.0, transaction_cost=0.001):
        super().__init__()
        self.symbol = symbol
        self.window_size = window_size
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        
        # Action: sell=-1, hold=0, buy=+1 (discrete)
        self.action_space = spaces.Discrete(3)
        
        # Observation: window_size x 7 features (close, rsi, macd, bb_u, bb_l, vol, ma20)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(window_size, 7), dtype=np.float32)
        
        self._load_data()
        self.reset()
        
    def _load_data(self):
        data_file = Path(f"/c/Users/gqama/AppData/Local/hermes/quant_swarm/data/raw/{self.symbol.replace('=', '').replace('/', '_')}_1m.csv")
        if not data_file.exists():
            # Fallback: generate random data
            dates = pd.date_range('2026-09-01', periods=5000, freq='1min')
            prices = 1.05 + np.cumsum(np.random.randn(5000) * 0.001)
            self.data = pd.DataFrame({'Close': prices, 'Volume': np.random.randint(1000, 10000, 5000)}, index=dates)
        else:
            self.data = pd.read_csv(data_file, index_col=0, parse_dates=True)
            if 'Close' not in self.data.columns:
                if isinstance(self.data.columns, pd.MultiIndex):
                    self.data.columns = [c[0] if isinstance(c, tuple) else c for c in self.data.columns]
                self.data = self.data[['Close', 'Volume'] if 'Volume' in self.data.columns else ['Close']]
        
        # Calculate features if not present
        close = self.data['Close']
        self.data['RSI'] = self._rsi(close)
        self.data['MACD'] = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        self.data['BB_Upper'] = bb_mid + 2 * bb_std
        self.data['BB_Lower'] = bb_mid - 2 * bb_std
        self.data['MA20'] = bb_mid
        self.data['MA50'] = close.rolling(50).mean()
        
        self.feature_cols = ['Close', 'RSI', 'MACD', 'BB_Upper', 'BB_Lower', 'Volume', 'MA20']
        self.data = self.data.dropna().reset_index(drop=True)
        
    def _rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        return 100 - 100 / (1 + gain / loss)
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = self.window_size
        self.position = 0
        self.cash = self.initial_capital
        self.entry_price = None
        return self._get_obs(), {}
    
    def _get_obs(self):
        obs = self.data[self.feature_cols].iloc[self.current_step - self.window_size:self.current_step].values
        return obs.astype(np.float32)
    
    def step(self, action):
        # Decode action: -1=sell, 0=hold, +1=buy
        target_pos = action - 1  # convert 0/1/2 to -1/0/1
        price = self.data['Close'].iloc[self.current_step]
        
        # Execute position change
        if target_pos != self.position:
            # Close existing position
            if self.position != 0 and self.entry_price is not None:
                pnl = (price - self.entry_price) * self.position
                self.cash += pnl - self.transaction_cost * abs(price)
            self.position = target_pos
            if target_pos != 0:
                self.entry_price = price - self.transaction_cost * price
        
        # Calculate reward
        if self.position != 0:
            unrealized = (price - self.entry_price) * self.position
            reward = unrealized
        else:
            reward = 0
        reward = float(reward) / self.initial_capital  # normalize
        
        self.current_step += 1
        done = self.current_step >= len(self.data) - 1
        obs = self._get_obs() if not done else np.zeros_like(self.observation_space.low)
        
        info = {"cash": self.cash, "step": self.current_step, "position": self.position}
        return obs, reward, done, done, info
    
    def render(self):
        print(f"Step: {self.current_step}, Cash: {self.cash:.2f}, Position: {self.position}")

if __name__ == "__main__":
    env = ForexTradingEnv(symbol="EURUSD=X")
    obs, _ = env.reset()
    print(f"Observation shape: {obs.shape}")
    for _ in range(10):
        action = env.action_space.sample()
        obs, reward, done, truncated, info = env.step(action)
        print(f"Action: {action}, Reward: {reward:.6f}, Done: {done}")
        if done or truncated:
            break
    print("Environment test complete.")