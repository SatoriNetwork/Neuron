issues:

DONE 1. remove row number cache design from disk, add in regular old cache design.
DONE 2. move scheduler up to the engine level, cycle through all datasets.
DONE 3. make sure we clear out any bad data at all times.
DONE 4. move the cache out of the topic, and up to the startDag singleton, then make everything pull from the same cache, such as the relay stuff, rendezvous stuff, and engine, anything that uses the Disk object currently.
DONE 5. make better use of the async stuff, convert simple timed threads to use it.

DONE 8. make the rendezvous relay server run by default
DONE 11. remove prints and debug logs
DONE 13. remove reto
DONE 6. move the host.py stuff into the runner
DONE 6a. recompile test
DONE 7. rebuild the docker containers
DONE 13. research solution on avalanche
DONE 14. fix installer - must make sure to pull the latest version explicitly
DONE 18. fix open browser - before blocking
DONE 19. loop until docker pulls correctly
DONE 15. fix installer - windows doesn't recognize it as safe - sign it.
FINE 16. fix installer - on one computer windows defender flagged it as a "bearfoos" virus, so we have to figure that out. - doesn't happen on more up to date windows machines
DONE 17. fix pause functionality - it's reversed, paused by default I think?
DONE 20. I noticed histories aren't downloading automatically. explore...
DONE 21. fix issue where we can miss some of the raw data stream and we'd never know, except we would because when we ask and it doesn't match our hash we know it's no goood. so we have to ask for the history backwards until we find the missing data. the best solution is to broadcast the hash in the pubsub. then if it looks like the hash is invalid, we know that we missed something. at that point what should we do? when it looks like our dataset is missing something we should? ask for the middle hash, then see if it matches, so on and so forth until we identify the missing one? not sure.
DONE 22. when we broadcast a prediction we need to include time and observationHash too
DONE 23. not saving observations
9. test
10. seed with datastreams with histories
12. release alpha Jan 1
13. still have a connection annoyance, but it connects eventually on startup.