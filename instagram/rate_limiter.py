"""
Adaptive Rate Limiting dengan Reinforcement Learning — Algorithm 5

Q-Learning agent yang belajar pola rate limit Instagram secara real-time.
Semakin sering dipakai, semakin pintar menentukan delay optimal.

State Space (240 states):
  - time_since_last: 8 bins (0-120s)
  - error_rate: 5 bins (0-100%)
  - hour_of_day: 6 bins (0-23 jam)

Action Space (6 actions):
  - 0: 1-2s (agresif)
  - 1: 2-4s (normal)
  - 2: 4-8s (cautious)
  - 3: 8-15s (safe)
  - 4: 15-30s (conservative)
  - 5: 30-60s (ultra-safe)

Reward:
  +1.0 untuk request sukses
  -1.0 untuk 429 rate limit
  -0.3 untuk error lainnya
"""

import json
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ==================== CONSTANTS ====================

# State discretization bins
TIME_BINS = [0, 1, 2, 4, 8, 15, 30, 60]           # 8 bins
ERROR_RATE_BINS = [0.0, 0.1, 0.25, 0.5, 0.75]       # 5 bins
HOUR_BINS = [0, 4, 8, 12, 17, 21]                   # 6 bins (night, early, morning, afternoon, evening, late)

# Action → delay ranges (min, max) in seconds
ACTION_DELAYS = [
    (1.0, 2.0),     # 0: agresif
    (2.0, 4.0),     # 1: normal
    (4.0, 8.0),     # 2: cautious
    (8.0, 15.0),    # 3: safe
    (15.0, 30.0),   # 4: conservative
    (30.0, 60.0),   # 5: ultra-safe
]

NUM_ACTIONS = len(ACTION_DELAYS)

# Total state space
NUM_TIME_BINS = len(TIME_BINS)
NUM_ERROR_BINS = len(ERROR_RATE_BINS)
NUM_HOUR_BINS = len(HOUR_BINS)
TOTAL_STATES = NUM_TIME_BINS * NUM_ERROR_BINS * NUM_HOUR_BINS  # 240

# Rewards
REWARD_SUCCESS = 1.0
REWARD_RATE_LIMITED = -1.0
REWARD_OTHER_ERROR = -0.3

# Default hyperparameters
DEFAULT_ALPHA = 0.1        # Learning rate
DEFAULT_GAMMA = 0.9        # Discount factor
DEFAULT_EPSILON = 0.15     # Initial exploration rate
DEFAULT_EPSILON_MIN = 0.05 # Minimum exploration
DEFAULT_EPSILON_DECAY = 0.9995  # Per-step decay


# ==================== STATE REPRESENTATION ====================

@dataclass
class RLState:
    """State representation for the Q-learning agent"""
    time_since_last: float = 0.0   # Seconds since last request
    error_rate: float = 0.0        # Rolling error rate (0.0 - 1.0)
    hour_of_day: int = 0           # Current hour (0-23)
    
    def to_index(self) -> int:
        """Convert continuous state to discrete index for Q-table lookup"""
        t_bin = _discretize(self.time_since_last, TIME_BINS)
        e_bin = _discretize(self.error_rate, ERROR_RATE_BINS)
        h_bin = _discretize(float(self.hour_of_day), [float(x) for x in HOUR_BINS])
        
        return (t_bin * NUM_ERROR_BINS * NUM_HOUR_BINS +
                e_bin * NUM_HOUR_BINS +
                h_bin)
    
    def describe(self) -> str:
        """Human-readable state description"""
        if self.error_rate > 0.5:
            err_label = "HIGH"
        elif self.error_rate > 0.2:
            err_label = "MEDIUM"
        else:
            err_label = "LOW"
        
        if 0 <= self.hour_of_day < 6:
            time_label = "night"
        elif 6 <= self.hour_of_day < 12:
            time_label = "morning"
        elif 12 <= self.hour_of_day < 18:
            time_label = "afternoon"
        else:
            time_label = "evening"
        
        return f"t={self.time_since_last:.1f}s, err={err_label}({self.error_rate:.0%}), {time_label}"


def _discretize(value: float, bins: List[float]) -> int:
    """Map a continuous value to a bin index"""
    for i in range(len(bins) - 1, -1, -1):
        if value >= bins[i]:
            return i
    return 0


# ==================== Q-LEARNING AGENT ====================

class AdaptiveRateLimiter:
    """
    Q-Learning based rate limiter that learns optimal request timing.
    
    Usage:
        rl = AdaptiveRateLimiter()
        
        # Before each request
        delay = rl.smart_delay()   # Returns actual delay applied
        
        # After each request
        rl.record_result(success=True)   # or success=False for 429
        
        # Stats
        print(rl.get_stats())
        
        # Persist policy (auto-saved periodically)
        rl.save_policy()
    """
    
    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        gamma: float = DEFAULT_GAMMA,
        epsilon: float = DEFAULT_EPSILON,
        epsilon_min: float = DEFAULT_EPSILON_MIN,
        epsilon_decay: float = DEFAULT_EPSILON_DECAY,
        policy_file: str = "instagram_rl_policy.json",
        window_size: int = 20,
        auto_save_interval: int = 50,
        debug: bool = False,
    ):
        """
        Args:
            alpha: Learning rate (0.0-1.0)
            gamma: Discount factor (0.0-1.0)
            epsilon: Initial exploration rate
            epsilon_min: Minimum exploration rate
            epsilon_decay: Decay rate per step
            policy_file: Path to persist Q-table
            window_size: Rolling window for error rate calculation
            auto_save_interval: Save policy every N steps
            debug: Print debug info
        """
        # Hyperparameters
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        
        # Q-Table: state_index → [q_values for each action]
        self.q_table: Dict[int, List[float]] = {}
        
        # Result tracking
        self.result_window: deque = deque(maxlen=window_size)
        self.window_size = window_size
        
        # Timing
        self._last_request_time: float = 0.0
        self._last_state_index: Optional[int] = None
        self._last_action: Optional[int] = None
        
        # Stats
        self._total_steps: int = 0
        self._total_rewards: float = 0.0
        self._total_success: int = 0
        self._total_rate_limited: int = 0
        self._action_counts: List[int] = [0] * NUM_ACTIONS
        self._recent_rewards: deque = deque(maxlen=100)
        
        # Persistence
        self.policy_file = Path(policy_file)
        self.auto_save_interval = auto_save_interval
        self.debug = debug
        
        # Load existing policy if available
        self.load_policy()
    
    # ==================== PUBLIC API ====================
    
    def smart_delay(self) -> float:
        """
        Determine and apply the optimal delay before a request.
        Drop-in replacement for static smart_delay().
        
        Returns:
            float: Actual delay applied (seconds)
        """
        # Build current state
        state = self._get_current_state()
        state_index = state.to_index()
        
        # Choose action (ε-greedy)
        action = self._choose_action(state_index)
        
        # Calculate delay with jitter
        min_delay, max_delay = ACTION_DELAYS[action]
        delay = random.uniform(min_delay, max_delay)
        
        # Add small Gaussian jitter for human-like behavior
        jitter = random.gauss(0, delay * 0.1)
        delay = max(0.5, delay + jitter)
        
        # Store for Q-table update after result
        self._last_state_index = state_index
        self._last_action = action
        
        # Apply delay
        if self.debug:
            print(f"  [RL] State: {state.describe()} → Action {action} (delay {delay:.1f}s) "
                  f"[ε={self.epsilon:.3f}]")
        
        time.sleep(delay)
        
        # Track action usage
        self._action_counts[action] += 1
        
        return delay
    
    def record_result(self, success: bool, rate_limited: bool = False):
        """
        Record the outcome of a request and update Q-table.
        
        Args:
            success: True if request returned valid data
            rate_limited: True if got 429 status
        """
        # Compute reward
        if rate_limited:
            reward = REWARD_RATE_LIMITED
            self._total_rate_limited += 1
        elif success:
            reward = REWARD_SUCCESS
            self._total_success += 1
        else:
            reward = REWARD_OTHER_ERROR
        
        # Track result for error rate
        self.result_window.append(1 if success else 0)
        
        # Update Q-table
        if self._last_state_index is not None and self._last_action is not None:
            self._update_q_value(
                self._last_state_index,
                self._last_action,
                reward,
            )
        
        # Update timing
        self._last_request_time = time.time()
        
        # Stats
        self._total_steps += 1
        self._total_rewards += reward
        self._recent_rewards.append(reward)
        
        # Decay exploration
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        
        # Auto-save
        if self._total_steps > 0 and self._total_steps % self.auto_save_interval == 0:
            self.save_policy()
            if self.debug:
                print(f"  [RL] Auto-saved policy at step {self._total_steps}")
        
        if self.debug:
            action_label = ["agresif", "normal", "cautious", "safe", "conservative", "ultra-safe"][self._last_action or 0]
            result_label = "✓" if success else ("⚠ 429" if rate_limited else "✗")
            print(f"  [RL] {result_label} reward={reward:+.1f} (action={action_label})")
    
    def get_stats(self) -> Dict:
        """Get comprehensive training statistics"""
        avg_reward = (self._total_rewards / self._total_steps) if self._total_steps > 0 else 0
        recent_avg = (sum(self._recent_rewards) / len(self._recent_rewards)) if self._recent_rewards else 0
        
        # Find dominant action
        if self._total_steps > 0:
            dominant_action = self._action_counts.index(max(self._action_counts))
            action_labels = ["agresif", "normal", "cautious", "safe", "conservative", "ultra-safe"]
            dominant_label = action_labels[dominant_action]
        else:
            dominant_label = "none"
        
        # Q-table coverage
        non_zero_states = sum(1 for v in self.q_table.values() if any(q != 0 for q in v))
        
        return {
            'total_steps': self._total_steps,
            'total_success': self._total_success,
            'total_rate_limited': self._total_rate_limited,
            'success_rate': f"{(self._total_success / self._total_steps * 100):.1f}%" if self._total_steps > 0 else "N/A",
            'avg_reward': round(avg_reward, 3),
            'recent_avg_reward': round(recent_avg, 3),
            'epsilon': round(self.epsilon, 4),
            'q_table_states_explored': non_zero_states,
            'q_table_coverage': f"{(non_zero_states / TOTAL_STATES * 100):.1f}%",
            'dominant_action': dominant_label,
            'action_distribution': {
                f"a{i}_{['agresif','normal','cautious','safe','conservative','ultra-safe'][i]}": count
                for i, count in enumerate(self._action_counts)
            },
            'current_error_rate': f"{self._get_error_rate():.0%}",
            'policy_file': str(self.policy_file),
        }
    
    def print_stats(self):
        """Print formatted training statistics"""
        stats = self.get_stats()
        print(f"""
╔══════════════════════════════════════════════════╗
║   🧠 RL Rate Limiter — Training Stats           ║
╠══════════════════════════════════════════════════╣
║  Total Steps:       {stats['total_steps']:>6}                      ║
║  Success Rate:      {stats['success_rate']:>8}                    ║
║  Rate Limited:      {stats['total_rate_limited']:>6}                      ║
║  Avg Reward:        {stats['avg_reward']:>+7.3f}                    ║
║  Recent Avg:        {stats['recent_avg_reward']:>+7.3f}                    ║
║  Exploration (ε):   {stats['epsilon']:>7.4f}                    ║
║  Q-Table Coverage:  {stats['q_table_coverage']:>8}                    ║
║  Dominant Action:   {stats['dominant_action']:<12}                ║
║  Error Rate:        {stats['current_error_rate']:>8}                    ║
╚══════════════════════════════════════════════════╝""")
    
    # ==================== Q-LEARNING CORE ====================
    
    def _get_current_state(self) -> RLState:
        """Build current state from environment observations"""
        now = time.time()
        
        # Time since last request
        if self._last_request_time > 0:
            time_since = now - self._last_request_time
        else:
            time_since = 0.0
        
        # Rolling error rate
        error_rate = self._get_error_rate()
        
        # Current hour
        from datetime import datetime
        hour = datetime.now().hour
        
        return RLState(
            time_since_last=time_since,
            error_rate=error_rate,
            hour_of_day=hour,
        )
    
    def _get_error_rate(self) -> float:
        """Calculate rolling error rate from recent results"""
        if not self.result_window:
            return 0.0
        successes = sum(self.result_window)
        return 1.0 - (successes / len(self.result_window))
    
    def _choose_action(self, state_index: int) -> int:
        """
        ε-greedy action selection.
        
        With probability ε: random action (exploration)
        With probability 1-ε: best known action (exploitation)
        """
        if random.random() < self.epsilon:
            # Explore: random action
            return random.randint(0, NUM_ACTIONS - 1)
        
        # Exploit: best Q-value action
        q_values = self._get_q_values(state_index)
        max_q = max(q_values)
        
        # Break ties randomly
        best_actions = [i for i, q in enumerate(q_values) if q == max_q]
        return random.choice(best_actions)
    
    def _get_q_values(self, state_index: int) -> List[float]:
        """Get Q-values for a state, initializing if needed"""
        if state_index not in self.q_table:
            # Optimistic initialization: slight preference for moderate delays
            # This encourages exploration of non-aggressive strategies early on
            self.q_table[state_index] = [0.0, 0.1, 0.05, 0.0, 0.0, 0.0]
        return self.q_table[state_index]
    
    def _update_q_value(self, state_index: int, action: int, reward: float):
        """
        Q-Learning update rule:
        Q(s,a) ← Q(s,a) + α[r + γ·max_a' Q(s',a') - Q(s,a)]
        """
        # Current Q-value
        q_values = self._get_q_values(state_index)
        old_q = q_values[action]
        
        # Next state's max Q-value
        next_state = self._get_current_state()
        next_index = next_state.to_index()
        next_q_values = self._get_q_values(next_index)
        max_next_q = max(next_q_values)
        
        # Bellman equation
        new_q = old_q + self.alpha * (reward + self.gamma * max_next_q - old_q)
        
        # Update
        q_values[action] = round(new_q, 6)  # Keep precision manageable
        self.q_table[state_index] = q_values
    
    # ==================== PERSISTENCE ====================
    
    def save_policy(self, filepath: Optional[str] = None):
        """Save Q-table and stats to JSON for incremental learning"""
        path = Path(filepath) if filepath else self.policy_file
        
        data = {
            'version': '1.0',
            'q_table': {str(k): v for k, v in self.q_table.items()},
            'epsilon': self.epsilon,
            'total_steps': self._total_steps,
            'total_rewards': round(self._total_rewards, 4),
            'total_success': self._total_success,
            'total_rate_limited': self._total_rate_limited,
            'action_counts': self._action_counts,
            'hyperparameters': {
                'alpha': self.alpha,
                'gamma': self.gamma,
                'epsilon_min': self.epsilon_min,
                'epsilon_decay': self.epsilon_decay,
                'window_size': self.window_size,
            },
        }
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            if self.debug:
                print(f"  [RL] Policy saved: {path}")
        except Exception as e:
            print(f"  [!] Failed to save RL policy: {e}")
    
    def load_policy(self, filepath: Optional[str] = None):
        """Load Q-table from previous session"""
        path = Path(filepath) if filepath else self.policy_file
        
        if not path.exists():
            if self.debug:
                print(f"  [RL] No existing policy found, starting fresh")
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Restore Q-table
            self.q_table = {int(k): v for k, v in data.get('q_table', {}).items()}
            
            # Restore training state
            self.epsilon = data.get('epsilon', self.epsilon)
            self._total_steps = data.get('total_steps', 0)
            self._total_rewards = data.get('total_rewards', 0.0)
            self._total_success = data.get('total_success', 0)
            self._total_rate_limited = data.get('total_rate_limited', 0)
            self._action_counts = data.get('action_counts', [0] * NUM_ACTIONS)
            
            states_loaded = sum(1 for v in self.q_table.values() if any(q != 0 for q in v))
            print(f"  [+] RL policy loaded: {states_loaded} states, "
                  f"{self._total_steps} steps, ε={self.epsilon:.4f}")
            
        except Exception as e:
            print(f"  [!] Failed to load RL policy: {e}")
    
    # ==================== ANALYSIS ====================
    
    def get_learned_strategy(self) -> Dict[str, str]:
        """Analyze what the agent has learned"""
        strategy = {}
        action_labels = ["agresif(1-2s)", "normal(2-4s)", "cautious(4-8s)",
                         "safe(8-15s)", "conservative(15-30s)", "ultra-safe(30-60s)"]
        
        # Best action per error rate level
        for e_idx, e_threshold in enumerate(ERROR_RATE_BINS):
            if e_idx < len(ERROR_RATE_BINS) - 1:
                e_label = f"error_{int(e_threshold*100)}-{int(ERROR_RATE_BINS[e_idx+1]*100)}%"
            else:
                e_label = f"error_{int(e_threshold*100)}%+"
            
            # Average best action across all time/hour bins
            actions = []
            for t_idx in range(NUM_TIME_BINS):
                for h_idx in range(NUM_HOUR_BINS):
                    state_idx = t_idx * NUM_ERROR_BINS * NUM_HOUR_BINS + e_idx * NUM_HOUR_BINS + h_idx
                    if state_idx in self.q_table:
                        best = self.q_table[state_idx].index(max(self.q_table[state_idx]))
                        actions.append(best)
            
            if actions:
                from collections import Counter
                most_common = Counter(actions).most_common(1)[0][0]
                strategy[e_label] = action_labels[most_common]
            else:
                strategy[e_label] = "unexplored"
        
        return strategy
    
    def print_learned_strategy(self):
        """Print what the agent has learned in a readable format"""
        strategy = self.get_learned_strategy()
        
        print("\n  🧠 Learned Strategy:")
        print("  " + "-" * 45)
        for condition, action in strategy.items():
            print(f"  {condition:<25} → {action}")
        print("  " + "-" * 45)
