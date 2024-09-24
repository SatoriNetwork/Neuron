# his delegate
>> > d.read("select * from balance where wallet_id = 401787")
wallet_id currency  satori  proxy                               ts deleted
0     401787     None   5.998    0.0 2024-09-22 23: 36: 22.967054+00: 00    None
# his remote
>> > d.read("select * from wallet where address='Ec7igsKkT4xdyy9hrNFQ2rRAKdq3xL84vk'")
id                                             pubkey                             address  ...                               ts deleted                       rewardaddress
0  376489  03627a67bd8fbe91453603791b87847a58159a69e14ee7...  Ec7igsKkT4xdyy9hrNFQ2rRAKdq3xL84vk  ... 2024-09-19 16: 30: 19.741330+00: 00    None  EUwAmX1J2LkBsU8WB5oFMP7SmZTRCwYe3j

[1 rows x 16 columns]
>> > d.read("select * from proxy where child = 376489")
Empty DataFrame
Columns: []
Index: []
>> > d.read("select * from proxy where parent = 376489")
Empty DataFrame
Columns: []
Index: []
# unable to delegate to it.

d.write("update proxy set parent=401787 where child= 376489")


remote: EHiB6LJvhkY8dbkXAJjMRG6jWdgnvqvZnS
delegate: EJwQdjEXzc2tRQW6mLBgifjQLBqrMwF765

the remote is v2.08 so it should work since it said saved on the remote side

[6:19 PM]
the remote side seems to be working now which is weird. just tried on another v2.06 and it says saved
[6:23 PM]
well, it seems isolated to just that delegate. got 2 others to work fine

BoNoBo — Today at 6: 26 PM
This remote wont save to the delegate
EZfHAPz2ooXadW1932dwFoD9FDrWVpR1x6

[6:26 PM]
so its not the version
