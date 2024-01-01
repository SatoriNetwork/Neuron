issues:

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
test
seed with datastreams with histories
rendezvous, pubsub, server: anything behind gunicorn not logging right.
make an installer for linux
have it make a prediction and broadcast it on startup
show the latest prediction on the UI