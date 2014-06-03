#!/usr/bin/env python

import mock
from twisted.trial import unittest
from zope.interface.verify import verifyClass, verifyObject
from twisted.internet import task, defer

from twistedpusher.client import Pusher, PusherService
from twistedpusher.interfaces import IPusherClient, IPusherClientService
from twistedpusher.test.helpers import TEST_TIMEOUT

# Tests needed:
# url creation?
# todo finish tests


class InterfacesTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.clock = task.Clock()

    def test_pusher_client_interface(self):
        verifyObject(IPusherClient, Pusher(mock.Mock(), reactor=self.clock))
        verifyClass(IPusherClient, Pusher)

    def test_pusher_client_service_interface(self):
        verifyObject(IPusherClientService, PusherService(mock.Mock(), reactor=self.clock))
        verifyClass(IPusherClientService, PusherService)


class ChannelManagementTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def test_subscribe_normal(self):
        """Client triggers subscribe on the created Channel and adds it to self.channels."""

    def test_unsubscribe_normal(self):
        """Client triggers unsubscribe on the Channel and removes it from self.channels."""

    def test_channel_lookup_normal(self):
        """Client returns the named channel if found."""

    def test_dispatches_channel_events(self):
        """Client dispatches events to appropriate Channels."""

    def test_triggers_subscribe_on_connect(self):
        """Client calls subscribe on all Channels on reconnect."""