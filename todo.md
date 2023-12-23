issues:

DONE 1. remove row number cache design from disk, add in regular old cache design.
2. move scheduler up to the engine level, cycle through all datasets.
3. make sure we clear out any bad data at all times.
DONE 4. move the cache out of the topic, and up to the startDag singleton, then make everything pull from the same cache, such as the relay stuff, rendezvous stuff, and engine, anything that uses the Disk object currently.