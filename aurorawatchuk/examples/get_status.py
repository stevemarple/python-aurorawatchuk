#!/usr/bin/env python

import aurorawatchuk
import aurorawatchuk.snapshot
import datetime
import logging
import os
import time


__author__ = 'Steve Marple'
__version__ = '0.0.6'
__license__ = 'MIT'


logger = logging.getLogger(__name__)
# Set logging level to debug to that HTTP GETs are indicated
logging.basicConfig(level=logging.DEBUG)

# If desired set user agent string. Must be set before first use.
aurorawatchuk.user_agent = 'Python aurorawatchuk module (%s)' % os.path.basename(__file__)

# Creating an AuroraWatchUK object. Its fields are accessors which return the latest status and other information.
aw = aurorawatchuk.AuroraWatchUK()


# Print the current status level, and when it was updated.
print('Current status level: ' + aw.status.level)
print('Current status updated: ' + aw.status.updated.strftime('%Y-%m-%d %H:%M:%S'))

# Print the color, meaning and description for each status level
print('Status descriptions:')
desc = aw.descriptions
for status_level in desc:
    print('    Level: ' + status_level)
    print('    Color: ' + desc[status_level]['color'])
    print('    Description: ' + desc[status_level]['description'])
    print('    Meaning: ' + desc[status_level]['meaning'])


# Take a snapshot of the AuroraWatch UK status. The information will not be updated
aw_ss = aurorawatchuk.snapshot.AuroraWatchUK_SS()

while True:
    print('----------------------------')
    now = datetime.datetime.utcnow()

    # Print the snapshot taken earlier
    print('Earlier snapshot: level={aw.status.level}    updated={aw.status.updated:%Y-%m-%d %H:%M:%S}'
          .format(aw=aw_ss))

    # Print the current time
    print('{now:%Y-%m-%d %H:%M:%S}'.format(now=now))

    # Print the latest activity
    print('Latest activity:  activity={aw.activity.latest.value:.1f}  updated={aw.activity.updated:%Y-%m-%d %H:%M:%S}'
          .format(aw=aw))

    # Print the current status. Note that the status information is a subset of activity so it is generally more
    # efficient to request activity data before status (particularly when preemptive updates are needed).
    print('Current status:   level={aw.status.level}    updated={aw.status.updated:%Y-%m-%d %H:%M:%S}'
          .format(aw=aw))

    # Print messages
    # IMPORTANT: take a copy of messages as otherwise the number of messages could change between len() and loop
    # iterations.
    messages = aw.status.messages
    for n in range(len(messages)):
        print('Message #%d (priority=%s)' % (n, messages[n].priority))
        print('    ' + messages[n].description)
    time.sleep(10)
