#!/usr/bin/env python

import logging
import warnings
from twisted.application.service import MultiService
from twisted.internet.endpoints import clientFromString

from twistedpusher.connection import Connection
from twistedpusher import channel, websocket
from twistedpusher.events import EventEmitter

log = logging.getLogger(__name__)

# References:
# http://pusher.com/docs/pusher_protocol
# http://autobahn.ws/python/reference.html
# http://autobahn.ws/python/examples.html

VERSION = '1.3.0'


class PusherService(MultiService, EventEmitter):
    protocol_version = 7
    host = 'ws.pusherapp.com'
    client_name = 'twistedpusher'

    def __init__(self, key, encrypted=True, endpoint_string=None, reactor=None, **kwargs):
        """
        Pusher client service. Start it with ``startService`` and stop it with ``stopService``.

        :param key: key for the Pusher application to connect to
        :type key: str

        :param encrypted: whether to use secure websockets
        :type encrypted: bool

        :param endpoint_string: a string to build the endpoint with, using clientFromString
        :type endpoint_string: str

        :param reactor: optional Twisted reactor
        """
        # Must do it this way so both constructors execute.
        # (Multi)Service constructor is not equipped for multiple inheritance.
        MultiService.__init__(self)
        EventEmitter.__init__(self)

        self.key = key
        self.encrypted = encrypted

        if not reactor:
            from twisted.internet import reactor

        # todo add support for other factory classes
        factory = websocket.PusherWebsocketFactory(
            url=PusherService._build_url(key, encrypted),
            useragent='{0}/{1}'.format(PusherService.client_name, VERSION),
            **kwargs)
        endpoint = self.__class__._build_endpoint(endpoint_string, encrypted)

        self.connection = Connection(factory, endpoint, self._on_event, reactor=reactor)
        self.addService(self.connection)

        # List of subscribed channels
        self.channels = dict()

    ####################
    ##### Channels #####
    ####################

    def subscribe(self, channel_name, **kwargs):
        """
        Subscribe to a channel.

        :param channel_name: the channel's name
        :type channel_name: str or unicode

        :param json_data: flag to enable parsing client event data as JSON

        :return: the created channel
        :rtype: twistedpusher.Channel

        :raises BadChannelNameError: if channel_name is not a valid Pusher channel name
        """
        if channel_name not in self.channels:
            chan = channel.buildChannel(channel_name, self.connection, **kwargs)

            # only subscribe if connected, it'll get automatically triggered on connect if we aren't
            if self.connection.state == 'connected':
                chan.subscribe()
            self.channels[channel_name] = chan
        else:
            warnings.warn("Already subscribed to channel {0}".format(channel_name))

        return self.channels[channel_name]

    def unsubscribe(self, channel_name):
        """
        Unsubscribe from a channel.

        :param channel_name: the channel's name
        :type channel_name: str
        """
        if channel_name in self.channels:
            self.channels[channel_name].unsubscribe()
            self.channels.pop(channel_name)
        else:
            warnings.warn("Attempted to unsubscribe from channel {0} when not subscribed".format(channel_name))

    def channel(self, channel_name):
        """
        Get a channel by name.

        :type channel_name: str

        :return: the requested channel, if found
        :rtype: twistedpusher.Channel

        :raises ValueError: if the channel is not found (i.e. subscribed to)
        """
        try:
            return self.channels[channel_name]
        except KeyError:
            raise ValueError("Channel not found: '{0}'.".format(channel_name))

    ####################
    ##### Handlers #####
    ####################

    def _on_event(self, event):
        """
        :type event: events.Event
        """
        try:
            chan = self.channels[event['channel']]
        except (KeyError, AttributeError) as e:
            # not subscribed to the channel, or this isn't a channel event.
            pass
        else:
            chan.emit_event(event)
            self.emit_event(event)

    #####################
    ##### Utilities #####
    #####################

    @classmethod
    def _build_url(cls, key, encrypted):
        """
        Build a Pusher URL using the specified app key.

        :param key: Pusher application key
        :type key: str
        :param encrypted: whether to use secure websockets (wss)
        :type encrypted: bool

        :return: a Pusher URL
        :rtype: str
        """
        path = "/app/{0}?client={1}&version={2}&protocol={3}".format(
            key,
            cls.client_name,
            VERSION,
            cls.protocol_version)
        return "{0}://{1}:{2}{3}".format(
            "wss" if encrypted else "ws",
            cls.host,
            443 if encrypted else 80,
            path)

    @classmethod
    def _build_endpoint(cls, endpoint_string=None, encrypted=True, timeout=5, host=None):
        from twisted.internet import reactor
        host = host or cls.host
        if endpoint_string:
            endpoint = clientFromString(reactor, endpoint_string)
        else:
            if encrypted:
                port = 443
                proto = 'ssl'
            else:
                port = 80
                proto = 'tcp'
            endpoint = clientFromString(reactor, '{0}:host={1}:port={2}:timeout={3}'.format(proto, host, port, timeout))
        return endpoint


class Pusher(PusherService):
    def __init__(self, key, encrypted=True, endpoint_client_string=None, **kwargs):
        """
        Pusher client. Extends PusherService.

        :param key: key for the Pusher application to conenct to
        :type key: str

        :param encrypted: whether to use secure websockets
        :type encrypted: bool
        """
        super(Pusher, self).__init__(key, encrypted, endpoint_client_string, **kwargs)

        from twisted.internet import reactor
        reactor.addSystemEventTrigger('before', 'shutdown', self.stopService)

        self.connect()

    def connect(self):
        """
        Connect to Pusher.
        """
        self.startService()

    def disconnect(self):
        """Disconnect from Pusher."""
        self.stopService()


Client = Pusher
ClientService = PusherService