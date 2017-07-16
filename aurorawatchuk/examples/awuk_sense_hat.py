#!/usr/bin/env python

# Simple script to demonstrate setting the Raspberry Pi sense hat LEDs to the AuroraWatch UK status color
import aurorawatchuk
from sense_hat import SenseHat
import logging
import struct
import time

logger = logging.getLogger(__name__)
sense = SenseHat()
awuk = aurorawatchuk.AuroraWatchUK()

# Convert RGB color strings (#RRGGBB) to tuples
sense_color = {}
for c, v in awuk.descriptions.items():
    sense_color[c] = tuple(int(v['color'][x:x+2], 16) for x in range(1,7,2))

while True:
    sense.set_pixels([sense_color[awuk.status.level]]*64)
    time.sleep(30)
