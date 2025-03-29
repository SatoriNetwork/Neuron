import gym
import numpy as np
from gym import spaces

class NChainEnv(gym.Env):
    """
    Replicates the classic NChain-v0 environment:
      - We have a chain of n states (0..n-1).
      - Two actions: 0="back" (move to state 0), 1="forward" (move ahead by 1).
      - Small reward = 0 if not at end; large reward if we manage to move forward from the last state (which loops us to state 0).
    """
    def __init__(self, n=5, small_reward=0, large_reward=10):
        super().__init__()
        self.n = n
        self.small = small_reward
        self.large = large_reward

        # The state is an integer in [0, n-1]
        self.observation_space = spaces.Discrete(n)
        # The action space is discrete(2): 0=back, 1=forward
        self.action_space = spaces.Discrete(2)

        self.state = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.state = 0
        return self.state

    def step(self, action):
        # action=0 => go back to state 0 from anywhere
        # action=1 => move forward by 1, wrapping from n-1 to 0
        if action == 0:
            self.state = 0
            reward = self.small
        else:
            # forward
            if self.state == self.n - 1:
                # from last state to 0 => large reward
                reward = self.large
                self.state = 0
            else:
                reward = self.small
                self.state += 1

        done = False  # NChain typically doesn't have a done condition (unless you define a max step)
        info = {}
        return self.state, reward, done, info
