'''
includes preferred prior states
'''

import numpy as np

class NChainActiveInferenceAgent:
    def __init__(self, n_states=5, n_actions=2, sigma=0.5, lr=0.1, alpha=0.1):
        """
        :param n_states: Number of hidden states in NChain env.
        :param n_actions: Action space size (2 in typical NChain).
        :param sigma: Noise std-dev for observation model p(x|z).
        :param lr: Learning rate for updating transition/observation estimates.
        :param alpha: Strength of preference for "connected" states in log_prior.
        """
        # (1) Transition model T[s, a, s_next]
        self.T = np.ones((n_states, n_actions, n_states)) / n_states  # uniform init

        # (2) Observation model: R[s] ~ expected reward if in state s
        self.R = np.zeros(n_states)

        # (3) Posterior belief over states as log-probs
        self.phi = np.zeros(n_states)  # log(prob) => uniform init

        # (4) Connectivity measure for each state. We'll update this after each transition update.
        self.connectivity = np.zeros(n_states)

        self.n_states = n_states
        self.n_actions = n_actions
        self.sigma = sigma
        self.lr = lr
        self.alpha = alpha

        # Initialize connectivity once
        self.update_connectivity()

    def update_transition_model(self, s_old, a, s_new):
        """
        Simple incremental update of T[s_old,a,:], then re-normalize.
        Then recalc connectivity to incorporate the new transition info.
        """
        self.T[s_old, a, :] *= (1 - self.lr)
        self.T[s_old, a, s_new] += self.lr
        self.T[s_old, a, :] /= np.sum(self.T[s_old, a, :])

        # Recalculate connectivity
        self.update_connectivity()

    def update_observation_model(self, s, reward):
        """
        Update R[s] to reflect new data about the reward in that state.
        """
        self.R[s] = self.R[s] + self.lr*(reward - self.R[s])

    def update_connectivity(self):
        """
        For each state s, measure how many distinct next-states are reachable
        (with non-trivial probability) across all actions.

        Example measure:
          connectivity[s] = sum_{a} [# of next-states with T[s,a,s'] > threshold]

        A higher connectivity[s] => state s can lead to more diverse future states.
        We use a threshold to avoid counting tiny probabilities as distinct transitions.
        """
        threshold = 0.01
        conn = np.zeros(self.n_states)
        for s in range(self.n_states):
            count_s = 0
            for a in range(self.n_actions):
                # number of next states w prob above threshold
                count_s += np.sum(self.T[s, a, :] > threshold)
            conn[s] = count_s
        self.connectivity = conn

    def log_prior_z(self):
        """
        Incorporate connectivity into the prior.
        The bigger connectivity[s], the higher we want the prior log-prob.

        log_prior[s] = alpha * connectivity[s].
        """
        return self.alpha * self.connectivity

    def log_likelihood_x_given_z(self, x):
        """
        p(x|z) = Normal( R[s], sigma^2 ), so log-likelihood for each s is:
            -0.5 * ((x - R[s])^2 / sigma^2).
        """
        means = self.R
        return -0.5 * ((x - means)**2) / (self.sigma**2)

    def posterior_inference(self, x):
        """
        Update self.phi given a new observation x, multiple coordinate ascent steps.
        phi <- argmax( sum_z q(z)[log p(x,z) - log q(z)] ), simplified here.
        We'll do a direct 'posterior ~ prior * likelihood' approach, ignoring transitions for now.
        """
        for _ in range(3):  # do 3 steps
            log_lik = self.log_likelihood_x_given_z(x)
            log_pri = self.log_prior_z()

            log_posterior_unnorm = log_pri + log_lik
            # normalize:
            max_val = np.max(log_posterior_unnorm)
            log_posterior_unnorm -= max_val
            posterior_unnorm = np.exp(log_posterior_unnorm)
            posterior_unnorm /= np.sum(posterior_unnorm)
            self.phi = np.log(posterior_unnorm + 1e-12)

    def choose_action(self):
        """
        One-step look-ahead: for each action a,
          next_state_dist = sum_{z in states} q(z) * T[z,a,:]
          predicted_reward = sum_{s'} next_state_dist[s'] * R[s']
        Pick the action with highest predicted_reward.
        """
        curr_belief = np.exp(self.phi)
        best_a = 0
        best_value = float('-inf')

        for a in range(self.n_actions):
            # predicted next-state distribution
            next_state_dist = curr_belief @ self.T[:, a, :]
            # predicted reward
            predicted_reward = np.sum(next_state_dist * self.R)
            if predicted_reward > best_value:
                best_value = predicted_reward
                best_a = a

        return best_a
