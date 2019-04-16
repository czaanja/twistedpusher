#!/usr/bin/env python

import mock
from twisted.trial import unittest
from zope.interface.verify import verifyClass, verifyObject
from twisted.internet import task

from twistedpusher.interfaces import IPusherTransport
from twistedpusher.transport import Transport

from twistedpusher.test.helpers import TEST_TIMEOUT

# Note: treat Transport and Connection as a unit, so keep behaviour tests in test_connection.


class TransportTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.clock = task.Clock()
        self.tr = Transport('fake_factory', mock.Mock(), on_pusher_event=mock.Mock(), reactor=self.clock)

    def test_implements_pusher_transport_interface(self):
        """IPusherTransport is implemented"""
        verifyClass(IPusherTransport, Transport)
        verifyObject(IPusherTransport, self.tr)
