#!/usr/bin/env python

import mock
from twisted.trial import unittest
from twisted.internet import defer, task
from zope.interface.verify import verifyObject, verifyClass

from twistedpusher.connection import Connection
from twistedpusher.interfaces import IPusherConnection
from twistedpusher.errors import ConnectionError
from twistedpusher.test.helpers import *


class BaseConnTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.endpoint, self.proto = make_mock_endpoint()
        self.clock = task.Clock()

        try:
            handler = self.chan_event_handler
        except AttributeError:
            handler = lambda x: x

        self.conn = Connection(None,
                               self.endpoint,
                               handler,
                               reactor=self.clock)

    def connect(self):
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        self.proto.on_event(PUSHER_CONNECT_EVENT)


class ConnectionTestCase(BaseConnTestCase):
    def test_implements_pusher_connection_interface(self):
        """IPusherConnection is implemented"""
        verifyClass(IPusherConnection, Connection)
        verifyObject(IPusherConnection, Connection(None, None, lambda x: x, reactor=self.clock))

    def test_send_event_while_connected(self):
        self.connect()
        self.conn.send_event(TEST_EVENT)
        self.proto.send_event.assert_called_once_with(TEST_EVENT)

    def test_send_event_while_not_connected_raises_connection_error(self):
        self.assertRaises(ConnectionError, self.conn.send_event, FakeEvent(name='test'))

    def test_init_raises_assertion_error_with_bad_channel_event_callback(self):
        """Connection constructor raises AssertionError if on_channel_event is not callable."""
        self.assertRaises(AssertionError, Connection, None, None, {}, self.clock)


class ConnectionEventEmittingTestCase(BaseConnTestCase):
    def setUp(self):
        self.chan_event_handler = mock.Mock()
        super(ConnectionEventEmittingTestCase, self).setUp()

    def test_connecting_in_event(self):
        m = mock.Mock()
        self.conn.bind('connecting_in', m)
        self.conn.startService()
        self.assertEqual(m.call_count, 1)

    def test_state_change_events(self):
        m = mock.Mock()
        self.conn.bind('state_change', m)
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        m.assert_called_with({'name': 'state_change', 'current': 'connecting', 'previous': 'initialized'})
        self.proto.on_event(PUSHER_CONNECT_EVENT)
        m.assert_called_with({'name': 'state_change', 'current': 'connected', 'previous': 'connecting'})
        self.assertEqual(m.call_count, 2)

    @mock.patch('twistedpusher.connection.log.warning')
    def test_error_event_on_pusher_error(self, _):
        m = mock.Mock()
        self.conn.bind('error', m)
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        self.proto.on_event(FakeEvent(name='pusher:error', data={'code': 4206}))
        self.assertEqual(m.call_count, 1)


class ConnectionEventHandlingTestCase(BaseConnTestCase):
    def setUp(self):
        self.chan_event_handler = mock.Mock()
        super(ConnectionEventHandlingTestCase, self).setUp()

    def test_connect_handler_saves_socket_id(self):
        self.connect()
        self.assertEqual(self.conn.socket_id, 'a')

    def test_ping_handler_responds_with_pong(self):
        self.connect()
        self.proto.on_event(PUSHER_PING_EVENT)
        self.proto.send_event.assert_called_once_with({'name': 'pusher:pong'})

    @mock.patch('twistedpusher.connection.log.warning')
    @mock.patch('warnings.warn')
    def test_error_handler_fatal_error_warns_and_stops(self,  mock_warn, mock_log):
        """Code between 4000 and 4001 results in warning, log message, and stopped service"""
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)

        self.proto.on_event(PUSHER_FATAL_ERROR_EVENT)

        self.assertFalse(self.conn.running)
        self.assertEqual(mock_warn.call_count, 1)
        self.assertEqual(mock_log.call_count, 1)

    @mock.patch('twistedpusher.connection.log.warning')
    def test_error_handler_nonfatal_error(self, mock_log):
        """Anything else results in log message"""
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        self.proto.on_event(PUSHER_NONFATAL_ERROR_EVENT)
        self.assertTrue(self.conn.running)
        self.assertEqual(mock_log.call_count, 1)

    def test_only_channel_events_forwarded(self):
        self.connect()

        self.proto.on_event(PUSHER_PONG_EVENT)
        self.proto.on_event(TEST_CHANNEL_EVENT)
        self.chan_event_handler.assert_called_once_with(TEST_CHANNEL_EVENT)


# todo better state transition tests, so instead of IS_X@TIME_A and IS_Y@TIME_B, assert ^A->B->C$
class ConnectionStatesTestCase(BaseConnTestCase):
    def test_state_is_initialized_after_init(self):
        self.assertEqual(self.conn.state, 'initialized')

    def test_state_is_connecting_after_service_started(self):
        """Switch to connecting state after the service is started"""
        self.conn.startService()
        self.assertEqual(self.conn.state, 'connecting')

    def test_state_is_connected_after_pusher_connected_event(self):
        self.connect()
        self.assertEqual(self.conn.state, 'connected')

    def test_state_is_disconnected_after_stop_service_and_protocol_disconnected(self):
        """State=disconnecting after protocol disconnect if the service is not running."""
        self.connect()
        self.conn.stopService()
        self.proto.on_connection_lost.callback(None)
        self.assertEqual(self.conn.state, 'disconnected')

    def test_state_is_connecting_after_protocol_lost_while_running(self):
        """
        State=connecting after protocol connection lost if the
        service is running, since it will auto-reconnect.
        """
        self.connect()
        self.assertEqual(self.conn.state, 'connected')
        self.proto.on_connection_lost.callback(mock.Mock())
        self.assertEqual(self.conn.state, 'connecting')

    def test_state_is_connecting_after_connection_failure(self):
        """
        State=connecting after a protocol connection attempt fails if
        the service is running, since it will auto-reconnect.
        """
        d = defer.Deferred()
        self.endpoint.connect.side_effect = [d, defer.Deferred()]
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        self.assertEqual(self.conn.state, 'connecting')
        d.cancel()
        self.clock.advance(CONNECT_TIME)
        self.assertEqual(self.conn.state, 'connecting')

    def test_state_is_unavailable_after_problems_connecting(self):
        """State=unavailable if it's been a while since it attempted connecting."""
        self.endpoint.return_value = defer.Deferred()
        self.conn.startService()

        # just has to be more than TIME_BEFORE_UNAVAILABLE_STATE
        self.clock.advance(60)

        self.assertEqual(self.conn.state, 'unavailable')


class ConnectionTimeoutsTestCase(BaseConnTestCase):
    def test_ping_after_inactivity(self):
        """Send a pusher:ping after inactivity"""
        self.connect()
        self.clock.advance(150)

        self.proto.send_event.assert_called_once_with({'name': 'pusher:ping'})

    def test_reconnect_if_no_pong_response(self):
        """If there is no response to a pusher:ping, disconnect and then connect again."""
        self.connect()
        # let the activity timeout get triggered
        self.clock.advance(150)
        # now let the pong timeout get triggered
        self.clock.advance(30)

        # check that it called disconnect on proto
        self.assertEqual(self.proto.disconnect.call_count, 1)

        # disconnect and give it some time to reconnect
        self.proto.on_connection_lost.callback(mock.Mock())
        self.endpoint.connect.return_value = mock.Mock()
        self.clock.advance(CONNECT_TIME)

        # check that it connected again using endpoint
        self.assertEqual(self.endpoint.connect.call_count, 2)

    def test_no_reconnect_if_pong_response(self):
        """If there is a response to a pusher:ping, don't reconnect."""
        self.connect()
        self.clock.advance(150)

        self.proto.on_event(PUSHER_PONG_EVENT)
        self.assertFalse(self.proto.disconnect.called)

    def test_activity_timeout_works_multiple_times(self):
        self.connect()
        self.clock.advance(150)
        self.proto.send_event.assert_called_once_with({'name': 'pusher:ping'})
        self.assertEqual(self.proto.send_event.call_count, 1)
        self.proto.on_event(PUSHER_PONG_EVENT)
        self.clock.advance(150)
        self.assertEqual(self.proto.send_event.call_count, 2)

    def test_disconnect_during_pong_timeout_stops_pong_timer(self):
        self.connect()
        self.clock.advance(150)

        self.assertTrue(self.conn.pong_timeout.active)
        self.proto.on_connection_lost.callback(mock.Mock())
        self.assertFalse(self.conn.pong_timeout.active)


class ReconnectingTestCase(BaseConnTestCase):
    """Test auto-reconnecting."""

    def setUp(self):
        super(ReconnectingTestCase, self).setUp()
        self.d = defer.Deferred()

    def test_auto_reconnect_on_fail(self):
        """Reconnect if the connection attempt fails."""
        self.endpoint.connect.side_effect = [self.d, defer.succeed(self.proto)]

        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        self.assertEqual(self.endpoint.connect.call_count, 1)
        self.d.cancel()

        self.clock.advance(CONNECT_TIME*2)
        self.assertEqual(self.endpoint.connect.call_count, 2)

    def test_auto_reconnnect_on_lost(self):
        """Reconnect if the connection is lost."""
        self.endpoint.connect.side_effect = [defer.succeed(self.proto), defer.succeed(FakeProtocol())]
        self.connect()
        self.proto.on_connection_lost.callback(mock.Mock())
        self.clock.advance(CONNECT_TIME)
        self.assertEqual(self.endpoint.connect.call_count, 2)

    def test_auto_reconnect_on_attempt_timeout(self):
        """Try again if a connection attempt times out."""
        self.endpoint.connect.side_effect = [self.d, defer.succeed(self.proto)]
        self.conn.startService()
        # let it try to connect...
        self.clock.advance(CONNECT_TIME)
        # now trigger the timeout.
        self.clock.advance(TIMEOUT_TIME)
        # now let it try to connect again
        self.clock.advance(CONNECT_TIME*2)
        self.assertEqual(self.endpoint.connect.call_count, 2)

    def test_no_auto_reconnect_after_stop_service_if_connected(self):
        self.endpoint.connect.side_effect = [defer.succeed(self.proto), defer.succeed(FakeProtocol())]
        self.connect()
        self.conn.stopService()
        self.clock.advance(CONNECT_TIME*2)
        self.endpoint.connect.assert_called_once_with(None)

    def test_no_auto_reconnect_after_stop_service_if_connecting(self):
        self.endpoint.connect.side_effect = [self.d, defer.succeed(self.proto)]
        self.conn.startService()
        self.clock.advance(CONNECT_TIME)
        self.conn.stopService()
        self.clock.advance(CONNECT_TIME*2)
        self.endpoint.connect.assert_called_once_with(None)