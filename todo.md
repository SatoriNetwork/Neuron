
DONE remove row number cache design from disk, add in regular old cache design
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

-- P2P options --

we have to make a more robust p2p solution. because we don't want to make the node operator change port settings, and we have to find a solution that handles nat traversal we can't use most available options, perhaps even including IPFS and  BitTorrent. I think there are basically 2 options:

1. use aiortc to implement p2p connections using webrtc protocol: set up your own peer discovery server, and your own signaling server and maybe even your own stun and turn and ice servers. I don't think we can use WebTorrent built on webrtc because it requires a browser, and satori is headless.
2. sure-up and simplify our current implmentation of udp hole punching: we were able to get it to work for 2 test nodes reliably, but it seems to constantly fail in beta production. I think the design is trying to do too much and is too complex (prematurely optimized), leading to it being too brittle. Instead of using rest on a rendezvous server and connecting to every machine at all times we could set up a websocket connection as a secondary pubsub server where reuqests for immediate connections would come in and be handled on an on-demand basis. Clients would only have to deal with one connection per stream at a time. And we'd use that connection to negotiate historic data only, for now.

I think option 2 is worth trying, partly because I know exactly what it entails and how to troubleshoot it and tell if it's working well, and partly because if we can get the UDP hole punching method to work it's simple and elegant. So after we finish giving the user more control over their predictive datastreams, we should try that to see if we can solve the p2p issue before launch.

central - set up a synergy server (pubsub clone where subscribers can send in a request to connect, and the publisher will simply distribute historic datasets to them.)
synergy - synergy protocol - request connection (with data request embedded)
synergy - synergy protocol - promise connection
synergy - synergy protocol - connect connection
synergy - synergy protocol - send data
synergy - synergy protocol - receive data
neuron - publisher must allways be connected to synergy
neuron - subscribers need only connect to synergy on demand
neuron - handle saving data
server - make an end point for verifying p2p script hash
neuron - recreate the installer using the abstractor

-- p2p end --

-- Prep for launch --

all - reissue SATORI to be 8 decimal places, handle everywhere

central - test the average cadence query
central - derived cadence as well from history table
central - purge history more than 31+ days old (it grows very quickly)
central - see server todo

neuron - point everything at evrmore wallet instead of ravencoin wallet and test
all - convert rvn wallet to evr wallet
all - all test evr manually since electrum servers are newer versions for evr
central - update website (images)
central - update website (copy)
central - update website (yellowpaper)

central - we will need an admin dashboard to track the activity of the network

central - setup additional electrumx server for evr

vault - allow for automatic send of tokens to their vault (needed for vps users especially, advanced autosecure?)

central - better frontend experience - llm lite

-- Launch --

-- Nice --

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
