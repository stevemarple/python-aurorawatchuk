"""Python interface to the AuroraWatch UK status API."""

from atomiccreate import smart_open
from collections import OrderedDict
from copy import deepcopy
import datetime
import importlib
import logging
import lxml.etree as etree
import os
import pickle
import requests
import six
from six.moves.configparser import SafeConfigParser
import sys
import threading
import time
import traceback

if sys.version_info[0] >= 3:
    # noinspection PyCompatibility
    from urllib.parse import urlsplit
else:
    # noinspection PyCompatibility
    from urlparse import urlsplit


__author__ = 'Steve Marple'
__version__ = '0.2.1'
__license__ = 'MIT'


default_base_url = 'http://aurorawatch-api.lancs.ac.uk/0.2/'


class AuroraWatchUK(object):
    """Class from which the current and recent AuroraWatch UK status, activity and descriptions can be obtained.

    The :class:`.AuroraWatchUK` class handles all network traffic with the AuroraWatch UK web service and automatically
    updates as information fetched expires. For time-critical applications where network delays are undesirable (for
    example the :mod:`cameralogger` module) preemptive updates can be requested; if enabled a background thread
    will initiate an update shortly before the expiry time is reached.

    Be aware that updates can occur at any time, and may occur between calls for related information. Consider using
    the snapshot version of this class, :class:`aurorawatchuk.snapshot.AuroraWatchUK_SS`, which also features lazy
    evaluation and will make network calls only if required.

    When the object is constructed ``base_url`` may be used to adjust the base URL of the AuroraWatch UK API,
    for instance to select between HTTP and HTTPS transport. The language used for descriptions, messages etc.
    can be selected with the ``lang`` parameter; only ``lang='en'`` is supported at present.

    By default exceptions are raised when the status, activity or descriptions cannot be fetched from
    AuroraWatch UK. In some limited cases unknown values can be returned instead of exceptions (primarily
    when such information may be included in formatted strings). Call the constructor with ``raise_=False`` to
    avoid exceptions, note the trailing underscore to avoid collision with the :keyword:`raise` keyword. When the
    status is unknown the value retrieved from ``status_color`` returned can be set with the
    ``unknown_status_color`` keyword."""

    def __init__(self,
                 base_url=default_base_url,
                 lang='en',
                 raise_=True,
                 unknown_status_color='#777777',
                 preemptive=False):
        self._base_url = base_url or default_base_url
        if not self._base_url.endswith('/'):
            self._base_url += '/'
        self._lang = lang
        self._raise = raise_
        self._unknown_color = unknown_status_color
        self._preemptive = preemptive
        init(self._base_url)

    def _get_expires(self, name):
        with _locks[self._base_url][name]:
            return _expires[self._base_url][name]

    def _get_data(self, name, _forced_update=False):
        with _locks[self._base_url][name]:
            data = deepcopy(_data[self._base_url][name])
            expires = _expires[self._base_url][name]
            # Only attempt a preemptive update for this location if this instance wants it AND no-one else is already
            # doing a preemptive update.
            preemptive = _permit_preemptive[self._base_url][name] and self._preemptive
        now = time.time()
        time_left = expires - now
        if time_left > 0 and not _forced_update:
            if use_disk_cache:
                if name in _min_time_left and time_left < _min_time_left[name] and preemptive:
                    try:
                        # Proactively update cache by forcing data to be fetched
                        logger.debug('starting new thread to update %s', name)
                        thread = threading.Thread(target=self._get_data,
                                                  args=(name, True))
                        thread.start()
                        with _locks[self._base_url][name]:
                            # Don't permit any more background updates for this URL
                            _permit_preemptive[self._base_url][name] = False
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        logger.error('could not proactively update %s', name)
                        logger.debug(traceback.format_exc())
                        raise

            return data

        else:
            try:
                data, expires = globals()['_cache_' + name](self._base_url, self._lang)
                _save_to_cache(self._base_url, name, data, expires)
                if name == 'activity':
                    # This is a superset of the status information so update the cache for that too
                    _save_to_cache(self._base_url,
                                   'status',
                                   Status(expires, data.latest.level, data.updated, data.messages),
                                   expires)
                return data

            except (KeyboardInterrupt, SystemExit):
                raise

            except:
                logger.error('could not get AuroraWatch UK status')
                logger.debug(traceback.format_exc())
                raise

    @property
    def lang(self):
        """Retrieves the selected language for messages, descriptions etc. from the API Type :class:`str`."""
        return self._lang

    @property
    def status(self):
        """Retrieves the current status object. Type :class:`.Status`.

        If the current status cannot be obtained accessing this property will generate an exception, regardless of the
        constructor parameter ``raise_``."""
        return self._get_data('status')

    @property
    def status_level(self):
        """Retrieves the current status level. Type :class:`str`.

        If the :class:`.AuroraWatchUK` object was created with ``raise=True`` then accessing this property will
         generate an exception if the current status cannot be obtained. However if it was created with
         ``raise_=False`` then the status level will be returned as `unknown` if the current status cannot be
         determined."""
        if self._raise:
            return self._get_data('status').level
        else:
            try:
                return self._get_data('status').level
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                return 'unknown'

    @property
    def status_color(self):
        """Retrieves the current status color as a RGB string. Type :class:`str`.

        If the :class:`.AuroraWatchUK` object was created with ``raise_=True`` then accessing this property will
        generate an exception if the current status cannot be obtained. However if it was created with
        ``raise_=False`` then ``unknown_status_color`` will be returned if the current status
        cannot be determined."""
        if self._raise:
            return self.descriptions[self.status.level]['color']
        else:
            try:
                return self.descriptions[self.status.level]['color']
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                return self._unknown_color

    @property
    def status_description(self):
        """Retrieves the description for the current alert status. Type :class:`str`.

        If the :class:`.AuroraWatchUK` object was created with ``raise_=True`` then accessing this property will
        generate an exception if the current description cannot be obtained. However if it was created with
        ``raise_=False`` then ``'Unknown'`` will be returned.

        Status descriptions are not terminated with a full stop."""
        if self._raise:
            return self.descriptions[self.status.level]['description']
        else:
            try:
                return self.descriptions[self.status.level]['description']
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                return 'Unknown'

    @property
    def status_meaning(self):
        """The meaning of the current alert status. Type :class:`str`.

        If the :class:`.AuroraWatchUK` object was created with ``raise_=True`` then accessing this property will
        generate an exception if the current description cannot be obtained. However if it was created with
        ``raise_=False`` then ``'Unknown.'`` will be returned.

        The status meanings are terminated with a full stop."""
        if self._raise:
            return self.descriptions[self.status.level]['meaning']
        else:
            try:
                return self.descriptions[self.status.level]['meaning']
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                return 'Unknown.'

    @property
    def activity(self):
        """The current activity object. Type :class:`.Activity`.

        If the current activity cannot be obtained accessing this property will generate an exception,
        regardless of the constructor parameter ``raise_``."""
        return self._get_data('activity')

    # @property
    # def activity_expires(self):
    #     return self._get_expires('activity')

    @property
    def descriptions(self):
        """Descriptions and meanings used in the AuroraWatch UK API. Type :class:`collections.OrderedDict`.

        If the current activity cannot be obtained accessing this property will generate an exception,
        regardless of the constructor parameter ``raise_``."""
        return self._get_data('descriptions')

    # @property
    # def descriptions_expires(self):
    #     return self._get_expires('descriptions')


class Status(object):
    """AuroraWatch UK current status.

    If only a minimal set of information is required (status level and messages) this class should be preferred
    over the :class:`.Activity` class as the network transfers are smaller."""

    def __init__(self, expires, level, updated, messages):
        self._expires = expires
        self._level = level
        self._updated = updated
        self._messages = messages

    @property
    def expires(self):
        """Retrieves the expiry time, as seconds since epoch. Type :class:`float`."""
        return self._expires

    @property
    def level(self):
        """Retrieves the current status level. Type :class:`str`."""
        return self._level

    @property
    def updated(self):
        """Retrieves the time status was last updated. Type :class:`datetime.datetime`."""
        return self._updated

    @property
    def messages(self):
        """Retrieves a list of currently active messages. Type :class:`.Message` or ``None``.

        The list of messages may be empty."""
        return self._messages


class Activity(object):
    """Current and recent AuroraWatch UK activity values.

     If only a minimal set of information is required (current status level and messages) then the :class:`.Status`
     class should be preferred over this class as the network transfers are smaller."""

    def __init__(self, expires, thresholds, updated, activity_values, messages):
        """Class constructor."""

        self._expires = expires
        self._thresholds = thresholds
        self._updated = updated
        self._activity_values = activity_values
        self._messages = messages

    @property
    def expires(self):
        """Retrieves the expiry time, as seconds since epoch. Type :class:`float`."""
        return self._expires

    @property
    def thresholds(self):
        """Retrieves the lower thresholds for each activity level. Type :class:`collections.OrderedDict`.

        The lower thresholds are given in units of nanotesla (nT). The activity must equal or exceed the lower
        threshold, and not equal or exceed the lower threshold of the next status level."""
        return self._thresholds

    @property
    def updated(self):
        """Retrieves the time the status was last updated. Type :class:`datetime.datetime`."""
        return self._updated

    @property
    def all(self):
        """Retrieves all activity values. Type :class:`list` of :class:`.ActivityValue` objects."""
        return self._activity_values

    @property
    def latest(self):
        """Retrieves the latest activity value available. Type :class:`.ActivityValue`."""
        return self._activity_values[-1]

    @property
    def messages(self):
        """Retrieves a list of currently active messages. Type :class:`.Message` or ``None``.

        The list of messages may be empty."""
        return self._messages


class ActivityValue(object):
    """A single AuroraWatch UK activity value."""
    def __init__(self, level, datetime, value):
        self._level = level
        self._datetime = datetime
        self._value = value

    @property
    def level(self):
        """Retrieves the status level. Type :class:`str`."""
        return self._level

    @property
    def datetime(self):
        """Retrieves the start time for the hourly activity value. Type :class:`datetime.datetime`."""
        return self._datetime

    @property
    def value(self):
        """Retrieves the activity value, in units of nanotesla (nT). Type :class:`float`.

        The activity value is an unsigned scalar value."""
        return self._value


class Message(object):
    """An AuroraWatch UK message."""

    def __init__(self, id_, priority, description, url, expires):
        self._id = id_
        self._priority = priority
        self._description = description
        self._url = url
        self._expires = expires

    @property
    def id(self):
        """Retrieves a unique identifier for the message. Type :class:`str`.

        The identifier can be used to record which messages have been presented to a user and to hide any which
        have been seen previously."""
        return self._id

    @property
    def priority(self):
        """Retrieves the priority level for a message. Type :class:`str`.

        The priority indicates what action, if any, may be appropriate. A ``'high'`` priority suggests that an
        alerting notification may be appropriate while a ``'low'`` priority suggests a silent notification may be
        more appropriate. Test messages are indicated with the priority ``'test'``. Messages with unknown
        priorities should be ignored."""
        return self._priority

    @property
    def description(self):
        """Retrieves the descriptive text of the message, in the selected language.  Type :class:`str`."""
        return self._description

    @property
    def url(self):
        """Retrieves an optional URL for the message. Type :class:`str` or ``None``.

        The URL associated with the message, if one is present, otherwise ``None``."""
        return self._url

    @property
    def expires(self):
        """Retrieves the date and time the message expires. Type :class:`datetime.datetime`.

        After the expiry time the message should not be displayed and any saved references (for
        instance recording that the message has been shown to the user) can be discarded."""
        return self._expires


def _get_cache_filename(base_url, name):
    # Incorporate protocol and host. Must remove any leading '/' from the HTTP(S) path since that causes
    # os.path.join to disregard any previous directory parts.
    p = urlsplit(_urls[base_url][name])
    return os.path.join(cache_dir, p.scheme, p.netloc, *split_dirs(p.path.lstrip('/') + '.pck'))


def _invalidate_cache(base_url, name):
    logger.warning('invalidating cache for %s (%s)' % (_urls[base_url][name], _cache_files[base_url][name]))
    if os.path.exists(_cache_files[base_url][name]):
        os.remove(_cache_files[base_url][name])


def _load_from_disk_cache(base_url, name):
    with open(_cache_files[base_url][name], 'rb') as fh:
        return pickle.load(fh)


def _save_to_cache(base_url, name, data, expires):
    if use_disk_cache:
        with smart_open(_cache_files[base_url][name], 'wb') as fh:
            pickle.dump((data, expires), fh)

    with _locks[base_url][name]:
        _data[base_url][name] = deepcopy(data)
        _expires[base_url][name] = expires
        _permit_preemptive[base_url][name] = True  # Re-enable background updates for this URL


def _read_document(url):
    if url.startswith('file:'):
        with open(url.replace('file:', '', 1)) as fh:
            return fh.read().encode('UTF-8'), round(time.time() + 180)

    req = requests.get(url, headers={'user-agent': user_agent})
    if req.status_code != 200:
        raise Exception('could not access %s' % url)
    expires = time.mktime(datetime.datetime.strptime(req.headers['Expires'],
                                                     '%a, %d %b %Y %H:%M:%S %Z').utctimetuple())
    return req.text.encode('UTF-8'), expires


def _cache_status(base_url, lang):
    logger.debug('caching status')
    url = _urls[base_url]['status']
    doc, expires = _read_document(url)

    try:
        xml_tree = etree.fromstring(doc)
        if xml_tree.tag != 'current_status':
            raise Exception('incorrect root element')

        site_status = xml_tree.find('site_status')
        r = Status(expires,
                   site_status.attrib['status_id'],
                   datetime.datetime.strptime(xml_tree.find('updated').find('datetime').text,
                                              '%Y-%m-%dT%H:%M:%S+0000'),
                   _parse_messages(xml_tree, lang))
        return r, expires
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        logger.error('could not parse status')
        _invalidate_cache(base_url, 'status')
        raise


def _cache_activity(base_url, lang):
    logger.debug('caching activity')
    url = _urls[base_url]['activity']
    doc, expires = _read_document(url)

    try:
        xml_tree = etree.fromstring(doc)
        if xml_tree.tag != 'site_activity':
            raise Exception('incorrect root element')

        thresholds = OrderedDict()
        for threshold_elem in xml_tree.findall('lower_threshold'):
            level = threshold_elem.attrib['status_id']
            thresholds[level] = float(threshold_elem.text)

        updated = datetime.datetime.strptime(xml_tree.find('updated').find('datetime').text,
                                             '%Y-%m-%dT%H:%M:%S+0000')

        activity = []
        for act_elem in xml_tree.findall('activity'):
            activity.append(ActivityValue(act_elem.attrib['status_id'],
                                          datetime.datetime.strptime(act_elem.find('datetime').text,
                                                                     '%Y-%m-%dT%H:%M:%S+0000'),
                                          float(act_elem.find('value').text)))

        messages = _parse_messages(xml_tree, lang)
        return Activity(expires, thresholds, updated, activity, messages), expires
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        logger.error('could not parse status')
        _invalidate_cache(base_url, 'status')
        raise


def _cache_descriptions(base_url, lang):
    logger.debug('caching descriptions')
    url = _urls[base_url]['descriptions']
    doc, expires = _read_document(url)

    try:
        xml_tree = etree.fromstring(doc)
        if xml_tree.tag != 'status_list':
            raise Exception('incorrect root element')

        d = OrderedDict()
        d.expires = expires
        for status_elem in xml_tree.findall('status'):
            status = status_elem.attrib['id']
            # Filter description and meaning based on chosen language
            description = status_elem.find("description[@lang='{lang}']".format(lang=lang)).text
            meaning = status_elem.find("meaning[@lang='{lang}']".format(lang=lang)).text
            d[status] = dict(color=status_elem.find('color').text,
                             description=description,
                             meaning=meaning)
        return d, expires
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        logger.error('could not parse status')
        _invalidate_cache(base_url, 'status')
        raise


def _parse_messages(xml_tree, lang):
    messages = []
    for mesg_elem in xml_tree.findall('message'):
        # Output only those messages whose description matches the required language
        desc_elem = mesg_elem.find("description[@lang='{lang}']".format(lang=lang))
        expires = datetime.datetime.strptime(mesg_elem.find('expires').find('datetime').text,
                                             '%Y-%m-%dT%H:%M:%S+0000')
        if desc_elem is not None:
            url_elem = mesg_elem.find('url')
            messages.append(Message(mesg_elem.attrib['id'],
                                    mesg_elem.attrib['priority'],
                                    desc_elem.text,
                                    url_elem.text if url_elem else None,
                                    expires))
    return messages


def _get_cache_dir(config_filename):
    config = SafeConfigParser()
    files_read = config.read(config_filename)
    if config_filename not in files_read:
        logger.warn('could not read config file %s', config_filename)
    for f in files_read:
        logger.debug('read config file %s', f)
    if config.has_option(__package__, 'cache_dir'):
        return config.get(__package__, 'cache_dir')
    else:
        return None


# Set up locks, URLs, and read in previously cached values.
def init(base_url):
    global cache_dir
    global _urls
    global _cache_files
    global _locks
    global _expires
    global _data

    with _init_lock:
        if use_disk_cache:
            if not cache_dir:
                appdirs = importlib.import_module('appdirs')
                config_filename = os.path.join(appdirs.user_config_dir(__package__), 'config.ini')
                if os.path.exists(config_filename):
                    cache_dir = _get_cache_dir(config_filename)

            if not cache_dir:
                    cache_dir = appdirs.user_cache_dir(__package__)

            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, mode=0o700)
            else:
                os.chmod(cache_dir, 0o700)

        if base_url not in _urls:
            _urls[base_url] = dict(status=base_url + 'status/current-status.xml',
                                   activity=base_url + 'status/alerting-site-activity.xml',
                                   descriptions=base_url + 'status-descriptions.xml')
            _cache_files[base_url] = {}
            _locks[base_url] = {}
            _expires[base_url] = {}
            _data[base_url] = {}
            _permit_preemptive[base_url] = {}
            for k, v in six.iteritems(_urls[base_url]):
                _locks[base_url][k] = threading.RLock()
                _expires[base_url][k] = 0
                _data[base_url][k] = None
                _permit_preemptive[base_url][k] = True  # Permit background updates
                if use_disk_cache:
                    _cache_files[base_url][k] = _get_cache_filename(base_url, k)
                    if os.path.exists(_cache_files[base_url][k]):
                        try:
                            d, expires = _load_from_disk_cache(base_url, k)
                            with _locks[base_url][k]:
                                _data[base_url][k] = d
                                _expires[base_url][k] = expires
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except:
                            logger.error('could not read %s', _cache_files[base_url][k])
                            logger.debug(traceback.format_exc())
                            _invalidate_cache(base_url, k)


def split_dirs(path):
    p = os.path.normpath(path)
    r = []
    while True:
        a, b = os.path.split(p)
        if a == '':
            r.insert(0, b)
            return r
        elif b == '':
            r.insert(0, a)
            return r
        else:
            r.insert(0, b)
            p = a


_init_lock = threading.RLock()

logger = logging.getLogger(__name__)
user_agent = 'Python AuroraWatch UK module'
use_disk_cache = True
cache_dir = None

_urls = {}
_cache_files = {}

# Each lock controls access to the corresponding _expires, _data and _permit_preemptive nested dictionary values
_locks = {}
_expires = {}            # Holds expiry times from the HTTP(S) requests
_data = {}               # Holds the Python representation of the XML page
_permit_preemptive = {}  # Flags to indicate if the page can be fetched by a background thread

_min_time_left = dict(activity=20,
                      status=20,
                      descriptions=3600)
