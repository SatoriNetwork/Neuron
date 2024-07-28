# Satori

Decentralized AI. Future Prediction.

Satori makes knowledge of the future freely available to everyone as a public good.

## Brief High level Overview of the Project

When a new Satori Neuron comes online, the Satori Network assigns the Satori Neuron data stream(s) to subscribe to. The Satori Neuron watches the assigned data streams and learns to anticipate their patterns. It does this by virtue of a continually running internal Satori AI Engine which builds models and searches correlated data streams for patterns. Overtime, on average it gets better and better at predicting the future of the streams which it has been assigned. Every time it gets a new observation on a datastream it was assigned it publishes a prediction that data stream's future.

In short, the network watches everything in the real world that people find valuable, and predicts the future of it. See satorinet.io for more high level overview explanations.

## The Code

The SatoriNeuron repository is the Miner. It houses the Satori AI Engine, a User Interface, an interface to disk, an interface to the Satori Network, and an interface to the blockchain through the SatoriWallet library. Most of the logic of the project lies in the SatoriNeuron repo, or it's associated libraries. For security reasons the Satori Server code is not publicly available.

### Current State

Satori in the final stages of its initial, prototypical development phase. An alpha release occurred on January 1st 2024. Satori entered Beta by March of 2024 and the official mainnet launch is scheduled for July 1st 2024.

### How to get involved

Review the code, feel free to submit pull requests, review the issues for things that need to be done.
Feel free to tackle any of these issues or make any improvement you can see using pull requests. You'll notice that the entry point is currently in satorineuron/web/app.py

#### Testing

We need a test suite. It's amazing we've made it this far without one.

#### Architecture

We'd like to make the code more amenable to new eyes in general.

We'd also like to extract the engine out of the miner software so it's it's own running service.

We'd also like to extract the api's into their own libraries.

#### The Engine

The Engine will always need continual improvement.

A recommender system must be instantiated for node-to-node communication.

#### Connection with the Satori Network

Integrate the Streamr network or other open pubsub solutions.

The underlying DLT (blockchain) has not been designed.

### Social

- <https://satorinet.io>
- <https://discord.gg/jjSp4Wk2qy>
- <https://twitter.com/Satorinetio>
- <https://www.reddit.com/r/SatoriNetwork>
- <https://www.linkedin.com/company/satorinet/>


### Development Setup:

VSCode plugins: Dev Containers (WSL on Windows)
clone local Neuron repo, make sure set to correct branch
https://github.com/SatoriNetwork/Neuron.git
in VSCode new window:
(bottom left, Open Remote Window) Open Folder in Container...
pick local Neuron repo