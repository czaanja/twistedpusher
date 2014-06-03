#!/usr/bin/env python

import json
from twisted.trial import unittest

from twistedpusher.events import Event, load_pusher_event, serialize_pusher_event
from twistedpusher.errors import BadEventNameError


class EventTestCase(unittest.TestCase):
    timeout = 0.1

    def test_constructor_name(self):
        """Test constructor with only name field."""
        event = Event(name='abcdefg')
        self.assertEqual(event.name, 'abcdefg')

    def test_constructor_kwargs(self):
        """Test constructor with extra fields in kwargs."""
        event = Event(name='098765', test=[], nothing=None, last='{"a": ""}')
        self.assertDictEqual(event, {'name': '098765', 'test': [], 'nothing': None, 'last': '{"a": ""}'})

    def test_attribute_and_dict_access(self):
        """Check that attributes can be accessed via attribute AND dict index."""
        event = Event(name='abcd')
        self.assertEqual(event['name'], 'abcd')
        self.assertEqual(event.name, 'abcd')


class LoadPusherEventTestCase(unittest.TestCase):
    timeout = 0.1

    def test_load_with_hashed_json_data(self):
        """Load reads the data field of pusher events correctly if it's json encoded on a 2nd pass."""
        raw = """{"event": "pusher:connection_established", "data": "{\\"socket_id\\":\\"123.456\\"}"}"""
        expected = {'name': 'pusher:connection_established', 'data': {'socket_id': '123.456'}}
        self._check_load(raw, expected)

    def test_load_with_unhashed_json_data(self):
        """Load reads the data field of pusher events correctly if it isn't doubly encoded."""
        raw = """{"event": "pusher:error", "data": {"message": "error message here", "code": 2005}}"""
        expected = {'name': 'pusher:error',
                    'data': {'message': 'error message here', 'code': 2005}}
        self._check_load(raw, expected)

    def test_load_pusher_event_with_no_data(self):
        """Load works fine with no data field on a pusher:* event."""
        raw = """{"event": "pusher:event"}"""
        self._check_load(raw, {'name': 'pusher:event', 'data': {}})

    def test_load_channel_event(self):
        """Load reads channel events."""
        raw = """ {"event": "pusher_internal:member_removed",
                    "channel": "presence-example-channel",
                    "data": "{\\"user_id\\": \\"id\\"}"} """
        expected = {'name': 'pusher_internal:member_removed',
                    'channel': 'presence-example-channel',
                    'data': {'user_id': 'id'}}

        self._check_load(raw, expected)

    def test_load_extra_keys(self):
        """Load works with unexpected event keys."""
        raw = '{"event": "evname", "data": 1, "randomfield": "aaaa", "another": {}}'
        expected = {'name': 'evname', 'data': 1, 'randomfield': 'aaaa', 'another': {}}
        self._check_load(raw, expected)

    def test_load_no_data_field(self):
        """Load reads events with no data."""
        raw = '{"event": "anevent"}'
        expected = {'name': 'anevent', 'data': {}}
        self._check_load(raw, expected)

    def test_load_invalid_no_event_name(self):
        """Load raises a BadEventNameError if there is no event name."""
        raw = '{"data": 123}'
        self.assertRaises(BadEventNameError, load_pusher_event, raw)

    def test_load_invalid_empty_str(self):
        """Load raises a ValueError if the raw event is an empty string."""
        raw = ''
        self.assertRaises(ValueError, load_pusher_event, raw)

    def _check_load(self, raw, expected_result):
        loaded = load_pusher_event(raw)
        self.assertDictEqual(loaded, expected_result)


# could replace the ev/expected pairs here with a single dict after adding auto-convert for event->name fields
class SerializePusherEventTestCase(unittest.TestCase):
    timeout = 0.1

    def test_serialize_extra_keys(self):
        """Serialize ignores unexpected extra fields."""
        ev = Event(name='n', extra_field='msg', last='msg2')
        expected = {'data': '', 'event': 'n'}
        self._check(ev, expected)

    def test_serialize_json_data(self):
        """Serialize works with a json data field."""
        ev = Event(**{'name': 'pusher:connection_established', 'data': {'socket_id': '123.456'}})
        expected = {'event': 'pusher:connection_established', 'data': {'socket_id': '123.456'}}
        # As stated in serialize:
        # Spec seems to say to serialize the data field for pusher:* events, but
        # the server rejects it.
        #expected = """{"data": "{\\"socket_id\\": \\"123.456\\"}", "event": "pusher:connection_established"}"""
        self._check(ev, expected)

    def test_serialize_str_data(self):
        """Serialize works with a string data field."""
        ev = Event(**{'name': 'pusher:connection_established', 'data': 'empty'})
        expected = {'event': 'pusher:connection_established', 'data': 'empty'}
        self._check(ev, expected)

    def test_serialize_only_name(self):
        """Serialize works with only a name set."""
        ev = Event(name='an:event')
        expected = {'data': '', 'event': 'an:event'}
        self._check(ev, expected)

    def test_serialize_channel_event(self):
        """Serialize works with channel events."""
        expected = {'event': 'some:event', 'data': 'empty', 'channel': 'yesitsachannel'}
        ev = Event(**{'name': 'some:event', 'data': 'empty', 'channel': 'yesitsachannel'})
        self._check(ev, expected)

    def test_serialize_error_no_event_name(self):
        """Serialize raises BadEventNameError with no name field."""
        ev = Event(name='')
        self.assertRaises(BadEventNameError, serialize_pusher_event, ev)

    def _check(self, event, expected_result):
        serialized = serialize_pusher_event(event)
        recreated = json.loads(serialized)
        self.assertDictEqual(recreated, expected_result)