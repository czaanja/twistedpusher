#!/usr/bin/env python
# -*- test-case-name: twistedpusher.test.test_connection -*-

import logging
import warnings

from twisted.application import service
from zope.interface import implementer

from twistedpusher.events import Event, EventEmitter
from twistedpusher.utils import Timeout
from twistedpusher.interfaces import IPusherConnection
from twistedpusher.errors import ConnectionError
from twistedpusher.transport import Transport

log = logging.getLogger(__name__)


### Constants ###

# pusher connection events
CONNECTION_ESTABLISHED = 'pusher:connection_established'
PING = 'pusher:ping'
PONG = 'pusher:pong'
ERROR = 'pusher:error'

# missing 'failed' intentionally
CONNECTION_STATES = set(['initialized', 'connecting', 'connected', 'unavailable', 'disconnected'])
# not used, just for documentation
EMITTED_EVENTS = set(['error', 'connecting_in', 'state_change']).union(CONNECTION_STATES)

# complete list of possible error codes
ERROR_CODES = {
    4000: 'application only accepts SSL connections',
    4001: 'application does not exist',
    4003: 'application disabled',
    4004: 'application is over connection quota',
    4005: 'path not found',
    4006: 'invalid version string format',
    4007: 'unsupported protocol version',
    4008: 'no protocol version supplied',

    4100: 'over capacity',

    4200: 'generic reconnect signal',
    4201: 'ping/pong reply not received by server',
    4202: 'connection closed after inactivity',

    4301: 'client event rejected due to rate limit'
}

# how long to attempt to connect before setting state to 'unavailable'
TIME_BEFORE_UNAVAILABLE_STATE = 30

### End constants ###


# todo make these state machines nicer?
# maybe something from here https://stackoverflow.com/questions/2101961/python-state-machine-design


@implementer(IPusherConnection)
class Connection(EventEmitter, service.MultiService):
    """
    :ivar state: current connection state, all possibilities enumerated in ``CONNECTION_STATES``
    :type state: str
    :ivar socket_id: Pusher socket ID of currently established connection
    :type socket_id: str

    :ivar transport: ``IPusherTransport`` provider

    ==============  =======================================
    Possible states:
    -------------------------------------------------------
    State           When it is triggered
    ==============  =======================================
    initialized     initial state, not emitted
    connecting      when attempting to connect
    unavailable     after failing to connect for a while
    connected       on a fully established connection
    disconnected    on intentionally disconnecting
    ==============  =======================================

    ==============  =======================================
    Emits the following events:
    -------------------------------------------------------
    Event               Explanation
    ==============  =======================================
    States          Listed above. They have an attribute 'previous' with the previous state
    state_change    duplicate of the states, with attributes 'current' and 'previous'.
    connecting_in   if attempting to connect, how long the delay is until next attempt. Has attribute 'delay'.
    error           Pusher errors, data includes fields 'code' and maybe 'message'.
    ==============  =======================================
    """
    def __init__(self, factory, endpoint, on_channel_event, reactor=None, **kwargs):
        """
        :param clock:
        :param transport: ``IPusherTransport`` provider
        :param on_channel_event: callback to send channel events

        """
        EventEmitter.__init__(self)
        service.MultiService.__init__(self)

        assert callable(on_channel_event)

        self.on_channel_event = on_channel_event

        if not reactor:
            from twisted.internet import reactor

        self.transport = Transport(factory, endpoint, self._on_event, reactor)
        self.transport.bind_all(self._on_transport_event)
        self.addService(self.transport)

        # socket_id is returned by Pusher on connection
        self.socket_id = ''

        # Sends a ping if the connection has been dead for a while.
        def keepalive():
            self.pong_timeout.start()
            self.send_event(Event(name='pusher:ping'))
        self.activity_timeout = Timeout(120,
                                        keepalive,
                                        reactor=reactor)

        # Started if we sent a ping and expect a pong.
        self.pong_timeout = Timeout(30,
                                    self.transport.reconnect,
                                    reactor=reactor)

        def go_unavailable():
            self.state = 'unavailable'
        # Changes the state to unavailable if we're having trouble connecting.
        self.unavailable_timeout = Timeout(TIME_BEFORE_UNAVAILABLE_STATE,
                                           go_unavailable,
                                           start_now=False, reactor=reactor)

        self.handlers = {CONNECTION_ESTABLISHED: self._connected,
                         ERROR: self._error,
                         PING: self._ping,
                         PONG: self._pong}

        # Publicly accessible state info (changes also accessed via bind)
        self._state = 'initialized'
        self.prev_state = self._state

    ######################
    #####     IO     #####
    ######################

    def send_event(self, event):
        """
        :param event: the event to send
        :type event: Event

        :raises ConnectionError: if attempting to send an event while not connected.
        """
        if self.state == 'connected':
            return self.transport.send_event(event)
        else:
            raise ConnectionError("Attempted to send an event while disconnected: {0}".format(event))

    ############################
    ##### Connection State #####
    ############################

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        assert new_state in CONNECTION_STATES
        if new_state != self._state:
            self.prev_state = self._state
            self._state = new_state

            log.info("Connection state: {0} -> {1}".format(self.prev_state, self._state))
            self.emit_event(Event(name=new_state, previous=self.prev_state))
            self.emit_event(Event(name='state_change', current=new_state, previous=self.prev_state))

    def _on_transport_event(self, event):
        if event.name == 'started_connecting':
            self.state = 'connecting'
            self.unavailable_timeout.start()
        elif event.name == 'connected':
            self.activity_timeout.start()
        elif event.name == 'disconnected':
            if self.activity_timeout.active:
                self.activity_timeout.stop()
            if self.pong_timeout.active:
                self.pong_timeout.stop()

            if self.running:
                self.state = 'connecting'
            else:
                self.state = 'disconnected'
        elif event.name == 'connecting_in':
            self.emit_event(event)
        else:  # pragma: no cover
            log.critical("Unrecognized transport event '{}'".format(event.name))
            assert False

    def _on_event(self, event):
        """Called whenever an event is received from Pusher."""
        if hasattr(event, 'channel'):
            self.on_channel_event(event)
        elif event.name in self.handlers:
            self.handlers[event.name](event)
        else:  # pragma: no cover
            log.warning("Unrecognized Pusher event '{}'".format(event.name))
        self.activity_timeout.reset()

    def _connected(self, event):
        """
        Handle pusher:connection_established events.

        :type event: Event
        """
        self.unavailable_timeout.stop()
        self.socket_id = str(event.data['socket_id'])
        try:
            activity_timeout = int(event.data['activity_timeout'])
        except KeyError:  # pragma: no cover
            log.warning("Error reading activity timeout after establishing connection with Pusher...",
                        exc_info=True)
        else:
            self.activity_timeout.reset(activity_timeout)
        finally:
            log.info("Pusher connection socket_id is {0}.".format(self.socket_id))
            self.state = 'connected'

    def _error(self, event):
        """
        Handle pusher:error events.

        :type event: Event
        """

        event.name = 'error'
        self.emit_event(event)

        try:
            if event.data['code']:
                err = int(event.data['code'])
                err_str = "Pusher error {0}: ".format(err)

                try:
                    err_str += ERROR_CODES[err]
                except KeyError:
                    log.warning(err_str + event.data['message'])
                else:
                    err_str += '.'
                    log.warning(err_str)

                if (err >= 4000) and (err < 4100):
                    # Indicates an error resulting in the connection being closed by Pusher,
                    # and that attempting to reconnect using the same parameters will not succeed.
                    warnings.warn("It is impossible to connect to Pusher with the current connection parameters.")
                    self.stopService()
                #elif (err >= 4100) and (err < 4200):
                    # Indicates an error resulting in the connection being closed by Pusher,
                    # and that the client may reconnect after 1s or more.

                    # these two cases don't need special treatment since the transport will automatically reconnect
                #    pass
                #elif (err >= 4200) and (err < 4300):
                    # Indicates an error resulting in the connection being closed by Pusher,
                    # and that the client may reconnect immediately.
                #    pass
        except KeyError:
            log.warning("Problem processing pusher error: {0}".format(event.data), exc_info=True)

    def _ping(self, _):
        """Handle received pusher:ping events."""
        log.debug("An unexpected pusher:ping event was received from the Pusher server.")
        self.send_event(Event(name='pusher:pong'))

    def _pong(self, _):
        """Handle received pusher:pong events."""
        self.pong_timeout.stop()
        self.activity_timeout.start()