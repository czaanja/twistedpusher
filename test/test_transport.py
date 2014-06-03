#!/usr/bin/env python

import mock
from twisted.trial import unittest
from zope.interface.verify import verifyClass, verifyObject

from twisted.internet import defer, task

from twistedpusher.interfaces import IPusherTransport
from twistedpusher.transport import Transport

from twistedpusher.test.helpers import CONNECT_TIME, TIMEOUT_TIME, TEST_TIMEOUT


class TransportTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.clock = task.Clock()
        self.end = mock.Mock()
        self.proto = mock.Mock()
        self.proto_on_event = mock.PropertyMock()
        type(self.proto).on_event = self.proto_on_event
        self.end.connect.return_value = defer.succeed(self.proto)
        self.on_event = mock.Mock()
        self.tr = Transport('fake_factory', self.end, on_pusher_event=self.on_event, reactor=self.clock)

    def test_implements_pusher_transport_interface(self):
        """IPusherTransport is implemented"""
        verifyClass(IPusherTransport, Transport)
        verifyObject(IPusherTransport, self.tr)

    def test_with_reactor_parameter(self):
        """Use a reactor passed at init."""
        tr = Transport(None, self.end, lambda x: x, reactor='abcdefg')
        self.assertEqual(tr.reactor, 'abcdefg')

    def test_without_reactor_parameter(self):
        """Provide a default reactor."""
        tr = Transport(None, self.end, lambda x: x)
        from twisted.internet.interfaces import IReactorTime
        verifyObject(IReactorTime, tr.reactor)

    def test_on_event_callback(self):
        """
        Call the on_event callback with pusher events received from the protocol.
        Note: currently just tests that it's assigned to protocol's on_event.
        """
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.proto_on_event.assert_called_once_with(self.on_event)

    def test_startservice_connects(self):
        """startService connects, using the endpoint's connect method."""
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.end.connect.assert_called_once_with('fake_factory')

    def test_stopservice_disconnects(self):
        """stopService disconnects, using the protocol's disconnect method."""
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.tr.stopService()

        self.proto.disconnect.assert_called_once_with()

    def test_send_event(self):
        """If send_event is called while connected, call the protocol's send_event."""
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        event = mock.Mock()
        self.tr.send_event(event)
        self.proto.send_event.assert_called_once_with(event)

    @mock.patch('warnings.warn')
    def test_send_event_disconnected_warning(self, mock_warn):
        """If send_event is called while not connected, warn and don't try to call the protocol."""
        event = mock.Mock()
        self.tr.send_event(event)
        self.assertTrue(mock_warn.called)
        self.assertEqual(self.proto.send_event.call_count, 0)


class TransportConnectionStateEventTestCase(unittest.TestCase):
    """Test that the transport emits state events properly."""
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.handler = mock.Mock()
        self.global_handler = mock.Mock()
        self.clock = task.Clock()
        self.end = mock.Mock()
        self.proto = mock.Mock()
        self.proto_on_event = mock.PropertyMock()
        type(self.proto).on_event = self.proto_on_event
        self.end.connect.return_value = defer.succeed(self.proto)
        self.on_event = mock.Mock()
        self.tr = Transport(None, self.end, on_pusher_event=self.on_event, reactor=self.clock)
        self.tr.bind_all(self.global_handler)

    def test_connecting_in_event(self):
        """Emit a connecting_in event when connecting (with a non-zero delay, but that's not tested)."""
        self.tr.bind('connecting_in', self.handler)
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.handler.assert_called_once_with({'delay': 1, 'name': 'connecting_in'})
        self.assertEqual(self.global_handler.call_count, 3)

    def test_started_connecting_event(self):
        """Emit a started_connecting event when first connecting."""
        self.tr.bind('started_connecting', self.handler)
        self.tr.startService()
        self.handler.assert_called_once_with({'name': 'started_connecting'})
        self.assertEqual(self.global_handler.call_count, 2)

    def test_no_started_connecting_event_on_2nd_try(self):
        """Don't emit a started_connecting event on additional attempts."""
        d = defer.Deferred()
        self.end.connect.side_effect = [d, defer.succeed(self.proto)]

        self.tr.bind('started_connecting', self.handler)

        self.tr.startService()
        self.clock.advance(CONNECT_TIME)

        d.cancel()
        self.clock.advance(CONNECT_TIME)

        self.assertEqual(self.global_handler.call_count, 4)
        self.assertEqual(self.handler.call_count, 1)
        self.assertEqual(self.end.connect.call_count, 2)

    def test_connected_event(self):
        """Emit a connected event when the connection is established."""
        self.tr.bind('connected', self.handler)
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.handler.assert_called_once_with({'name': 'connected'})
        self.assertEqual(self.global_handler.call_count, 3)

    def test_disconnected_event_on_lost(self):
        """Emit a disconnected event when the connection is lost."""
        d = defer.Deferred()
        on_conn_mock = mock.PropertyMock(return_value=d)
        type(self.proto).on_connection_lost = on_conn_mock
        self.tr.bind('disconnected', self.handler)
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        d.callback({})
        self.handler.assert_called_once_with({'name': 'disconnected'})

    def test_prev_state_works(self):
        first_prev_state = self.tr.prev_state
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        second_prev_state = self.tr.prev_state
        self.assertNotEqual(first_prev_state, second_prev_state)
        self.assertNotEqual(self.tr.state, self.tr.prev_state)
        self.assertEqual(second_prev_state, 'connecting')


class TransportConnectionManagementTestCase(unittest.TestCase):
    """Test auto-reconnect, startService, stopService, and reconnect."""
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.clock = task.Clock()
        self.end = mock.Mock()

        self.d = defer.Deferred()

        self.lose_conn = defer.Deferred()
        self.on_conn_lost = mock.PropertyMock(return_value=self.lose_conn)

        self.proto = mock.Mock()
        self.proto_on_event = mock.PropertyMock()
        type(self.proto).on_event = self.proto_on_event
        type(self.proto).on_connection_lost = self.on_conn_lost

        self.end.connect.return_value = defer.succeed(self.proto)
        self.on_event = mock.Mock()
        self.tr = Transport(None, self.end, on_pusher_event=self.on_event, reactor=self.clock)

    ### auto-reconnect
    def test_auto_reconnect_on_fail(self):
        """Reconnect if the connection attempt fails."""
        self.end.connect.side_effect = [self.d, defer.succeed(self.proto)]

        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.assertEqual(self.end.connect.call_count, 1)
        self.d.cancel()

        self.clock.advance(CONNECT_TIME*2)
        self.assertEqual(self.end.connect.call_count, 2)

    def test_auto_reconnnect_on_lost(self):
        """Reconnect if the connection is lost."""
        self.end.connect.side_effect = [defer.succeed(self.proto), defer.succeed(self.proto)]
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.lose_conn.callback({})
        self.clock.advance(CONNECT_TIME)
        self.assertEqual(self.end.connect.call_count, 2)

    def test_auto_reconnect_on_attempt_timeout(self):
        """Try again if a connection attempt times out."""
        self.end.connect.side_effect = [self.d, defer.succeed(self.proto)]
        self.tr.startService()
        # let it try to connect...
        self.clock.advance(CONNECT_TIME)
        # now trigger the timeout.
        self.clock.advance(TIMEOUT_TIME)
        # now let it try to connect again
        self.clock.advance(CONNECT_TIME*2)
        self.assertEqual(self.end.connect.call_count, 2)

    def test_no_auto_reconnect_after_stop_service_if_connected(self):
        self.end.connect.side_effect = [defer.succeed(self.proto), defer.succeed(self.proto)]
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.tr.stopService()
        self.clock.advance(CONNECT_TIME*2)
        self.end.connect.assert_called_once_with(None)

    def test_no_auto_reconnect_after_stop_service_if_connecting(self):
        self.end.connect.side_effect = [self.d, defer.succeed(self.proto)]
        self.tr.startService()
        self.clock.advance(CONNECT_TIME)
        self.tr.stopService()
        self.clock.advance(CONNECT_TIME*2)
        self.end.connect.assert_called_once_with(None)