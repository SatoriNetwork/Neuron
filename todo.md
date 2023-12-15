issues:

1. we got interupted when downloading histories and we didn't resume where we left off.
  why did we get interupted?
  why didn't we recover?
2. we aren't stopping asking for more data when we recognize a hash. so we need a way to do that.
3. related to that, we need to make sure we ask for the most recent time, then the oldest hash we have to see if we have the whole history, and we need to run a hash check through the whole dataset to see if we're missing any.

4. datasets are wrong - time is wrong - saving to the right dataset? saving the wrong time? hashes are wrong? whats going on?
  a. its not as bad as I thought at first glance: requires us to deal with 3 things.
    first, we should save the observations time as the time given to us by the relay neuron. this might be happening...
    secondly, we need to clean hashes, not just verify but clean. that means remove all observations that don't fit in the chain.
    lastly, make sure you order the data before you read it and save it. test the cleaning function.
