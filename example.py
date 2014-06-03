#!/usr/bin/env python

from __future__ import print_function
from twisted.internet import reactor
from twistedpusher import Pusher

# Start the Pusher client. PusherService can also be used.
client = Pusher(key="de504dc5763aeef9ff52")

# Subscribe to a channel
channel = client.subscribe("live_trades")

# Listen to all events on the channel. If you want to receive
# Pusher events, use the flag ignore_pusher_events=False.
channel.bind_all(lambda event: print("Received an event named {}".format(event.name)))

# You can also receive connection state events.
client.connection.bind("connected", lambda _: print("Connected!"))
# state_change includes all connection state events.
client.connection.bind("state_change", lambda event: print("{} -> {}".format(event.previous, event.current)))

reactor.run()