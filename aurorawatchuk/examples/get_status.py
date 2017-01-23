#!/usr/bin/env python

import aurorawatchuk
import aurorawatchuk.snapshot
import datetime
import logging
import os
import time


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


print('----------------------------')
# Take a snapshot of the AuroraWatch UK status. The information will not be updated
aw_ss = aurorawatchuk.snapshot.AuroraWatchUK()

while True:
    now = datetime.datetime.utcnow()
    # Print the current status
    print('{now:%Y-%m-%d %H:%M:%S}'.format(now=now))
    print('Current status:   level={status.level} updated={status.updated:%Y-%m-%d %H:%M:%S}'
          .format(status=aw.status))

    # Print the snapshot taken earlier
    print('Earlier snapshot: level={status.level} updated={status.updated:%Y-%m-%d %H:%M:%S}'
          .format(status=aw_ss.status))

    time.sleep(10)
