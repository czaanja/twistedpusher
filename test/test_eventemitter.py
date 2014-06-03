#!/usr/bin/env python

import mock
from twisted.trial import unittest
from zope.interface.verify import verifyClass, verifyObject

from twistedpusher.interfaces import IEventEmitter
from twistedpusher.events import EventEmitter
from twistedpusher.test.helpers import FakeEvent, TEST_TIMEOUT


class EventEmitterTestCase(unittest.TestCase):
    timeout = TEST_TIMEOUT

    def setUp(self):
        self.em = EventEmitter()
        self.event = FakeEvent(name='an:event')
        self.m = mock.Mock()

    def test_bind_simple(self):
        self.em.bind('an:event', self.m)
        self.em.emit_event(self.event)
        self.m.assert_called_once_with(self.event)

    def test_bindall_simple(self):
        self.em.bind_all(self.m)
        self.em.emit_event(self.event)
        self.m.assert_called_once_with(self.event)

    def test_unbind_simple(self):
        self.em.bind('an:event', self.fail)
        self.em.unbind('an:event', self.fail)
        self.em.emit_event(self.event)

    def test_unbind_all_simple(self):
        self.em.bind_all(self.fail)
        self.em.unbind_all(self.fail)
        self.em.emit_event(self.event)

    def test_bind_unicode_event_name(self):
        """Must be able to bind to unicode event names."""
        name = u'\u03ef\u03ef\u03ef'
        event = FakeEvent(name=name)
        self.em.bind(name, self.m)
        self.em.emit_event(event)
        self.m.assert_called_once_with(event)

    def test_collapsing_of_duplicate_binds(self):
        """Avoid emitting events multiple times to duplicate bound entries."""
        # this test was bugged, fixed it with a mock.
        # Change this to call_count==1 if going back to de-duping global/local handlers.
        self.em.bind('an:event', self.m)
        self.em.bind('an:event', self.m)
        self.em.bind_all(self.m)
        self.em.bind_all(self.m)
        self.em.emit_event(self.event)
        self.assertEqual(self.m.call_count, 2)

    def test_bind_uncallable_listener_value_error(self):
        """Raise ValueError if given listener is not callable."""
        self.assertRaises(ValueError, self.em.bind, 'foo:event', {})

    def test_bind_all_uncallable_listener_value_error(self):
        """Raise ValueError if given listener is not callable."""
        self.assertRaises(ValueError, self.em.bind_all, str())

    def test_bind_emit_wrong_event(self):
        """Local listeners should not receive unrelated events."""
        self.em.bind('an:event', self.m)
        self.em.emit_event(self.event)
        self.em.emit_event(FakeEvent(name='wrong:event'))
        self.m.assert_called_once_with(self.event)

    @mock.patch('warnings.warn')
    def test_unbind_not_bound_error(self, mock_warn):
        """unbind should warn if the listener is not bound."""
        self.em.bind('an:event', self.fail)
        self.em.unbind('an:unbound_event', self.fail)
        self.assertTrue(mock_warn.called)

    @mock.patch('warnings.warn')
    def test_unbind_all_not_bound_error(self, mock_warn):
        """unbind_all should warn if the listener is not bound."""
        self.em.bind_all(self.fail)
        self.em.unbind_all(lambda _: None)
        self.assertTrue(mock_warn.called)

    def test_multiple_binds_same_event(self):
        """Emit events to all bound listeners and global listeners."""
        self.m2 = mock.Mock()
        self.m3 = mock.Mock()

        self.em.bind('wrong:event', self.fail)
        self.em.bind('an:event', self.m)
        self.em.bind('an:event', self.m2)
        self.em.bind_all(self.m3)

        self.em.emit_event(self.event)

        self.m.assert_called_once_with(self.event)
        self.m2.assert_called_once_with(self.event)
        self.m3.assert_called_once_with(self.event)

    def test_implements_interface(self):
        verifyClass(IEventEmitter, EventEmitter)
        emitter = EventEmitter()
        verifyObject(IEventEmitter, emitter)

    @mock.patch('warnings.warn')
    def test_trap_error_in_listener(self, mock_warn):
        """Errors in the listener must be trapped by EventEmitter and re-raised as a warning."""
        def bad_cb(event):
            raise AttributeError("This is an untrapped error in the listener")
        self.em.bind('an:event', bad_cb)
        self.em.emit_event(self.event)
        self.assertTrue(mock_warn.called)

    def test_reraise_assertion_errors(self):
        def raise_it(_):
            raise AssertionError()
        self.em.bind('an:event', raise_it)
        try:
            self.em.emit_event(self.event)
        except AssertionError:
            pass
        else:
            self.fail('AssertionError was trapped')