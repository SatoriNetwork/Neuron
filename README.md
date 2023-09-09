# Satori
_The Future Network_

Satori is a blockchain that predicts the future.

It makes knowledge of the future freely available to everyone as a public good.

## Brief Highlevel Overview of the Project

When a new node comes online, the Satori Network assigns the node data stream(s) to subscribe to. The node watches the assigned data streams and learns to anticipate their patterns. It does this by virtue of a continually running internal Satori AI Engine which builds models and searches correlated data streams for patterns. Overtime, on average it gets better and better at predicting the future of the streams which it has been assigned. Everytime it gets a new observation on a datastream it was assigned it publishes a prediction that data stream's future.

In short, the network watches everything in the real world that people find valuable, and predicts the future of it. See satorinet.io for more highlevel overview explanations.

## The Code

The SatoriNeuron repository is the Miner. It houses the Satori AI Engine, a User Interface, an interface to disk, an interface to the Satori Network, and an interface to the blockchain through the SatoriWallet library. Most of the logic of the project lies in the SatoriNeuron repo, or it's associated libraries. For security reasons the Satori Server code is not publically available.

### Current State

Satori in the final stages of its initial, prototypical development phase. An alpha release is anticipated for Q3 of 2023 and Satori will have a soft launch and beta release Q1 of 2024.

### Getting Started

If you want to run the code you can...

0. fork and clone this repo
1. download, install, and run docker
2. you can mount your local code with this command:  
    - `docker run --rm -it --name satorineuron -p 24601:24601 -v c:\repos\Satori\Neuron:/Satori/Neuron --env SATORI_RUN_MODE=prod satorinet/satorineuron:v1 ./start.sh`
    - notice `c:\repos\Satori\Neuron` should be your local path to this repository
    - notice `--env SATORI_RUN_MODE=prod` indicates that it'll talk to the official servers at satorinet.io
    - while  `--env SATORI_RUN_MODE=dockerdev` indicates that it'll talk to locally running servers which we will opensource eventually.

### How to get involved

Review the code, feel free to submit pull requests, review the issues for things that need to be done.
Feel free to tackle any of these issues or make any improvement you can see using pull requests. You'll notice that the entry point is currently in satorineuron/web/app.py

#### Testing

We need a test suite. It's amazing we've made it this far without one.

#### Architeture

We'd like to make the code more ameanable to new eyes in general.

We'd also like to extract the engine out of the miner software so it's it's own running service.

We'd also like to extract the api's into their own libraries.

#### The Engine

The Engine will always need continual improvement.

A recommender system must be instanteated for node-to-node communication.

#### Connection with the Satori Network 

Integrate the Streamr network or other open pubsub solutions.

The underlying DLT (blockchain) has not been designed.

### Social 

- https://satorinet.io
- https://discord.gg/jjSp4Wk2qy
- https://twitter.com/Satorinetio
- https://www.reddit.com/r/SatoriNetwork
- https://www.linkedin.com/company/satorinet/
