Improve Infrastructure:
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

Improve AI Engine
Decentralize


