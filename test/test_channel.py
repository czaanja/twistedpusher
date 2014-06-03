#!/usr/bin/env python

import mock
from twisted.trial import unittest
from twisted.internet import defer

from twistedpusher.channel import Channel, buildChannel
from twistedpusher.test.helpers import FakeEvent
from twistedpusher.errors import BadChannelNameError
from twistedpusher.connection import Connection
from twistedpusher.test.helpers import TEST_TIMEOUT

CHANNEL_NAME = 'chan_name'
SUBSCRIBE_EVENT = {'data': {'channel': CHANNEL_NAME}, 'name': 'pusher:subscribe'}
UNSUBSCRIBE_EVENT = {'data': {'channel': CHANNEL_NAME}, 'name': 'pusher:unsubscribe'}


class ChannelTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.conn = mock.Mock(spec=Connection)
        self.chan = Channel(CHANNEL_NAME, self.conn)
        self.m = mock.Mock()

    def test_unicode_bad_channel_name_error(self):
        """The constructor raises BadChannelNameError on a channel name that includes invalid characters."""
        self.assertRaises(BadChannelNameError, Channel, u'asd\u03ef', None)

    def test_success_handler_emit(self):
        """Channel forwards pusher_internal:subscription_succeeded to pusher:subscription_succeeded."""
        event = FakeEvent(name='pusher_internal:subscription_succeeded')
        self.chan.bind('pusher:subscription_succeeded', self.m)
        self.chan.emit_event(event)
        self.m.assert_called_once_with(event)

    def test_subscribe(self):
        """Subscribe sends a well-formed pusher:subscribe event."""
        self.chan.subscribe()
        self.conn.send_event.assert_called_once_with(SUBSCRIBE_EVENT)

    def test_unsubscribe(self):
        """Unsubscribe sends a well-formed pusher:unsubscribe event."""
        self.chan.unsubscribe()
        self.conn.send_event.assert_called_once_with(UNSUBSCRIBE_EVENT)

    def test_subscribe_on_connect(self):
        """Automatically subscribe on connected Connection state."""
        event = FakeEvent(name='connected')
        listener = self.conn.bind.call_args[0][1]
        listener(event)
        self.conn.send_event.assert_called_once_with(SUBSCRIBE_EVENT)


class ChannelEventEmitterTestCase(unittest.TestCase):
    """This tests against Channel and not ChannelEventEmitter"""
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.chan = Channel('a_channel', mock.Mock(spec=Connection))
        self.mock_handler = mock.Mock()

        m = mock.Mock()
        m.name = 'test-event'
        m.data = '{"test_key": "test_value"}'
        self.mock_event = m

    def test_ignore_pusher_events_flag_on(self):
        event = FakeEvent(name='pusher:conn')
        self.chan.bind_all(self.fail, ignore_pusher_events=True)
        self.chan.emit_event(event)
        self.assertEqual(len(self.chan.global_listeners), 1)

    def test_ignore_pusher_events_unbind(self):
        self.chan.bind_all(self.fail, ignore_pusher_events=True)
        self.chan.unbind_all(self.fail)
        self.assertEqual(len(self.chan.global_listeners), 0)

    def test_ignore_pusher_events_flag_off(self):
        event = FakeEvent(name='pusher:conn')
        self.chan.bind_all(self.mock_handler, ignore_pusher_events=False)
        self.chan.emit_event(event)
        self.assertTrue(self.mock_handler.called)

    def test_stores_listener_with_ignore_pusher_events_flag(self):
        """
        The listener is wrapped to implement ignore_pusher_flag.
        Test that the wrapper equals the listener so it's impossible to get accidental duplicates.
        """
        def handler(_):
            pass
        self.chan.bind_all(handler, ignore_pusher_events=True)
        self.assertTrue(handler in self.chan.global_listeners)

    def test_json_data_flag(self):
        """The json_data flag enables parsing of client event data as JSON."""
        self.chan = Channel(CHANNEL_NAME, mock.Mock(), json_data=True)
        self.chan.emit_event(self.mock_event)
        self.assertDictEqual(self.mock_event.data, {'test_key': 'test_value'})

    def test_no_json_data_flag(self):
        """Without json_data set, client event data should not be parsed as json."""
        self.chan = Channel(CHANNEL_NAME, mock.Mock(), json_data=False)
        self.chan.emit_event(self.mock_event)
        self.assertEqual(self.mock_event.data, '{"test_key": "test_value"}')


class BuilderTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.conn = mock.Mock(spec=Connection)

    def test_public(self):
        """buildChannel returns a public channel where appropriate."""
        self.chan = buildChannel('channelname', self.conn)
        self.assertIsInstance(self.chan, Channel)

    def test_private(self):
        """buildChannel returns a private channel if the name starts with 'private-'."""
        self.assertRaises(NotImplementedError, buildChannel, 'private-channel', self.conn)

    def test_presence(self):
        """buildChannel returns a presence channel if the name starts with 'presence-'."""
        self.assertRaises(NotImplementedError, buildChannel, 'presence-channel', self.conn)