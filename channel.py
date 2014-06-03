#!/usr/bin/env python
# -*- test-case-name: twistedpusher.test.test_channel -*-

import logging
import re
import json
from collections import Callable

from twistedpusher.events import Event, EventEmitter
from twistedpusher.errors import BadChannelNameError

log = logging.getLogger(__name__)

# todo add support for private and presence channels
# features: trigger client events, channel member data (presence), authentication (incl. subscription failure)

VALID_CHANNEL_NAME = re.compile('^[a-zA-Z_\-=@,.;]+$')


class ListenerWrapper(Callable):
    """
    This class is a doppelganger.
    It would be good to redo this in a simpler way, but I
    don't know how. functools.wrap doesn't work.
    """
    def __init__(self, target, ignore_pusher_events=True):
        self.listener = target
        self.ignore_pusher_events = ignore_pusher_events
    def __repr__(self):
        return self.listener.__repr__()
    def __str__(self):
        return self.listener.__str__()
    def __call__(self, event):
        if self.ignore_pusher_events:
            if not event.name.startswith(('pusher_internal:', 'pusher:')):
                self.listener(event)
        else:
            self.listener(event)
    def __hash__(self):
        return self.listener.__hash__()
    def __eq__(self, other):
        return self.listener == other

    def __getattr__(self, item):
        return getattr(self.listener, item)


class ChannelEventEmitter(EventEmitter):
    """
    Overrides EventEmitter to add a few features to Channels.
    1. an init flag to enable parsing client event data as JSON
    2. a bind_all flag to enable filtering of pusher events
    """
    def __init__(self, json_data=False):
        super(ChannelEventEmitter, self).__init__()
        self.parse_json_data = json_data

    def bind_all(self, listener, ignore_pusher_events=True):
        """
        Bind a listener to all events produced.

        :param listener: callable that will receive all events
        :param ignore_pusher_events: allows ignoring pusher events (those starting pusher: and pusher_internal:)
        :type ignore_pusher_events: bool

        :raises ValueError: if listener is not callable
        """
        # todo make a test to check whether a warning for a listener exception provides original function's info
        # todo another method of suppressing pusher_internal events
        # and not the doppelganger
        if ignore_pusher_events:
            if not callable(listener):
                raise ValueError("Global listener to be bound must be a callable.")
            wrapped = ListenerWrapper(listener)
            maybe_wrapped = wrapped
        else:
            maybe_wrapped = listener
        return super(ChannelEventEmitter, self).bind_all(maybe_wrapped)

    def emit_event(self, event):
        """
        Dispatch a channel event to registered listeners.

        :param event: event object guaranteed to have fields 'name', 'channel', and 'data'
        :type event: Event
        """
        if self.parse_json_data and isinstance(event.data, (str, unicode)):
            event.data = json.loads(event.data)
        return super(ChannelEventEmitter, self).emit_event(event)


class Channel(ChannelEventEmitter):
    def __init__(self, channel_name, connection, json_data=False, **kwargs):
        """
        Represents a Pusher channel.

        :param channel_name: channel to subscribe to
        :type channel_name: str or unicode
        :param connection: an IPusherConnection provider

        :param json_data: optional flag to enable parsing user event data as JSON

        :raises BadChannelNameError: if connection is not a ConnectionManager or the Pusher channel name is invalid
        """
        super(Channel, self).__init__(json_data)

        self.connection = connection

        if not VALID_CHANNEL_NAME.match(channel_name) or not len(channel_name):
            raise BadChannelNameError("Invalid channel name '{0}'".format(channel_name.encode('utf8')))
        self.name = channel_name

        self.bind('pusher_internal:subscription_succeeded', self._on_subscription_success)
        self.connection.bind('connected', self._on_pusher_connect)

    def _on_subscription_success(self, event):
        """Handle pusher subscribe messages."""
        log.debug("Subscribed to {0}.".format(self.name))
        event.name = 'pusher:subscription_succeeded'
        self.emit_event(event)

    def _on_pusher_connect(self, _):
        self.subscribe()

    def subscribe(self):
        """
        Subscribe to the Pusher channel.

        Users should not call this. Use ``Pusher.subscribe()`` instead.
        """
        event = Event(name='pusher:subscribe', data={'channel': self.name})
        self.connection.send_event(event)

    def unsubscribe(self):
        """Unsubscribe from the Pusher channel."""
        event = Event(name='pusher:unsubscribe', data={'channel': self.name})
        self.connection.send_event(event)


class PrivateChannel(Channel):
    def __init__(self, channel_name, connection, **kwargs):
        super(PrivateChannel, self).__init__(channel_name, connection, **kwargs)
        raise NotImplementedError('Private channels are not supported')


class PresenceChannel(Channel):
    def __init__(self, channel_name, connection, **kwargs):
        super(PresenceChannel, self).__init__(channel_name, connection, **kwargs)
        raise NotImplementedError('Presence channels are not supported')


def buildChannel(channel_name, connection, **kwargs):
    """
    Create a channel.

    :param channel_name: name of the channel to create
    :type channel_name: str

    :param connection: a :class:`~twistedpusher.connection.Connection` instance to pass to the channel

    :returns: the created channel
    :rtype: Channel or PrivateChannel or PresenceChannel
    """
    if channel_name.startswith('presence-'):
        chan_type = PresenceChannel
    elif channel_name.startswith('private-'):
        chan_type = PrivateChannel
    else:
        chan_type = Channel

    channel = chan_type(channel_name, connection, **kwargs)
    return channel
