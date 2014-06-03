#!/usr/bin/env python

import mock
from twisted.trial import unittest

# Tests needed:
# subscribe/unsubscribe (incl. channel retrieval and on-connect subscribe events)
# event dispatching to channels
# interfacing with connection (channel events, service parent)
# factory/endpoint creation?