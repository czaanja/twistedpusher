#!/usr/bin/env python

import logging
from twisted.application.service import IService
from zope.interface import Attribute, Interface

log = logging.getLogger(__name__)


class IEventEmitter(Interface):
    """Simple event dispatching. Listeners bind to event names and receive Event objects."""

    def bind(event_name, listener):
        """
        Bind a callable to a specific event.
        :type event_name: str or unicode
        :raises ValueError: if listener is not a callable
        """

    def unbind(event_name, listener):
        """
        Unbind a callable from a specific event.
        :type event_name: str or unicode
        :raises ValueError: if listener to be removed is not found
        """

    def bind_all(listener):
        """
        Bind a callable to all events emitted by this object.
        :raises ValueError: if listener is not a callable
        """

    def unbind_all(listener):
        """
        Unbind a listener that was bound to all events.
        :raises ValueError: if specified global listener is not found
        """

    def emit_event(event):
        """
        Dispatch an event to registered listeners.

        :param event: event object
        :type event: Event
        """


class IPusherConnection(IEventEmitter, IService):
    """Provides high-level access to the Pusher connection."""
    state = Attribute('state', 'The current connection state.')
    prev_state = Attribute('prev_state', 'The last connection state.')
    socket_id = Attribute('socket_id',
                          'Pusher socket ID for the current connection. Only valid while state is connected.')
    transport = Attribute('transport', 'an IPusherTransport')

    def send_event(event):
        """
        Send an event to Pusher.
        :type event: Event
        """


class IPusherTransport(IEventEmitter, IService):
    state = Attribute('state', 'Current transport state. Not 1:1 with emitted events.')
    prev_state = Attribute('prev_state', 'Previous transport state.')

    def send_event(event):
        """
        Send an event to Pusher.
        :type event: Event
        """

    def reconnect():
        """"""


class IPusherProtocol(Interface):
    """
    Provides low-level tools for managing a Pusher connection.
    Implemented by Protocols returned by the connection factory.
    """
    on_connection_lost = Attribute('on_connection_lost',
                                   """Deferred triggered when the connection is lost with a dict of info on why.""")
    """:type on_connection_lost: defer.Deferred"""
    on_event = Attribute('on_event', 'Set this to a callable to listen to all Pusher events received by the protocol.')

    connected = Attribute('connected', 'bool indicating whether a connection is currently established.')

    def send_event(event):
        """
        Send an event to Pusher.
        :type event: Event
        """

    def disconnect():
        """Close the connection immediately."""
