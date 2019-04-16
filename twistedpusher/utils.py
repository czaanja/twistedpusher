#!/usr/bin/env python

import logging
from twisted.internet import error

log = logging.getLogger(__name__)


class Timeout(object):
    """
    :ivar duration: how long to wait before triggering the callback
    :type duration:  int or float

    :ivar active: whether the timeout is currently ticking down
    :type active: bool

    :ivar callback: the function to call on timeout

    :ivar timed_out: whether the timeout was triggered
    """
    def __init__(self, duration, callback, start_now=False, reactor=None):
        """
        Timeout is a way to create timeouts that call a function if the clock runs out.
        They can be started, stopped, and reset.

        :param duration: timeout length
        :type duration: int or float
        :param callback: function to call. Arguments to it can be provided in `start`
        :param start_now: whether to start the timeout on creation
        :type start_now: bool
        :param reactor: :class:`IReactorTime` provider, defaults to :class:`twisted.internet.reactor`
        """
        self._timer = None
        """:type: DelayedCall"""
        self.duration = duration
        self.callback = callback
        self.timed_out = False
        if reactor:
            self.reactor = reactor
        else:
            from twisted.internet import reactor
            self.reactor = reactor

        if start_now:
            self.start()

    @property
    def active(self):
        if self._timer:
            return self._timer.active()
        else:
            return False

    def reset(self, duration=None):
        """
        Reset the timer.

        :param duration: optional, change the Timeout's duration
        :type duration: int or float
        """
        if self._timer:
            if duration:
                self.duration = duration
            self._timer.reset(self.duration)
        else:
            log.info("Cannot reset the timeout since it is not active")

    def start(self, *args, **kwargs):
        """Start the timer. `args` and `kwargs` are passed to the callback."""
        self.timed_out = False
        if not self._timer:
            self._timer = self.reactor.callLater(self.duration, self._trigger, *args, **kwargs)
        else:
            log.debug('Timeout started while already running')

    def stop(self):
        """Stop the timer."""
        if self._timer:
            try:
                self._timer.cancel()
            except (error.AlreadyCalled, error.AlreadyCancelled, AttributeError) as e:
                log.debug("Issue canceling a timeout: {0}".format(e), exc_info=True)
            self._timer = None
            """:type: DelayedCall"""
        else:
            log.info("Cannot stop the timeout since it is not active")

    def _trigger(self, *args, **kwargs):
        """Trigger the timeout callback."""
        self._timer = None
        self.timed_out = True
        self.callback(*args, **kwargs)
