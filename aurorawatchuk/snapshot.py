import aurorawatchuk as aw


class AuroraWatchUK(object):
    """Take a snapshot of the AuroraWatch UK status.

    This class mimics the behaviour of the aurorawatchuk.AuroraWatchUK class but its fields are evaluated just once,
    at the time first requested. Thus the values it returns are snapshots of the status. This is useful
    when the information may be required multiple times as it avoids the possibility that the status level
    could change between uses. If the information is not required then no network traffic is generated."""
    def __init__(self, *args, **kwargs):
        object.__setattr__(self, '_awuk', aw.AuroraWatchUK(*args, **kwargs))
        object.__setattr__(self, '_fields', {})

    def __getattr__(self, item):
        if item[0] != '_':
            # Cache this item
            if item not in self._fields:
                self._fields[item] = getattr(self._awuk, item)
            return self._fields[item]

    def __setattr__(self, key, value):
        if key[0] == '_':
            raise AttributeError
        else:
            return object.__setattr__(self, key, value)

    def __delattr__(self, item):
        if item[0] == '_':
            raise AttributeError
        else:
            return object.__delattr__(self, item)

