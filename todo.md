issues:

1. we got interupted when downloading histories and we didn't resume where we left off.
  why did we get interupted?
  why didn't we recover?
2. we aren't stopping asking for more data when we recognize a hash. so we need a way to do that.
3. related to that, we need to make sure we ask for the most recent time, then the oldest hash we have to see if we have the whole history, and we need to run a hash check through the whole dataset to see if we're missing any.