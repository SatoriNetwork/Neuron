import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

class TransitionModel(nn.Module):
    def __init__(self, n_states, n_actions, hidden_dim=16):
        super().__init__()
        # We'll one-hot the (state,action) inputs, so input size = n_states + n_actions
        self.linear1 = nn.Linear(n_states + n_actions, hidden_dim)
        self.linear2 = nn.Linear(hidden_dim, n_states)  # outputs logits for next-state distribution

    def forward(self, state_onehot, action_onehot):
        x = torch.cat([state_onehot, action_onehot], dim=-1)
        x = torch.relu(self.linear1(x))
        logits = self.linear2(x)
        return logits  # shape: [batch_size, n_states]

class RewardModel(nn.Module):
    def __init__(self, n_states, hidden_dim=16):
        super().__init__()
        # We'll one-hot the state, output a scalar predicted reward
        self.linear1 = nn.Linear(n_states, hidden_dim)
        self.linear2 = nn.Linear(hidden_dim, 1)

    def forward(self, state_onehot):
        x = torch.relu(self.linear1(state_onehot))
        r = self.linear2(x)  # shape: [batch_size, 1]
        return r.squeeze(-1) # shape: [batch_size]


def one_hot(index, size):
    v = np.zeros(size, dtype=np.float32)
    v[index] = 1.0
    return v

class NChainActiveInferenceAgentParam:
    """
    A version of the agent that uses small neural networks to approximate:
      1) The transition model p(z_{t+1} | z_t, a_t)
      2) The reward model E[r | z]
    Instead of storing T[s,a,s'] in a table and R[s] in a simple array.
    """
    def __init__(
        self,
        n_states=5,
        n_actions=2,
        sigma=0.5,
        alpha=0.1,
        lr=1e-2,
        hidden_dim=16
    ):
        self.n_states = n_states
        self.n_actions = n_actions
        self.sigma = sigma
        self.alpha = alpha

        # Posterior belief over states as log-probs
        self.phi = np.zeros(n_states)  # log(prob) => uniform init

        # Connectivity measure (we'll approximate differently or skip for now)
        self.connectivity = np.zeros(n_states)

        # Parametric models
        self.transition_model = TransitionModel(n_states, n_actions, hidden_dim)
        self.reward_model = RewardModel(n_states, hidden_dim)

        # We'll use separate optimizers for each
        self.optimizer_T = optim.Adam(self.transition_model.parameters(), lr=lr)
        self.optimizer_R = optim.Adam(self.reward_model.parameters(), lr=lr)

    def log_prior_z(self):
        # For now, do a simple connectivity-based prior = alpha * connectivity[s]
        # We'll pretend we have a method to get connectivity, or skip it.
        return self.alpha * self.connectivity

    def log_likelihood_x_given_z(self, x):
        # p(x|z) ~ Normal( reward(z), sigma^2 )
        # We'll need to query the reward model for each state.
        # shape: (n_states,)
        with torch.no_grad():
            all_states_oh = torch.eye(self.n_states)
            # predicted reward for each state:
            pred_r = self.reward_model(all_states_oh)  # shape: [n_states]
            pred_r_np = pred_r.detach().numpy()
        # compute log-likelihood
        return -0.5 * ((x - pred_r_np) ** 2) / (self.sigma ** 2)

    def posterior_inference(self, x, steps=3):
        for _ in range(steps):
            log_lik = self.log_likelihood_x_given_z(x)
            log_pri = self.log_prior_z()
            log_posterior_unnorm = log_pri + log_lik

            max_val = np.max(log_posterior_unnorm)
            log_posterior_unnorm -= max_val
            posterior_unnorm = np.exp(log_posterior_unnorm)
            posterior_unnorm /= np.sum(posterior_unnorm)
            self.phi = np.log(posterior_unnorm + 1e-12)

    def choose_action(self):
        # one-step look-ahead as before
        curr_belief = np.exp(self.phi)
        best_a = 0
        best_value = -1e9

        with torch.no_grad():
            # shape: [n_states, n_actions, n_states]
            # but we'll have to compute for each state+action individually.

            # step 1: for each state s in 0..n_states, for each action a
            # we get T[s,a,:] => distribution over next states

            # We'll store predicted next-state distribution in a 2D array: next_dist[s,a, s']
            next_dist = np.zeros((self.n_states, self.n_actions, self.n_states), dtype=np.float32)

            # also store predicted rewards for each state
            all_states_oh = torch.eye(self.n_states)
            pred_reward = self.reward_model(all_states_oh).detach().numpy()  # shape: [n_states]

            for s in range(self.n_states):
                s_oh = torch.from_numpy(one_hot(s, self.n_states)).unsqueeze(0)
                for a in range(self.n_actions):
                    a_oh = torch.from_numpy(one_hot(a, self.n_actions)).unsqueeze(0)

                    logits = self.transition_model(s_oh, a_oh)  # shape: [1, n_states]
                    probs = torch.softmax(logits, dim=-1).numpy().reshape(-1)
                    next_dist[s, a, :] = probs

            # now compute the expected next-state distribution given our current belief
            # for each action a:
            for a in range(self.n_actions):
                # next_state_dist = sum_{z} q(z) * T[z,a,:]
                sum_dist = np.zeros(self.n_states)
                for s in range(self.n_states):
                    sum_dist += curr_belief[s] * next_dist[s, a, :]

                # predicted reward = sum_{s'} sum_dist[s'] * reward_model[s']
                predicted_r = np.sum(sum_dist * pred_reward)

                if predicted_r > best_value:
                    best_value = predicted_r
                    best_a = a

        return best_a

    def update_transition_model(self, s_old, a, s_new):
        """
        We'll do a gradient step to make transition_model(s_old, a) => s_new distribution.
        That means we define cross-entropy between predicted distribution and one-hot of s_new.
        """
        self.optimizer_T.zero_grad()

        s_old_oh = torch.from_numpy(one_hot(s_old, self.n_states)).unsqueeze(0)
        a_oh = torch.from_numpy(one_hot(a, self.n_actions)).unsqueeze(0)
        logits = self.transition_model(s_old_oh, a_oh)  # shape: [1, n_states]

        # target distribution is one-hot s_new
        target = torch.from_numpy(one_hot(s_new, self.n_states)).unsqueeze(0)

        loss = nn.CrossEntropyLoss()(logits, torch.argmax(target, dim=-1))
        loss.backward()
        self.optimizer_T.step()

        # optionally we could try to recalc connectivity if we want to keep using it:
        self.update_connectivity()

    def update_observation_model(self, s, reward):
        """
        We'll do a gradient step to push reward_model(s) => observed reward.
        We'll use an MSE criterion.
        """
        self.optimizer_R.zero_grad()
        s_oh = torch.from_numpy(one_hot(s, self.n_states)).unsqueeze(0)
        pred_r = self.reward_model(s_oh)  # shape: [1]
        target = torch.tensor([reward], dtype=torch.float32)
        loss = (pred_r - target)**2
        loss.backward()
        self.optimizer_R.step()

    def update_connectivity(self):
        """
        We can approximate connectivity by sampling or just do a forward pass across (s,a) pairs.
        connectivity[s] = number_of_s' with T[s,a,s'] > threshold, averaged over a?
        """
        threshold = 0.01
        conn = np.zeros(self.n_states)

        with torch.no_grad():
            all_states_oh = torch.eye(self.n_states)
            for s in range(self.n_states):
                s_oh = all_states_oh[s].unsqueeze(0)
                count_s = 0
                for a in range(self.n_actions):
                    a_oh = torch.from_numpy(one_hot(a, self.n_actions)).unsqueeze(0)
                    logits = self.transition_model(s_oh, a_oh)  # [1, n_states]
                    probs = torch.softmax(logits, dim=-1).numpy().reshape(-1)
                    count_s += np.sum(probs > threshold)
                conn[s] = count_s
        self.connectivity = conn
