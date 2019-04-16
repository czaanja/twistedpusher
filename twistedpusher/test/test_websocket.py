#!/usr/bin/env python

import mock
from twisted.trial import unittest
from twisted.internet import defer
from zope.interface.verify import verifyClass, verifyObject

from twistedpusher.websocket import PusherWebsocketProtocol
from twistedpusher.interfaces import IPusherProtocol
from twistedpusher.test.helpers import TEST_TIMEOUT


class WebsocketProtocolTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.m = mock.Mock()
        self.d = defer.Deferred()
        self.pr = PusherWebsocketProtocol()

    def test_implements_pusher_protocol_interface(self):
        """IPusherProtocol is implemented"""
        verifyClass(IPusherProtocol, PusherWebsocketProtocol)
        verifyObject(IPusherProtocol, self.pr)

    def test_on_close_runs_conn_lost_callback(self):
        """"""
        self.pr.on_connection_lost.chainDeferred(self.d)
        self.pr.onClose(None, None, None)
        return self.d

    def test_on_message_runs_on_event_callback(self):
        self.pr.on_event = self.m
        self.pr.onMessage('{"event": "pusher:none"}', False)
        self.m.assert_called_once_with({'name': 'pusher:none', 'data': {}})

    def test_on_message_with_binary_raises_not_implemented(self):
        self.assertRaises(NotImplementedError, self.pr.onMessage, '', True)