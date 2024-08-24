# todo by inititive

Improve Infrastructure
  Make tradable wrapped version of token
    Krishna - Research, build, and test ERC20 version token
    Krishna - Research, build, and test wrapped token contract
    Krishna - Research, build, and test interactions with uniswap, metamask, etc
    Jordan - build bridge for managing Evrmore chain and interacting with wrapped token contract
      design requirement: for full auditability, specify evr txid and polygon tx id cross chain
      create (HD?) wallet to hold wrapped token on Evrmore.
      bridge monitors all transactions to that address, extracts polygon address from metadata
      bridge interacts with wrapping contract identifying evr txid when minting to polygon address
      bridge monitors wrapped contract activity looking for when token is burned with Evrmore address specified
      bridge unlocks burned amount from address, sending it to specified Evrmore address, specifying contract transaction id in metadata
  Modularize Server
    Upgrade database to postgres
    Containerize the database
    Improve scheduler
    Give users better control over datastreams
    Give users ability to use privately
Improve AI Engine
  Improve Engine architecture
    Improve code design
      build adapters for all algorithms
    Modularize with zeroMQ
    Make ensembling process
  Improve AI
    Include other algorithms 
      Chronos pertained model
      TTM, etc
      Large models requiring GPU
    Add ability to access the GPUs to docker image
    Add latent pooling
      develop on hugging face
      implement into then neuron
Decentralization
  Multi-sig mint
  Multi-sig distribution
  Implement competition mining
  Implement consumer mining


todo:
  make neurons pull code separately
  make delegate relationships public
  add ability to delegates (parents) to redirect the payment somewhere else
  add ability to delegates (parents) to see status and activity of their children
  add ability for everyone to see how many other predictors there are in their competitions
