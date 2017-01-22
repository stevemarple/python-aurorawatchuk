#!/usr/bin/env python

import aurorawatchuk
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
print('Current status level: ' + aw.status)
print('Current status updated: ' + aw.status_updated.strftime('%Y-%m-%d %H:%M:%S'))

# Print the color, meaning and description for each status level
print('Status descriptions:')
desc = aw.descriptions
for status_level in desc:
    print('    Level: ' + status_level)
    print('    Color: ' + desc[status_level]['color'])
    print('    Description: ' + desc[status_level]['description'])
    print('    Meaning: ' + desc[status_level]['meaning'])


print('----------------------------')

while True:
    now = datetime.datetime.utcnow()
    print('{now:%Y-%m-%d %H:%M:%S}: {status}'.format(now=now, status=aw.status))
    time.sleep(10)
