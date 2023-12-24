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
9. test
10. seed with datastreams with histories
12. release alpha Jan 1
13. research solution on avalanche
14. fix installer - must make sure to pull the latest version explicitly
DONE 15. fix installer - windows doesn't recognize it as safe
16. fix installer - on one computer windows defender flagged it as a "bearfoos" virus, so we have to figure that out.