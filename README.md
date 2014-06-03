Introduction
==========
TwistedPusher is a Pusher client for Twisted Python.

Find it at https://github.com/socillion/twistedpusher

Latest version: 1.3.0

**Major caveat: twistedpusher does not currently support Private/Presence channels.**

Usage
==========
See [the example](example.py) and [documentation](http://socillion.github.io/twistedpusher) for more.

    from twistedpusher import Pusher

    client = Pusher("pusherkey")
    channel = client.subscribe("channelname")

    def callback(event_obj):
        print(event_obj)

    channel.bind("event", callback)

Future Plans
==========
* Add support for presence/private channels
    * auth
        * subscription failure
    * trigger events
    * channel member list state events
        * see http://pusher.com/docs/pusher_protocol#client-only-events
* Allow usage of transports other than websocket
* Work on docs
* Add tests - integration and client
* Test with other version of Python

* Minor issue: make fake events in tests more flexible
    (mixed FakeEvent and dicts right now...) Could probably just use Event instead
* Minor issue: improve channel event emitting, particularly the pusher_internal stuff
TODO: trim unnecessary tests

Main barrier to adding private and presence channels is testing that it works. pusher-fake would work, but I don't
want to set up Ruby.
