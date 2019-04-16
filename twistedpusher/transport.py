#!/usr/bin/env python
# -*- test-case-name: twistedpusher.test.test_channel -*-

import logging
import warnings
from twisted.application.service import Service
from twisted.internet import task
from zope.interface import implementer

from twistedpusher.interfaces import IPusherTransport
from twistedpusher.events import Event, EventEmitter
from twistedpusher.utils import Timeout

log = logging.getLogger(__name__)

# maximum delay between reconnect attempts
MAX_RECONNECT_DELAY = 10

# all possible transport states
TRANSPORT_STATES = {'connected', 'disconnected', 'connecting', 'disconnecting', 'reconnecting'}


@implementer(IPusherTransport)
class Transport(EventEmitter, Service):
    """
    Handles the low-level details of a connection to Pusher.

    :ivar state: the current transport state
    :ivar prev_state: previous state

    :ivar endpoint: the endpoint to connect with
    :ivar factory: the factory that builds `IPusherProtocol` objects

    ==================  =======================================
    Possible states:
    -----------------------------------------------------------
    State               When it is triggered
    ==================  =======================================
    disconnected        once the connection is broken
    connecting          after beginning a connection attempt
    connected           if a connection attempt succeeds
    reconnecting        indicates to reconnect on disconnect
    disconnecting       prevents reconnecting on disconnect
    ==================  =======================================

    ==================  =======================================
    Emits the following events:
    -----------------------------------------------------------
    Event               Explanation
    ==================  =======================================
    started_connecting  the transport began trying to connect
    connecting_in       how long until the transport will try to connect again, has a non-zero ``delay`` attribute
    connected           a connection was established
    disconnected        the connection is now broken (not triggered by failure, only loss)
    ==================  =======================================

    """
    def __init__(self, factory, endpoint, on_pusher_event, reactor=None):
        """
        Manages the transport with auto-reconnecting and state events.

        :param: factory: a factory that builds IPusherProtocol objects
        :param endpoint: an endpoint to connect with
        :param on_pusher_event: function to call with received Pusher events
        :param reactor: optional IReactorTime provider, defaults to twisted.internet.reactor
        """
        EventEmitter.__init__(self)

        assert callable(on_pusher_event)
        self.on_event = on_pusher_event

        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor

        self.factory = factory
        self.endpoint = endpoint
        self.protocol = None

        self._state = 'disconnected'
        self.prev_state = self._state

        self.connect_attempt_timeout = Timeout(30,
                                               self._disconnect,
                                               reactor=self.reactor)

        self.connect_attempt = None
        self.connect_attempt_count = 0

    def startService(self):
        super(Transport, self).startService()
        self._connect()

    def stopService(self):
        super(Transport, self).stopService()
        self._disconnect()

    def reconnect(self):
        """Disconnect and then connect again."""
        self._disconnect()
        # connect will happen automatically

    def _connect(self):
        """Connect the transport."""
        if self.state == 'disconnected':
            self.state = 'connecting'

            # double reconnect delay each call.
            # Range:     1 <= delay <= max_reconn_delay
            connect_wait_time = max(1, min(MAX_RECONNECT_DELAY, 2**self.connect_attempt_count))

            if connect_wait_time:
                # we'll be waiting to connect
                self.emit_event(Event(name='connecting_in', delay=connect_wait_time))

            if not self.connect_attempt_count:
                # haven't failed any connect attempts yet
                self.emit_event(Event(name='started_connecting'))

            def do_connect():
                self.connect_attempt = self.endpoint.connect(self.factory)
                self.connect_attempt_timeout.start()
                self.connect_attempt.addCallbacks(self._connected, self._failed)
                return self.connect_attempt

            self.connect_attempt_count += 1
            self.connect_attempt = task.deferLater(self.reactor, connect_wait_time, do_connect)

            return self.connect_attempt

    def _disconnect(self):
        """Disconnect the transport."""
        old_state = self.state
        if self.running:
            self.state = 'reconnecting'
        else:
            self.state = 'disconnecting'

        if old_state == 'connected':
            self.protocol.disconnect()
        elif old_state == 'connecting':
            self.connect_attempt.cancel()

    def send_event(self, event):
        """
        :param event: the event to send
        :type event: Event
        """
        if self.state == 'connected':
            self.protocol.send_event(event)
        else:
            warnings.warn("Attempted to send an event while the transport is disconnected")

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        assert new_state in TRANSPORT_STATES
        if new_state != self._state:
            self.prev_state = self._state
            self._state = new_state
            log.debug("Transport state: {} -> {}".format(self.prev_state, new_state))

    def _connected(self, proto):
        """
        Called on connection.

        :param proto: an IPusherProtocol provider
        """
        self.state = 'connected'

        self.protocol = proto
        self.connect_attempt_count = 0
        self.connect_attempt_timeout.stop()
        self.protocol.on_event = self.on_event
        self.protocol.on_connection_lost.addCallback(self._lost)

        self.emit_event(Event(name='connected'))
        return self.protocol

    def _failed(self, reason):
        """
        Called on connection failure.
        :param reason: a reason for the failure
        """
        old_state = self.state
        self.state = 'disconnected'

        if old_state != 'disconnecting':
            self._connect()
        # returning this doesn't work, since it re-raises the exception
        #return reason

    def _lost(self, info):
        """
        Called on connection loss.
        :param info: info on the connection loss, the 'reason' key will be logged
        :type info: dict
        """
        old_state = self.state
        self.state = 'disconnected'
        self.emit_event(Event(name='disconnected'))

        if old_state == 'connected':
            if isinstance(info, dict):
                reason = info.get('reason', '')
                if reason:
                    reason = ': ' + reason
                log.info("Unexpected Pusher connection loss{}".format(reason))

        if old_state != 'disconnecting':
            self._connect()

        return info
