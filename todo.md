DONE remove row number cache design from disk, add in regular old cache design.
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

neuron - setup 3 more neurons
neuron - seed with datastreams with histories
-- BETA (test coin) target: march 3rd --
central - test the average cadence query
central - make it a soft delete - one reason we need it is streams can be published by others
central - modify queries to respect soft delete.
neuron - point everything at evrmore wallet instead of ravencoin wallet and test
all - convert rvn wallet to evr wallet
all - all test evr manually since electrum servers are newer versions for evr
central - update website (images)
central - update website (copy)
central - update website (yellowpaper)

neuron - build in a "vault"
vault - creation process with encrypting with a password of their own
vault - creation process with saving words
vault - add vault page
vault - allow for automatic send of tokens to their vault

central - rendezvous, pubsub, server: anything behind gunicorn not logging right.
central - make a history table and test the history table
central - make sure server is saving history of observations
central - purge history more than 8 days old

-- Launch --

-- Nice --

central - setup electrumx server for evr

Wallet Encryption:
    neuron - we really should at least give the option to encrypt the wallet yaml
    neuron - so on the wallet page add a card for encryption
    neuron - and ask for their password when showing the secret
    neuron - the only problem is in order to sign anything to verify your identity you need to use the private key... so the user would have to provide their password everytime satori starts... This is a problem for later... when they can authorize from their phone...
