import random

class TwoClusterEnv:
    """
    We have 8 states: 0..7
      - States 0..3 are cluster A
      - States 4..7 are cluster B
    We have 2 actions: 0 or 1
    If you're in cluster A:
        action=0 => move within A
        action=1 => possibly jump to cluster B if you're near boundary
    and similarly for cluster B -> jump to cluster A if near boundary
    We define a small reward structure just to have something to learn.
    """
    def __init__(self):
        self.n_states = 8
        self.n_actions = 2
        self.state = 0  # start in state 0

    def reset(self):
        self.state = 0
        return self.state

    def step(self, action):
        # We'll define some transitions by hand
        old_state = self.state

        # cluster A = [0,1,2,3], cluster B=[4,5,6,7]
        if self.state in [0,1,2,3]:
            # cluster A
            if action == 0:
                # Move around inside A
                self.state = random.choice([0,1,2,3])
                reward = 0
            else:
                # Possibly jump from boundary state 3 to cluster B
                if self.state == 3:
                    self.state = 4
                    reward = 2  # crossing boundary might yield a reward
                else:
                    # move around in A still
                    self.state = random.choice([0,1,2,3])
                    reward = 0
        else:
            # cluster B
            if action == 0:
                # Move around inside B
                self.state = random.choice([4,5,6,7])
                reward = 1  # maybe slightly different inside B
            else:
                # possibly jump from boundary state 4 to cluster A
                if self.state == 4:
                    self.state = 3
                    reward = 2
                else:
                    # move around in B
                    self.state = random.choice([4,5,6,7])
                    reward = 1

        done = False
        info = {}
        return self.state, reward, done, info

import numpy as np

class MacroPlanner:
    """
    Maintains a coarse model over the macro-states (A or B).
    We'll define A=0, B=1 in macro space.

    - We keep a transition model M[m, a, m_next].
    - We keep a reward model R[m].
    - We do multiple-step lookahead to pick the best macro-action sequence.

    Then we pass that macro-action down to the local policy.
    """
    def __init__(self):
        self.n_macro = 2  # 2 macro-states: A or B
        self.n_actions = 2
        # transition model in macro space
        self.M = np.ones((self.n_macro, self.n_actions, self.n_macro)) / self.n_macro
        # reward for each macro-state
        self.R = np.zeros(self.n_macro)
        # We'll keep a distribution over which macro-state we think we're in
        self.macro_phi = np.array([0.5, 0.5])  # uniform initially

    def update_macro_model(self, macro_old, a, macro_new, reward):
        """Pretend we see transitions in macro space. In practice, you'd infer macro states from fine states."""
        # increment transition counts
        # simplistic incremental update
        self.M[macro_old, a, :] *= 0.99
        self.M[macro_old, a, macro_new] += 0.01
        self.M[macro_old, a, :] /= np.sum(self.M[macro_old, a, :])

        # update reward
        lr = 0.1
        self.R[macro_new] += lr*(reward - self.R[macro_new])

    def posterior_inference(self, reward):
        """If we want, we can do p(macro| reward). For now, do nothing or keep it simple."""
        pass

    def pick_macro_action_plan(self, horizon=2):
        """
        Search the next 'horizon' steps in macro space to pick best macro-action.
        We'll do naive BFS or DFS for a short horizon.
        """
        best_a = 0
        best_value = -1e9

        # current macro belief
        phi = self.macro_phi
        # We'll enumerate all possible action sequences of length up to 'horizon' and pick the best first action
        # Very naive approach
        import itertools
        possible_plans = list(itertools.product(range(self.n_actions), repeat=horizon))

        for plan in possible_plans:
            # let's do a small forward simulation in macro space
            # copy phi
            dist = phi.copy()
            total_expected_reward = 0
            for step_a in plan:
                # next dist = sum_{m} dist[m] * M[m, step_a, :]
                new_dist = np.zeros(self.n_macro)
                for m in range(self.n_macro):
                    new_dist += dist[m] * self.M[m, step_a, :]
                dist = new_dist
                # expected reward = sum_{m} dist[m] * R[m]
                total_expected_reward += np.sum(dist * self.R)
            # compare with best
            if total_expected_reward > best_value:
                best_value = total_expected_reward
                best_a = plan[0]  # pick the first action in plan

        return best_a


class LocalPolicyA:
    """Handles local moves in cluster A (states 0..3)."""
    def pick_action(self, s):
        # If we want to go to boundary state 3, we might do something naive:
        if s < 3:
            return 0  # do an action that moves inside A
        else:
            return 1  # do an action that might cross to B

class LocalPolicyB:
    """Handles local moves in cluster B (states 4..7)."""
    def pick_action(self, s):
        # If we want to stay in B or move to boundary 4, do something naive
        if s > 4:
            return 0
        else:
            return 1

def macro_state_of(s):
    return 0 if s < 4 else 1

def run_hierarchical_agent(n_episodes=10, max_steps=20):
    env = TwoClusterEnv()
    macro_planner = MacroPlanner()
    local_policy_A = LocalPolicyA()
    local_policy_B = LocalPolicyB()

    for ep in range(n_episodes):
        s = env.reset()
        # guess macro-state
        macro_s = macro_state_of(s)
        macro_planner.macro_phi = np.array([0,1])[macro_s == 1].astype(float)  # set to [1,0] or [0,1]

        total_reward = 0
        for t in range(max_steps):
            # 1) macro planner picks a macro-level action plan (just the first step)
            macro_action = macro_planner.pick_macro_action_plan(horizon=2)

            # 2) local policy picks an actual environment action
            if macro_s == 0:
                a = local_policy_A.pick_action(s)
            else:
                a = local_policy_B.pick_action(s)

            # for demonstration, let's override that local action with the macro_action if we want:
            # Actually, let's just do the local action in this example:
            # a = macro_action

            s_next, r, done, info = env.step(a)
            total_reward += r

            # update macro model
            macro_s_next = macro_state_of(s_next)
            macro_planner.update_macro_model(macro_s, macro_action, macro_s_next, r)

            # do any macro-level posterior updates if we had partial observability at macro level
            macro_planner.posterior_inference(r)

            # now update local policies or beliefs if we want
            # ...

            # move on
            s = s_next
            macro_s = macro_s_next
            if done:
                break
        print(f"Episode {ep+1} total_reward={total_reward}")
