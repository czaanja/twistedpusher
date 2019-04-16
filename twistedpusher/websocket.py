#!/usr/bin/env python
# -*- test-case-name: twistedpusher.test.test_websocket -*-

import logging

from zope.interface import implementer
from twisted.internet import defer
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory

from twistedpusher.events import load_pusher_event, serialize_pusher_event
from twistedpusher.interfaces import IPusherProtocol

log = logging.getLogger(__name__)


@implementer(IPusherProtocol)
class PusherWebsocketProtocol(WebSocketClientProtocol):
    def __init__(self):
        """Pusher websocket connection."""
        self.on_connection_lost = defer.Deferred()
        self.on_event = None

    def onClose(self, wasClean, code, reason):
        """Handle Websocket connection shutdowns."""
        self.on_connection_lost.callback({'clean': wasClean, 'code': code, 'reason': reason})

    def onMessage(self, payload, isBinary):
        """
        Receive websocket messages.
        :type isBinary: bool
        """
        if not isBinary:
            event = load_pusher_event(payload)
            if self.on_event:
                self.on_event(event)
        else:
            # message is in binary
            raise NotImplementedError("Pusher websocket message in a binary format.")

    def send_event(self, event):
        """:type event: Event"""
        self.sendMessage(serialize_pusher_event(event))

    def disconnect(self):
        if self.state == WebSocketClientProtocol.STATE_OPEN:
            self.sendClose(code=1000)


class PusherWebsocketFactory(WebSocketClientFactory):
    """Factory for Pusher websocket connections."""
    protocol = PusherWebsocketProtocol
    noisy = False