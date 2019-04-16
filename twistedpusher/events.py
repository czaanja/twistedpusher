#!/usr/bin/env python
# -*- test-case-name: twistedpusher.test.test_event -*-
# -*- test-case-name: twistedpusher.test.test_eventemitter -*-

import logging
import warnings
import traceback
from collections import defaultdict
from itertools import chain
import json
from zope.interface import implementer

from twistedpusher.interfaces import IEventEmitter
from twistedpusher.errors import BadEventNameError

log = logging.getLogger(__name__)


class Event(dict):
    """
    Encapsulates events.

    :ivar name: the event's name
    :type name: str or unicode
    """
    def __init__(self, **kwargs):
        super(Event, self).__init__(kwargs)

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, item):
        return self[item]


def serialize_pusher_event(event):
    """
    Convert an event to serialized JSON. Ignores all fields except ``name``, ``data``, and ``channel``.

    :param event: the event to serialize
    :type event: Event

    :returns: the event as serialized JSON
    :rtype: str

    :raises BadEventNameError: if the event has no name set
    """
    tmp_event = dict()

    tmp_event['event'] = event.get('name')
    if not tmp_event['event']:
        raise BadEventNameError("Event name not set")

    # this is to replace e.g. {} with '' but also gracefully handle a nonexistent 'data' key
    tmp_event['data'] = event.get('data') or ''

    if event.get('channel'):
        tmp_event['channel'] = event.channel

    serialized_event = json.dumps(tmp_event)
    return serialized_event


def load_pusher_event(raw_event):
    """
    Load an event from serialized JSON.

    :param raw_event: a serialized JSON event
    :type raw_event: str or unicode

    :returns: the parsed event
    :rtype: Event

    :raise BadEventNameError: if raw_event had no event name field
    """
    event = Event(**json.loads(raw_event))
    try:
        event.name = event.pop('event')
    except KeyError:
        raise BadEventNameError("No event name")
    if (event.name.startswith(('pusher:', 'pusher_internal:'))
            and 'data' in event
            and isinstance(event.data, (str, unicode))):
        event.data = json.loads(event.data)
    elif 'data' not in event:
        event.data = dict()
    return event


@implementer(IEventEmitter)
class EventEmitter(object):
    """
    EventEmitter is a widely-used base class that provides an interface to produce and consume named events.

    :Example:

    >>> x = EventEmitter()
    >>> x.bind_all(lambda event: log.debug(event))
    >>> x.emit_event(Event(name='this_is_an_event'))
    """
    def __init__(self):
        """
        Simple event dispatching.
        Listeners receive Event objects.
        """
        super(EventEmitter, self).__init__()
        self.listeners = defaultdict(set)
        self.global_listeners = set()

    def bind(self, event_name, listener):
        """
        Bind a listener to a specific event.

        :param event_name: name of the event to bind to
        :type event_name: str or unicode

        :param listener: function that will receive those events

        :raises ValueError: if listener is not callable
        """
        if callable(listener):
            self.listeners[event_name].add(listener)
        else:
            raise ValueError("Listener must be callable.")

    def unbind(self, event_name, listener):
        """
        Unbind a listener from a specific event.

        :param event_name: name of the event that the listener was bound to
        :type event_name: str or unicode

        :param listener: function that will no longer receive events

        :warns: if listener to be removed is not found
        """
        try:
            self.listeners[event_name].remove(listener)
        except KeyError:
            warnings.warn("Could not unbind listener {0} from event '{0}': listener not found.".format(event_name))

    def bind_all(self, listener):
        """
        Bind a listener to all events produced.

        :param listener: function that will receive all events

        :raises ValueError: if listener is not a callable
        """
        if callable(listener):
            self.global_listeners.add(listener)
        else:
            raise ValueError("Global listener must be a callable.", listener)

    def unbind_all(self, listener):
        """
        Unbind a global listener.

        :param listener: function that will no longer be called with all events

        :warns: if specified global listener to be removed is not found
        """
        try:
            self.global_listeners.remove(listener)
        except KeyError:
            warnings.warn("Could not unbind global listener '{0}': listener not found.".format(listener))

    def emit_event(self, event):
        """
        Dispatch an event to registered listeners. Mostly for internal use.

        :param event: event object
        :type event: Event
        """
        for cb in chain(self.global_listeners, self.listeners[event.name]):
            try:
                cb(event)
            except AssertionError:
                raise
            except Exception:
                # todo find a better method than this to avoid a listener error killing the transport connection
                warnings.warn("Error in listener {} called with event '{}': \n{}".format(cb.__name__,
                                                                                         event.name,
                                                                                         traceback.format_exc()))