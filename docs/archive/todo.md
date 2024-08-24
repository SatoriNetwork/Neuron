# TODO List

- [x] remove row number cache design from disk, add in regular old cache design
DONE move scheduler up to the engine level, cycle through all datasets.
DONE make sure we clear out any bad data at all times.
DONE move the cache out of the topic, and up to the startDag singleton, then make everything pull from the same cache, such DONE as the relay stuff, rendezvous stuff, and engine, anything that uses the Disk object currently.
DONE make better use of the async stuff, convert simple timed threads to use it.
DONE make the rendezvous relay server run by default
DONE remove prints and debug logs
DONE remove reto
DONE move the host.py stuff into the runner
DONE recompile test
DONE rebuild the docker containers
DONE research solution on avalanche
DONE fix installer - must make sure to pull the latest version explicitly
DONE fix open browser - before blocking
DONE loop until docker pulls correctly
DONE fix installer - windows doesn't recognize it as safe - sign it.
FINE fix installer - on one computer windows defender flagged it as a "bearfoos" virus, so we have to figure that out. - doesn't happen on more up to date windows machines
DONE fix pause functionality - it's reversed, paused by default I think?
DONE I noticed histories aren't downloading automatically. explore...
DONE fix issue where we can miss some of the raw data stream and we'd never know, except we would because when we ask and it doesn't match our hash we know it's no goood. so we have to ask for the history backwards until we find the missing data. the best solution is to broadcast the hash in the pubsub. then if it looks like the hash is invalid, we know that we missed something. at that point what should we do? when it looks like our dataset is missing something we should? ask for the middle hash, then see if it matches, so on and so forth until we identify the missing one? not sure.
DONE when we broadcast a prediction we need to include time and observationHash too
DONE not saving observations
DONE assign a stream a random time... key it off the name... make the rendezvous connection happen at that time every day
DONE remove ping
DONE still have a connection annoyance,with moontree and checkin and maybe pubsub? but it connects eventually on startup.
DONE rendezvous - early worker timeout
DONE ping solution
DONE add something that fixes data - like when we send a check that verifies the hashes before we send
DONE fix logging - remove debugs
DONE fix logging - add add info about all coming and going
DONE start over if we've never established the root
DONE something broke in responding to requests?
DONE follow newData: save, trigger prediction, save that prediction, publish
DONE we should show predictions on the dashboard
DONE release alpha Jan 1

---

DONE have it make a prediction and broadcast it on startup
DONE show the latest prediction on the UI
DONE loop in runner
DONE central - remove sanction all endpoint
DONE central - only sanctioned streams show up on website
DONE central - create scheduling singleton
DONE central - add payout query logic (no competition yet)
DONE central - add call to payout logic
DONE central - automated straight up removal of inactive nodes (1 month)
DONE central - test straight up removal of inactive neurons (that it only deletes them)
DONE central - test the mining queries
DONE central - make an average cadence query
DONE central - automated desanction
DONE central - automated resanction (needs to be sanctioned first)
DONE central - add view tables to the database manually
DONE central - show when the predicton is implicitly targeting, instead of created
DONE central - add prediction target time formatting, human readable and client timezone
DONE central - test prediction target time formatting
GOOD central - fix search pulling predictions too far in past
DONE installer - make an installer for linux
DONE installer - test linux installer
DONE neuron - take out ipfs calls
DONE neuron - take out ipfs startup
DONE neuron - take out ipfs env var from run command, put in image
DONE neuron - add csv upload for datastreams visual to nueron ui
DONE neuron - add csv upload accept to nueron server
DONE neuron - process csv upload
DONE neuron - test csv upload process
DONE neuron - test seeding datastreams with csv
DONE neuron - give user feedback on processing
DONE neuron - add export csv of existing datastreams
DONE neuron - what happens if we add data to history without hash? does it hash it, throw it away? throw everything after it away?
DONE neuron - allow history to be added without hashes and have it automatically hash it.
DONE neuron - add ability to upload updates to history on relay streams
DONE neuron - add export csv of history - just grab the file from data
DONE neuron - add placeholder for voting
DONE wallet - convert ravencoin wallet to evrmore wallet
DONE lib - use new evrmore stuff as wallet
DONE neuron - change wallet yaml to include both
DONE neuron - create transaction functioanlity
DONE neuron - clean up the wallet code it is horrendous
DONE neuron - finish wallet UI for creating a transaction
DONE neuron - finish wallet UI for history of transactions
DONE neuron - flash feedback from trasnaction attempt
DONE neuron - correct address in transaction create code
DONE neuron - test transaction create code (address correct?)
DONE neuron - create send all
DONE neuron - create send all checkbox on UI
DONE neuron - test send all
DONE wallet - add op_return memos for tracking payment types
DONE central - add python-evrmorelib to the image
DONE central - add issuance logic to server
DONE central - test issuance logic to server with test token
DONE neuron - build an are you sure alert for any delete activity.
DONE neuron - does not always ask for server time first. (lib/server/server.py register_stream)
DONE neuron - fix the upload streams - shouldn't restart entire service.
DONE neuron - make the relay stream smarter about when it relays the next data on startup: relay at the next interval of the specified cadence per stream.
DONE neuron - make relay streams just relative to unix epoc time. simple.
DONE neuron - cadence messed up if you put in 0
DONE neuron - relay data stream on demand pull button since now we do it on the correct cadence.
DONE neuron - relay data stream fix
DONE neuron - limit relay streams? port limitations, threads, etc. 100? 50? 25? 25 for now
DONE neuron - relay data stream indicator of not working or working
DONE neuron - relay data stream indicator could be red if the history is longer in the past than cadence should allow? or yellow if that's the case but you just started the neuron. otherwise green.
DONE neuron - fix for dark mode
DONE neuron - build in a "vault" placeholders
DONE neuron - rebuild image
DONE central - restart server with all these changes
DONE installer - fix linux printouts
DONE installer - rebuild
DONE installer - add mac installer
DONE neuron - the show the current satori version and build on the UI somewhere
DONE central - add mac installer to webiste
DONE neuron - respect offset: now that we are doing the cadence by the proper utc time, we can use the offset as intended.
DONE neuron - fix offset issues: if you add a data stream with an offset and save it, it works fine. But when you enter its edit mode and try to remove or change the offset, the system freezes. You have to refresh the page, but the offset remains unchanged.
DONE neuron - debug - large number of streams takes a long time to open cache - why? - beucase it's rehashing them? or no? 50 + streams takes 10-30 minutes
DONE rendezvous - deubg - large number of streams unable to establish connection - shouldn't that be done one at a time anyway? no?
DONE neuron - debug peer to peer connections
DONE neuron - enforce 50 relays limit
DONE neuron - don't request if you publish
DONE neuron - rebuild neuron
DONE central - a neuron shouldn't subscribe to it's own datastreams by default.
DONE central - clean up database for test payouts
DONE central - test pubsub and rendezvous after we remove own subscriptions.
DONE neuron - make wallet reference test token in wallet page
DONE neuron - create main and test token link on navbar
DONE neuron - create make wallet page adaptable to main or test
DONE neuron - create main wallet as well as test wallet on startup
DONE neuron - setup 3 more neurons
DONE neuron - seed with datastreams with histories
DONE central - fix scheduler to run in it's own process (gunicorn runs multiple workers, so even though the object is singleton it runs more than once)
DONE central - rendezvous, pubsub, server: anything behind gunicorn not logging right.
DONE central - implement alternative logging solution
DONE central - needs a wallet on server
DONE central - add test value to server wallet
DONE neuron - rebuild images for new package
DONE neuron - build in a "vault"
DONE vault - allow wallet to be encrypted and decrypted
DONE vault - make endpoint for opening vault
DONE vault - make endpoint for vault
DONE vault - if they navigate away from the vault forget the vault
DOEN vault - add wallet template to vault template
DONE vault - add wallet code to vault endpoint
DONE vault - creation process with encrypting with a password of their own
DONE vault - add vault page
DONE central - test:
DONE central - does the nightly process run automatically?
DONE central - do inactive neurons get removed nightly?
DONE central - get a list of inactive neurons, run nightly process, see if they're gone
DONE central - do streams, subscription, etc, attached to missing neurons get removed?
DONE central - get a list of streams pulished by above neurons, run nightly process, see if they're gone
DONE central - do inactive streams get unsanctioned nightly?
DONE central - found ksm datastream with no observations, run the nightly schedule process, verify ksm no longer sanctioned
DONE central - do reactivated streams get resanctioned automatically?
DONE central - found kws neuron, start it, run the nightly schedule process, verify ksm no longer sanctioned
DONE central - do neurons get distributions if they published predictions on a sanctioned datastream within the last 24 hours? are they accurate?
DONE central - we don't keep history beyond a day so query for checking if relay or prediction streams had activity always fails. - we need to implement the history table.
DONE central - add History table
DONE central - verify observations are saved to history table
DONE central - fix hisotry table
DONE central - use history table in mining queries and verify

-- BETA (test coin) target --

DONE neuron - test send to and from vault
DONE neuron - cleanup wallet ui

DONE neuron - autosend to vault:
DONE neuron - add choice to UI
DONE neuron - add form and endpoint
DONE neuron - add entry to config file
DONE neuron - config entry to include vault address, vault pubkey, and signature
DONE neuron - signature involves (decrypted) address

DONE atomic swaps:
DONE neuron - if they have no currency, generate a transaction without currency input but using 1 SATORI as the sending fee: generate an output without an address, send to server.
DONE central - take transaction and supply sufficient RVN fee in inputs, and add output with own address and 1 SATORI.
DONE neuron - test
DONE neuron - fix the signing for partial transactions, redo the whole thing.
DONE central - test
DONE neuron - test send all satori transactions
DONE neuron - fix send all satori transactions
DONE central - check addresses too
DONE central - test again
DONE central - problem - unable to create and save subscriptions ever since database update
DONE central - add github link to website
DONE central - add resources links to website
DONE central - change donation link to btc, eth, rvn, evr addresses
DONE central - problem - database is locked while distributions run...
DONE neuron - allow people to specify an alias for their wallet.
DONE central - allow people to specify an alias for their wallet.
DONE central - I want the scheduler to continually update the time file so no other scheduler can start as a worker later
DONE neuron - autosecure - add optional minimum wallet account balance
DONE neuron - autosecure - send even multiparty transaction too
DONE central - clear out scheduler log on cycle
DONE neuron - vault - fix decrypting words
DONE neuron - vault - fix encrypting entropy
DONE vote - create:
DONE neuron - create voting page with form and explanation
DONE neuron - create communication with network and server to specify preference
DONE neuron - create communication with network and server to get community vote
DONE central - sql create table
DONE central - sql create orm
DONE central - create endpoints
DONE central - add balances table
DONE central - add balances orm
DONE central - add balances process
DONE central - fix - publications not working
DONE neuron - fix - subscriptions not being turned into anything...
DONE neuron - fix - voting page is broken
DONE neuron - fix - checkin - something wrong with subscriptions and publications
DONE central - either move sanction out it it's own table, rebuilding streams or update in bulk with a temporary table (probably ideal)
DONE central - add manifest queries
DONE central - add sanction queries
DONE neuron - fix self.disk issues, sometimes we don't have stream data we should...?
DONE central - consider turning observation table into a view on history... (this may have been a bad idea: it slows down our ability to determine if a stream is active more than expected).
DONE central - make it a soft delete - one reason we need it is streams can be published by others
DONE central - modify queries to respect soft delete.
DONE vault - allow for voting with vaulted coins and wallet coins
DONE central - make a history table and test the history table
DONE central - make sure server is saving history of observations
DONE vault - show words on page as well as private key
DONE wallet - show words on page as well as private key
DONE neuron - make the wallet value on dashboard and wallet pages and vault update more realtime
DONE neuron - could just be calling get just for the balance right after broadcasting, and right after distributions are scheduled to go out daily.
DONE central - fix - call to database to get predictions is broken
DONE central - make separate observation table instead of using a view on history (needs testing)
DONE central - make the Observation object again
DONE central - save new observations to the observations table using upsert
DONE central - remove history view
DONE neuron - vault - require password twice on first setup
DONE central - better customer experience

DONE neuron - streamline the ui model updates more by pushing individual model updates
DONE neuron - and interpreting individual model updates on the ui
DONE neuron - fix saving of predictions locally
DONE neuron - fix list of predictions - not pulling correctly to show on the UI
DONE neuron - fix the front end so you can click on the checkbox instead of the entire row
DONE neuron - fix the front end so you don't have to refresh page to get histories
DONE server - get the pin/depin call working on neuron
DONE neuron - remove view of the pinning feature (not sure it works)
DONE neuron - automatically delete subscriptions and predictive streams for unsanctioned streams
DONE central - refactor how we handle subscriptions in database: one single source of truth for raw data stream preditions, subscriptions table becomes only for ancillary subscriptions
DONE central - rewrite the process of choosing streams to predict:
DONE central - get a list of deleted predictings for streams that are sanctioned
DONE neuron, central - inspect subscriptions again.
DONE neuron - rebuild base image with new stuff
DONE neuron - host p2p file doesn't recognize when neuron is up
DONE neuron - host p2p file probably doesn't return to a waiting state if neuron goes down
DONE neuron - publish stream isn't loaded or relayed
DONE neuron - on checkin why am I not getting streams assigned to predict
DONE neuron - figure out why we don't have history or predictions on ui
DONE neuron - download where you left off.
DONE neuron - clear only what is wrong in download.
DONE central - are predictions being produced? yes
DONE central - are predictions being produced with new neuron? no
DONE central - save the time
DONE central - save history first
DONE central - fix double history glitch that has always existed
DONE central - fix predictions not being noticed? or something. payments arent going for predictions right now
DONE central - why aren't predictions being counted? predictors query perhaps - they are
DONE neuron - fix predictions not being produced:
DONE neuron - dataset not being produced properly - false alarm - dedupe
DONE central - still having some kind of issue on new downloads - doesn't assign streams or doesn't show them on neuron since they don't have 20 observations or something idk - figure it out.
DONE install - must rebuild all to get rid of double 'waiting on satori' printout
DONE neuron - make synapse a pip installable module - just the async and threaded scripts
DONE neuron - put python evrmore on pip

-- P2P options --

we have to make a more robust p2p solution. because we don't want to make the node operator change port settings, and we have to find a solution that handles nat traversal we can't use most available options, perhaps even including IPFS and  BitTorrent. I think there are basically 2 options:

1. use aiortc to implement p2p connections using webrtc protocol: set up your own peer discovery server, and your own signaling server and maybe even your own stun and turn and ice servers. I don't think we can use WebTorrent built on webrtc because it requires a browser, and satori is headless.
2. sure-up and simplify our current implmentation of udp hole punching: we were able to get it to work for 2 test nodes reliably, but it seems to constantly fail in beta production. I think the design is trying to do too much and is too complex (prematurely optimized), leading to it being too brittle. Instead of using rest on a rendezvous server and connecting to every machine at all times we could set up a websocket connection as a secondary pubsub server where reuqests for immediate connections would come in and be handled on an on-demand basis. Clients would only have to deal with one connection per stream at a time. And we'd use that connection to negotiate historic data only, for now.

I think option 2 is worth trying, partly because I know exactly what it entails and how to troubleshoot it and tell if it's working well, and partly because if we can get the UDP hole punching method to work it's simple and elegant. So after we finish giving the user more control over their predictive datastreams, we should try that to see if we can solve the p2p issue before launch.

DONE central - set up a synergy server (pubsub clone where subscribers can send in a request to connect, and the publisher will simply distribute historic datasets to them.)
DONE synergy - synergy protocol - request connection (with data request embedded)
DONE synergy - synergy protocol - promise connection
DONE synergy - synergy protocol - connect connection
DONE synergy - synergy protocol - send data
DONE synergy - synergy protocol - receive data
DONE neuron - publisher must allways be connected to synergy
DONE neuron - subscribers need only connect to synergy on demand
DONE server - make an end point for verifying p2p script hash
DONE neuron - handle saving data - test
DONE neuron - recreate the installer using the abstractor
DONE neuron - run the synergy script on startup to test.
DONE neuron - synergy author not found error should retry later? - on restart
DONE neuron - look out for packet empty queue error, might be fixed now
DONE neuron - gotta test mapping the port 24600 - maybe we can put the synapse inside. no good.
DONE neuron - get UI to start sooner
DONE neuron - show that you're building models
DONE neuron - everytime we get a message from pubsub about new data we should trigger a possible resync from the author if the data is disconnected

-- p2p end --

-- Prep for launch --

0. DONE - divisibility on rvn to 8 dec
1. DONE divisibility on evr to 8 dec
2. DONE build clone of network on test.satorinet.io
3. test extensively
4. DONE build NFT for launch

DONE all - reissue SATORI to be 8 decimal places, handle everywhere
DONE installer - I think we should visit the installer again before launch to give it the ability to shutdown or restart the node, that way we can update the docker image from within the docker image
DONE neuron - also give people the ability to auto send directly to their vault by changing the 'address' in wallet. investigate this - any issues with changing that address? anywhere I rely on the pubkey matching that address? might be best to make a new address field and pay to it if its not null.

DONE central - download ui should show docker to set it as running on docker step
DONE central - download ui should show step 3 as setting up vault, and mine to vault
DONE central - clone mainnet server to testnet server
DONE central - disable distributions on testnet
DONE central - setup/fix certs for testnet
DONE neuron - test connecting to testnet
DONE neuron - keep everything working off testnet till we have two working clones
DONE neuron - setup dev distinction
DONE vault - allow for automatic send of tokens to their vault (needed for vps users especially, advanced autosecure?)
DONE central - only have video on homepage

PLAN
    Before Launch
        App
            DONE simple one
        Legal
            DONE Ulas and other disclaimer/aggreement documents
        Central
            make sure every neuron ip address is unique
        Neuron
            DONE make optional wallet lock
            DONE ui message if people try to run it using just docker: to start Satori please double click on the desktop icon or restart your computer.
        Glitches
            DONE neuron or central - send all fails somewhere
            DONE footer nav
            DONE SSL redirect issue
            central - rework the daily scheduled batch process
        Affiliate Mining
            DONE central - accept pubkey in link, save to session
            DONE central - ip association with the referral
            DONE central - wallet association with the referral
            DONE neuron - show link in Neuron
            DONE neuron - ui to specify
            DONE neuron - call endpoint
            DONE central - endpoint
            DONE central - database to track
            DONE central - logic to avoid circular relationships
            DONE central - designation in minting manifest
            DONE central - designation in voting table
            DONE central - designation in voting logic
            DONE central - designation in mining logic
            DONE neuron - test voting
            DONE inform community
            DONE central - test distribution
            DONE central - manually rebuild tables in database test
            DONE central - manually rebuild tables in database prod
        Commemorative NFT on polygon
            DONE central - add columns to exiting test database
            DONE external - generate on some platform (rvn or opensea or something)
            DONE external - create artwork
            DONE external - host ipfs of artwork
            DONE lib - add ability to generate eth private keys locally
            DONE central - add eth address to database
            DONE central - add beta contributor to wallet
            DONE central - add rewarded to wallet
            DONE central - endpoint
            DONE central - manage
            DONE neuron - at least show the ETH address in their vault
            DONE neuron - make 'claim' atuomatic upon vault enter, if we need to make a button later in UI (send eth address)
            DONE neuron - pass eth address to central (upon open vault)
            DONE central - add columns to exiting main database
            DONE central - test entire process
            central - snapshot - set them to beta=1 june 30th MAIN
        Scalability
            DONE central - upgrade database to postgres
            central - install posgres
            central - migrate to posgres
            central - test posgres
            central - prod posgres
            central - revisit the scheduler after postgres as a standalone process since the database is multithreaded now.
        Infrastructure
            DONE setup backup electurmx servers for RVN and EVR
            DONE setup neurons on testnet full time
            DONE modify install to support testnet dynamically
            neuron - add neuron lock feature
        Deploy Mainnet
            external - make a separate wallet for the association so we don't co-mingle funds
            central - set the audit, wallet and other stuff to use that wallet
            DONE external - divisibility on evr to 8 dec
            neuron - switch mainnet to mainnet
    After Launch
        Banking
            accounts for The Satori Association
        Create Tutorials
            how to download
            how to install
            how to configure
            how to setup the vault
            how to share your affiliate link
            how to setup a oracle stream
            how to setup many orcacle streams
        Improve Neuron
            neuron - health monitor to verify we always connected to server, pubsub, peers / synergy when needed, electrumx when needed.
            central - health monitor as part of the admin dashboard
        Improve Mining
            central - implement competition check
        Improve Engine
            More Algorithms
                engine - use Chronos as a first pass, include it, optionally (depending on how useful it is) as a feature to the data on each datastream
                engine - take advantage of GPU - run chronos and xgboost on gpu if present
                engine - take advantage of multiple GPU - does it do this automatically since we're running multiple threads? idk.
            Better Exploration of Correlations
        Decentralized Chat Feature
            description - top down approach, each neuron is running GPT bots which answer questions given the data it knows. questions can be farmed out from the central website to neurons who respond. It's not time for this yet, if ever.
        Wrapped Token
            Contract
                design contract
                    ERC20 Basics
                    make sure it requires for an address to specify evr address upon burn
                test and deploy contract
            Eth setup
                DONE central - ipfs the icon 256x256 - bafybeiaggbts7bm3qniaemu7dvbzoqjyvcylosjevnvsewiz2hahxbgyoi
                DONE central - add eth address to database
                central - send eth address to central
                central - save eht address from neurons
                create address for holding evr wrapped tokens
                create address for holding wrapped tokens
                create owner address for contract
                get on Uniswap
                get on metamask swap
                get on tokenlist
                get on coingecko
                get on coinmarketcap
            neuron - include short tutorial video
            neuron - ui for wrapping token
                specify amount,
                only available in vault,
                display fee - 1 satori
                submit
            neuron - ui for unwrapping token
                enter eth burn transaction id
                submit
            neruon - call endpoints
            central - endpoints
            central - logic to wrap tokens
            central - logic to unwrap tokens
        Setup useful oracles
            Fred data
            finanacial data
            government statistics
            etc.

# TODO: CHANGE ON LAUNCH
neuron - point everything at evrmore wallet instead of ravencoin wallet and test
all - convert rvn wallet to evr wallet
all - all test evr manually since electrum servers are newer versions for evr
central - prodx to prod
Central - what about address? can't send to rvn addresses drive evr address for entire database, remove extra address, save elsewhere.

neuron - troubleshoot setting up a stream with the urls from wilsql
neuron - crete intensity level so you can dial down the rate at which it mines
neuron - on ui fix divisibility so it's at most 8 places
DONE central - setup restart signal
central - verify amounts match for distributions

DONE beta - make a commemorative NFT

central - test the average cadence query
central - derived cadence as well from history table
central - purge history more than 31+ days old (it grows very quickly)
central - see server todo
central - break database and servers into their own dockers to be deployed separately

DONE central - update website (images)
DONE central - update website (copy)
central - update website (yellowpaper)

central - we will need an admin dashboard to track the activity of the network

DONE central - setup additional electrumx server for evr

central - better frontend experience - llm lite

-- Launch --

-- Query Providers --

This is a top down approach to providing llm support across the network (usually to the website). Here's what we'd need to do to get this done in the minimalist way:

since the LLM runs too slowly when the neuron is doing it's normal behavior we need to break the neuron into 2 running modes: predictive, and responsive. in the responsive mode we slim down all things, even making a slimmer dashboard, and no extra threads: we make a copy of app.py with very little stuff, that checks in with the server indicating this responsive mode. We would run the ollama service in the background in this mode. We would connect to a copy of the pubsub network. when the machine is busy producing an answer we would either indicate we are busy if it's a push system or more likely, we would simply pull from the queries availble when we are available. we would need to incentivize this behavior so we would make a new designation for payments, and the voting mechanism and everything.

so...

1. make a copy of synergy so we can issue queries directly to neurons and get responses as they are generated
2. slim down version of the neuron with a minimal UI (maybe even cli if we don't need the wallet available in this mode). This simple version runs the ollama service and checks in with the server as a chat node.
3. create designation on server as chat nodes, and make a payment scheme for them (is it a category or is it a sanctioned stream or something?)

I see this entire 'service' as a necessary eventuality, so maybe we should build the most basic version of this soon. we will need to translate the knowledge the network generates into aggregated english concepts, so if we build this peice and evolve them together perhaps they can meet in the middle.

neuron - make a new slimmed down version of app.py, a new designation for queries in the pubsub and a new mode of running to answer queries, must tell server when available and when not available for a query, or it's first come first serve.

-- Nice --

neuron - on ui give restart/shutdown ability? why?  we only need to trigger it programmatically right now.

neuron - refactor data management - entire cache/disk system
neuron - refactor data management - make models beholden to cache
neuron - disk cache isn't able to added missing datastreams on the fly

all - complete stream pinning service:
server - add pinned status to checkin payload
neuron - use pinned status in checkin payload
neuron - test and fix potential problems in the pinning feature (make sure it respects the pinning decision)
neuron - allow neurons to predict any datastream including their own (not incentivized: assign_id = 2)
neuron - show which datastreams are active
neuron - show which datastreams are approved
all - change sanctioned to approved on all public stuff

neuron - update balances more realtime via subscriptions to the electrumx

vault - creation process with saving words
vault - allow user to change vault password

neuron - isolate transactions to it's own page/call
neuron - isolate stream votes to it's own page/call

neuron - settings:
neuron - change 'configuration' to settings, remove whats there, include options like, autorequest sanctioned datastreams
central - if a neuron is subscribed to an unsanctioned stream does the user know about it, and have the ability to switch to a sanctioned one? can that be a setting?

all - include different languages in neuron and on website, etc.

neuron - make values get pushed to front end UI for relay streams in realtime

Wallet Encryption:
    neuron - we really should at least give the option to encrypt the wallet yaml
    neuron - so on the wallet page add a card for encryption
    neuron - and ask for their password when showing the secret
    neuron - the only problem is in order to sign anything to verify your identity you need to use the private key... so the user would have to provide their password everytime satori starts... This is a problem for later... when they can authorize from their phone...

neuron - allow neurons to predict any stream by choice (include their own), but make them ineligible for reward for those streams
"""
ah, I see.

Well, you know what we probably should do that huh? We don't currently allow a neuron to predict its own streams because we wanted to avoid the problem of unfair advantage, so I think the right solution is actually to allow a neuron to predict its own streams but it won't be eligible for prediction reward on those particular streams, because since it's the one that's also generating them it could know them before it releases them to everyone else.

So that's a change I'm going to have to make.
"""
neuron - add the ability to manually trigger update, or make it instant and automatic.
"""
Can you add information in the panel or somewhere on the page that a new version has been released and with one click it will restart the node to the new version?
"""

neuron - earned pending estimate
"""
lajot — Today at 1:37 PM
would be nice to see pending satoris
meta stack — Today at 1:37 PM
oh like how many you've earned that day?
lajot — Today at 1:37 PM
and countdown for next payout
kinda lika a mininpool interface
lajot — Today at 1:37 PM
yeah
meta stack — Today at 1:37 PM
nice, it would have to be an estimate but good idea
lajot — Today at 1:38 PM
and some kind of "explorer" page with statistics
charts of neurons and so on
meta stack — Today at 1:39 PM
like a world map and growth charts, nice
"""
