Introduction
==========
TwistedPusher is a Pusher client for Twisted Python.

Find it at https://github.com/socillion/twistedpusher

Latest version: 1.3.1

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
    
Installing
==========
See [requirements.txt](requirements.txt) for a list of dependencies.
Specifically: `twisted`, `autobahn`, and `pyopenssl` (for `wss://`) as well as their respective requirements.


Future Plans
==========
* Add support for presence/private channels. The primary reason I haven't done this is I don't know an easy
way to verify whether it actually works.
    * auth
        * subscription failure
    * trigger events
    * channel member list state events
        * see http://pusher.com/docs/pusher_protocol#client-only-events
* Allow usage of transports other than websocket
* Work on docs
* Add integration tests
* Test with other version of Python
* Add a `setup.py`