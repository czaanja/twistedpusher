#!/usr/bin/env python

import mock
from twisted.internet import defer
from zope.interface import implementer

from twistedpusher.interfaces import IPusherProtocol

CONNECT_TIME = 3
TIMEOUT_TIME = 60

TEST_TIMEOUT = 0.1


# todo improve the FakeEvent/random dict usages... could probably just use Events.
class FakeEvent(object):
    def __init__(self, **kwargs):
        """:rtype: Event"""
        for k in kwargs.keys():
            setattr(self, k, kwargs[k])
        if 'data' not in kwargs:
            self.data = {}

    def get(self, key):
        return getattr(self, key)

PUSHER_CONNECT_EVENT = FakeEvent(name='pusher:connection_established', data={'socket_id': 'a', 'activity_timeout': 120})
PUSHER_PONG_EVENT = FakeEvent(name='pusher:pong')
PUSHER_PING_EVENT = FakeEvent(name='pusher:ping')
PUSHER_FATAL_ERROR_EVENT = FakeEvent(name='pusher:error', data={'code': 4003})
PUSHER_NONFATAL_ERROR_EVENT = FakeEvent(name='pusher:error', data={'code': 4103})
CONNECTING_IN_EVENT = FakeEvent(name='connecting_in', delay=3)
TEST_EVENT = FakeEvent(name='test')
TEST_CHANNEL_EVENT = FakeEvent(name='some_channel_event', channel='foobar', data={})


@implementer(IPusherProtocol)
class FakeProtocol(object):
    def __init__(self):
        # can be called to fake a disconnect
        self.on_connection_lost = defer.Deferred()
        # called with what it was set to
        self.on_event_set = defer.Deferred()

        self._on_event = None
        self.send_event = mock.Mock()
        self.disconnect = mock.Mock()

    @property
    def on_event(self):
        return self._on_event

    @on_event.setter
    def on_event(self, func):
        self._on_event = func
        self.on_event_set.callback(func)


def make_mock_endpoint():
    """Returns a tuple of (mock_endpoint, mock_protocol)"""
    endpoint = mock.Mock()
    proto = FakeProtocol()
    endpoint.connect.return_value = defer.succeed(proto)
    ret = (endpoint, proto)
    return ret
