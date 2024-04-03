'''
contains the protocol to communicate with clients once connected

once connected, the publisher will begin sending data to the subscriber starting
with the hash request. it will not wait for a response. it will merely continue 
to send the data to the subscriber until interrupted, at which time it will 
restart the process from the hash requested (in the interruption message).

the subscriber will accept data, checking that the new hash and data match the 
running hash and if it doesn't the subscriber will send a message to the server
with the lastest good hash received. it will ignore incoming data until it 
recieves that hash.
'''
