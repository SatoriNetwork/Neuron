import numpy as np

from nchain1 import NChainEnv
from free2 import NChainActiveInferenceAgent

def run_nchain_free_energy(n_episodes=5, max_steps=20):
    env = NChainEnv(n=5, small_reward=0, large_reward=10)

    # Note the alpha=0.1 or so. You can tweak it to see how strongly
    # connectivity shapes the agent's priors.
    agent = NChainActiveInferenceAgent(n_states=5, n_actions=2, sigma=1.0, lr=0.1, alpha=0.1)

    for ep in range(n_episodes):
        s = env.reset()
        agent.phi = np.zeros(agent.n_states)  # reset belief to uniform
        total_reward = 0
        for t in range(max_steps):
            # agent picks action
            a = agent.choose_action()

            # environment step
            s_next, r, done, info = env.step(a)
            total_reward += r

            # update transitions + observation model
            agent.update_transition_model(s, a, s_next)
            agent.update_observation_model(s_next, r)

            # posterior update given the new "observation" (which is the reward here)
            agent.posterior_inference(r)

            s = s_next
            if done:
                break

        # final connectivity for debug
        print(f"Episode={ep+1}, total_reward={total_reward}, final_belief={np.exp(agent.phi)}, connectivity={agent.connectivity}")
    env.close()


if __name__ == "__main__":
    run_nchain_free_energy()
