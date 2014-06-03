#!/usr/bin/env python


class BadEventNameError(ValueError):
    """Invalid Pusher event name."""
    pass


class BadChannelNameError(ValueError):
    """Invalid Pusher channel name."""
    pass


class ConnectionError(Exception):
    """Could not perform an action due to connection state."""
