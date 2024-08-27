meta stack
I need to build a simple product I think elixir would be perfect for, can I get your high level opinions about how to do it?

All I need is an api pubsub server. clients need to be able to create streams, publish json to those streams, subscribe to streams and perhaps request the entire history of a stream. that's it. no UI needed, but the clients are subscribing to streams, so they'll want to be connected to the server to get those updates constantly, forever.

I think elixir is perfect for this because I want lots of persistent connections to server so the clients can have subscriptions pushed to them realtime.

I was thinking of using phoenix LiveView with a relational database on the server, using GraphQL for historic queries. Does this sound like a good idea to you? would I want to use pg2? (edited)

Stevejones
do you care about the contents of the json that your users are publishing? 
why do you want graphQL? 
by stream do you mean websocket connection?
pg2 for what?

meta stack
first of all, know that I've never built a phoenix app before, so I'm just trying to architect the largest pieces of this system that must support thousands of concurrent subscribers.

the contents of the json will look something like this
{'key': 'text or number value',
'key1': 'each stream represents a table in the database',
'key2': 'keys would represent a column in a table',
'key3': 'a json object represents one row in that table'}

GraphQL could be used because streams and tables are coupled, and keys and columns are coupled. If I have a stream, x, with 2 columns, y, and z. and I make a query to get the entire history of column z in stream/table x. but that's aside from subscribing, it's an as-needed query functionality. For instance, say I want to evaluate the history of a stream in order to know if I want to subscribe to it - that kind of thing.

By stream I mean "Topic" probably. Websockets seems like an implementation layer, but when I say stream I'm talking about the abstract "data stream" Actually my entire post is to ask - how do I implement this abstract pattern? I don't even know the limitations of websockets or any other way of implementing this functionality.

pg2 because it seems like a pubsub system internal to the server itself, I would assume the best way to engineer this is to mirror the pubsub system internally that I want to instantiate world wide (edited)

Stevejones
https://www.youtube.com/watch?v=MZvmYaFkNJI
YouTube
Chris McCord
Build a real-time Twitter clone in 15 minutes with LiveView and Pho...
7:30

meta stack
Yes! that's great. So in this example there's a topic called "posts"

I guess the last question I have then is how do I make dynamic topics, like an actual twitter clone would have a "stream" or topic per user, which other users can subscribe to, but this tutorial looks like its just one big static topic called "posts" is that right?

Stevejones
he could have pulled the name out of the post for the topic and made the topic "posts_by_users_called_steve" or whatever you like

meta stack
thanks this is a great starting place for me

Orbital Love Platform
Some docs you may find relevant:
https://hexdocs.pm/phoenix_pubsub/2.1.1/Phoenix.PubSub.html
https://hexdocs.pm/phoenix/channels.html

Stevejones
theres no need to keep each stream as a table
you can keep the json from the user as a value
`user_id  stream_id  inserted_at  json_blob`

meta stack
true, but if I only want one key from that json, for all instance of a stream_id, I'd have to parse every single row to extract it.

Stevejones
id much rather do that in my application when handling user data.
vs in the db

meta stack
I'd rather parse it once and save it to the database in an easily quarriable state. I could parse it as it comes in, to multiple lines perhaps
what do you think of this?
`user_id  stream_id  key_id  inserted_at  value_blob`

Stevejones
what does key_id do

meta stack
there'd be a table of key names
I'd have to join to, the user knows the name

Stevejones
up to you, this is your show. my solution is to keep it simple and I wouldn't even allow users to shape the data they receive outside of the streams they are subscribed to. you remove a whole layer of fuckery
take out the graphql etc
and if a different shape of data is required
then they can publish a different shape under a different topic
that reduces the project into something manageable. forget the rest of the noise until you have something working and iterate on that





https://alchemist.camp/episodes
https://github.com/vjebelev/google_pubsub_grpc
https://github.com/simonewebdesign/elixir_pubsub