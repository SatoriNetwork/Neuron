'''
agent + free engery principle
'''
import gym
import numpy as np

import playground.energy.nchain1 as nchain

class NChainActiveInferenceAgent:
    def __init__(self, n_states=5, n_actions=2, sigma=0.5, lr=0.1):
        """
        :param n_states: Number of hidden states in NChain env ( default=5 in NChain-v0 ).
        :param n_actions: Usually 2 actions in NChain-v0 (0=back,1=forward).
        :param sigma: Noise std-dev for observation model p(x|z).
        :param lr: Learning rate for updating transition/observation estimates.
        """

        # We'll keep track of:
        # (1) T[s, a, s_next] ~ p(z_{t+1} = s_next | z_t = s, a_t = a)
        self.T = np.ones((n_states, n_actions, n_states)) / n_states  # start uniform

        # (2) R[s] ~ expected reward if the environment is in state s
        self.R = np.zeros(n_states)

        # (3) phi[s] ~ approximate log probability of being in state s
        # We'll keep them as logs so we can exponentiate to get a normalized distribution.
        self.phi = np.zeros(n_states)  # log probs -> initially uniform

        self.n_states = n_states
        self.n_actions = n_actions
        self.sigma = sigma
        self.lr = lr

    def update_transition_model(self, s_old, a, s_new):
        """
        We'll do a simple incremental update:
          T[s_old, a, :] is updated to reflect that s_new was the next state.
        Because we don't truly observe s_old and s_new, this is a hack (in real partial
        observability, we wouldn't see the states at all). For the sake of the example,
        we cheat a bit by letting Gym show us the real states.

        If we wanted *true* partial observability, we'd track beliefs about s_old, s_new
        and update T in a Bayesian way. But let's keep it simple.
        """
        # Pseudocount approach
        self.T[s_old, a, :] *= (1 - self.lr)
        self.T[s_old, a, s_new] += self.lr
        # Normalize so it sums to 1
        self.T[s_old, a, :] /= np.sum(self.T[s_old, a, :])

    def update_observation_model(self, s, reward):
        """
        Update R[s] to reflect new data about the reward. Simple incremental approach:
          R[s] = R[s] + lr*( (reward) - R[s] )
        """
        self.R[s] = self.R[s] + self.lr*(reward - self.R[s])

    def log_prior_z(self):
        """
        If we want a uniform prior over states, log p(z) = const => 0 (ignored).
        Alternatively, we could have preferences or 'survival states' built in here.
        For now, we just return 0 for all states => uniform prior.
        """
        return np.zeros(self.n_states)

    def log_likelihood_x_given_z(self, x):
        """
        We treat x = observed reward as coming from Normal(R[s], sigma^2).
        Return an array of log-likelihood for each state s.
        """
        # vector of means
        means = self.R
        # log-likelihood for each state s: -0.5 * ((x - means[s])^2 / sigma^2)
        return -0.5 * ((x - means)**2) / (self.sigma**2)

    def posterior_inference(self, x):
        """
        Update self.phi (which is log of the posterior) given new observation x, using multiple steps:
          phi <- arg min FreeEnergy(phi) = arg max E_q[ log p(x,z) - log q(z) ]
        Since we do a super-simplified approach, we'll do coordinate ascent in log space,
        ignoring transitions for the moment (or we incorporate them if we store the last action).
        """
        # We'll do a few gradient steps on self.phi:
        for _ in range(3):  # do 3 steps
            log_lik = self.log_likelihood_x_given_z(x)
            # posterior ~ prior + log_lik, ignoring transition from previous step for this simple example
            # phi_new[s] = (some function of) self.log_prior_z()[s] + log_lik[s] - self.phi[s] ...
            # But let's do a direct assignment ignoring old phi to keep it simpler:
            log_posterior_unnorm = self.log_prior_z() + log_lik
            # We can do a "soft update" from old phi to new, or just set phi = log_posterior_unnorm:
            # Then we normalize:
            max_val = np.max(log_posterior_unnorm)  # for numerical stability
            log_posterior_unnorm -= max_val
            posterior_unnorm = np.exp(log_posterior_unnorm)
            posterior_unnorm /= np.sum(posterior_unnorm)
            # convert back to log
            self.phi = np.log(posterior_unnorm + 1e-12)

    def choose_action(self):
        """
        We pick the action that yields the lowest *expected free energy* for the next step.
        That means we consider for each a:
          E_{z ~ posterior} [ E_{z' ~ T[z,a]} [ F(...) ] ]
        In this toy, let's define next-step free energy as simply:
          - the expected log-likelihood of future reward + some prior preference for states
        This is naive, but shows the structure.
        We'll sample a single next state from T, or do a small sum over all next states,
        approximate next reward as R[z'].

        Then pick the action that yields the highest predicted reward, or equivalently
        the lowest surprise, to keep it simpler.
        """

        # current belief distribution
        curr_belief = np.exp(self.phi)

        best_a = 0
        best_value = -9999999

        for a in range(self.n_actions):
            # predicted distribution over next states:
            # sum_{z} p(z) * T[z,a,:]
            next_state_dist = curr_belief @ self.T[:, a, :]  # shape=(n_states,)

            # predicted mean reward = sum_{z'} next_state_dist[z'] * R[z']
            predicted_reward = np.sum(next_state_dist * self.R)

            # we pick the action with highest predicted_reward
            if predicted_reward > best_value:
                best_value = predicted_reward
                best_a = a

        return best_a

def run_nchain_free_energy(n_episodes=5, max_steps=20):
    env = nchain.NChainEnv(n=5, small_reward=0, large_reward=10)
    agent = NChainActiveInferenceAgent(n_states=5, n_actions=2, sigma=1.0, lr=0.1)

    for ep in range(n_episodes):
        s = env.reset()
        agent.phi = np.zeros(agent.n_states)
        total_reward = 0
        for t in range(max_steps):
            a = agent.choose_action()
            s_next, r, done, info = env.step(a)
            total_reward += r

            # Since we have direct access to s, s_next, we do the "cheat" update:
            agent.update_transition_model(s, a, s_next)
            agent.update_observation_model(s_next, r)

            # posterior update
            agent.posterior_inference(r)

            s = s_next
            if done:
                break

        print(f"Episode={ep+1}, total_reward={total_reward}, final_belief={np.exp(agent.phi)}")


    env.close()

if __name__ == "__main__":
    run_nchain_free_energy()
