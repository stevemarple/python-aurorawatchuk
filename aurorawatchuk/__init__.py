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
__version__ = '0.0.7'
__license__ = 'MIT'


class AuroraWatchUK(object):
    """Object from which the current and recent AuroraWatch UK status, activity and descriptions can be obtained.

    When the object is constructed ``base_url`` may be used to adjust the base URL of the AuroraWatch UK API,
    for instance to select between HTTP and HTTPS transport. The language used for descriptions, messages etc.
    can be adjusted with the ``lang`` parameter; only ``lang='en'`` is supported at present.

    By default exceptions are raised when the status, activity or descriptions cannot be fetched from
    AuroraWatch UK. In some limited cases unknown values can be returned instead of exceptions (primarily
    when such information may be included in formatted strings). Call the constructor with ``raise_=False`` to
    avoid exceptions, note the trailing underscore to avoid collision with the :keyword:`raise` keyword. When the
    status is unknown the value retrieved from ``status_color`` returned can be set with the
    ``unknown_status_color`` keyword."""

    def __init__(self,
                 base_url='http://aurorawatch-api.lancs.ac.uk/0.2/',
                 lang='en',
                 raise_=True,
                 unknown_status_color='#777777'):
        self._base_url = base_url
        self._lang = lang
        self._raise = raise_
        self._unknown_color = unknown_status_color
        init(base_url)

    def _get_expires(self, name):
        with _locks[self._base_url][name]:
            return _expires[self._base_url][name]

    @property
    def lang(self):
        """Retrieves the selected language for messages, descriptions etc. from the API Type :class:`str`."""
        return self._lang

    @property
    def status(self):
        """Retrieves the current status object. Type :class:`.Status`.

        If the current status cannot be obtained accessing this property will generate an exception, regardless of the
        constructor parameter ``raise_``."""
        return _get_data(self._base_url, self._lang, 'status')

    @property
    def status_level(self):
        """Retrieves the current status level. Type :class:`str`.

        If the :class:`.AuroraWatchUK` object was created with ``raise=True`` then accessing this property will
         generate an exception if the current status cannot be obtained. However if it was created with
         ``raise_=False`` then the status level will be returned as `unknown` if the current status cannot be
         determined."""
        if self._raise:
            return _get_data(self._base_url, self._lang, 'status').level
        else:
            try:
                return _get_data(self._base_url, self._lang, 'status').level
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
        return _get_data(self._base_url, self._lang, 'activity')

    # @property
    # def activity_expires(self):
    #     return self._get_expires('activity')

    @property
    def descriptions(self):
        """Descriptions and meanings used in the AuroraWatch UK API. Type :class:`collections.OrderedDict`.

        If the current activity cannot be obtained accessing this property will generate an exception,
        regardless of the constructor parameter ``raise_``."""
        return _get_data(self._base_url, self._lang, 'descriptions')

    # @property
    # def descriptions_expires(self):
    #     return self._get_expires('descriptions')


class Status(object):
    """AuroraWatch UK object.

    :param base_url: Base URL of the AuroraWatch UK API
    :type base_url: str.
    :param lang: Language to use for descriptions, messages etc. `lang` must be provided by the API.
    :type lang: str
    :param raise_: Raise exceptions on errors (note the trailing underscore to avoid collision with the
        keyword `raise`).
    :type raise_: bool
    :param unknown_color: RGB color value for when status cannot be determined.
    :type unknown_color: str
    :return: An object from which the current AuroraWatch UK status, activity and descriptions can be obtained.
    :rtype: :class:`.AuroraWatchUK`
    """

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
        """The status level. Type :class:`str`."""
        return self._level

    @property
    def updated(self):
        """The time status was last updated. Type :class:`datetime.datetime`."""
        return self._updated

    @property
    def messages(self):
        """A list of currently active messages. May be empty."""
        return self._messages


class Activity(object):
    """An :class:`.Activity` object holds the current and recent AuroraWatch UK activity values."""

    def __init__(self, expires, thresholds, updated, activity_values, messages):
        """Class constructor."""

        self._expires = expires
        self._thresholds = thresholds
        self._updated = updated
        self._activity_values = activity_values
        self._messages = messages

    @property
    def expires(self):
        """The expiry time, as seconds since epoch. Type :class:`float`."""
        return self._expires

    @property
    def thresholds(self):
        """The lower thresholds, in nanotesla (nT), for each activity level. Type :class:`collections.OrderedDict`."""
        return self._thresholds

    @property
    def updated(self):
        """The time status was last updated. Type :class:`datetime.datetime`."""
        return self._updated

    @property
    def all(self):
        """All activity values. Type :class:`list` of :class:`.ActivityValue` objects."""
        return self._activity_values

    @property
    def latest(self):
        """The latest activity value available. Type :class:`.ActivityValue`."""
        return self._activity_values[-1]

    @property
    def messages(self):
        """A list of currently active messages. May be empty."""
        return self._messages


class ActivityValue(object):
    """A single AuroraWatch UK activity value.

    :param level: The status level.
    :type level: str
    :param datetime: The start time of the period for which the activity value applies. Activity values are
        computed hourly.
    :type datetime: datetime.datetime
    :param value: The activity value, in units of nanotesla (nT).
    :type value: float
    :return: An object holding an AuroraWatch UK activity value and its related information.
    :rtype: :class:`.ActivityValue`
    """
    def __init__(self, level, datetime, value):
        self._level = level
        self._datetime = datetime
        self._value = value

    @property
    def level(self):
        """The status level. Type :class:`str`."""
        return self._level

    @property
    def datetime(self):
        """The start time of the period for which the activity value applies. Type :class:`datetime.datetime`.

        Activity values are computed hourly."""
        return self._datetime

    @property
    def value(self):
        """The activity value, in units of nanotesla (nT). Type :class:`float`."""
        return self._value


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


def _get_data(base_url, lang, name, bg_update=False):
    with _locks[base_url][name]:
        data = deepcopy(_data[base_url][name])
        expires = _expires[base_url][name]
        permit_bg_update = _permit_bg_update[base_url][name]
    now = time.time()
    time_left = expires - now
    if time_left > 0 and not bg_update:
        if use_disk_cache:
            if name in _min_time_left and time_left < _min_time_left[name] and permit_bg_update:
                try:
                    # Proactively update cache by forcing data to be fetched
                    logger.debug('starting new thread to update %s', name)
                    thread = threading.Thread(target=_get_data,
                                              args=(base_url, lang, name, True))
                    thread.start()
                    with _locks[base_url][name]:
                        # Don't permit any more background updates for this URL
                        _permit_bg_update[base_url][name] = False
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    logger.error('could not proactively update %s', name)
                    logger.debug(traceback.format_exc())
                    raise

        return data

    else:
        try:
            data, expires = globals()['_cache_' + name](base_url, lang)
            _save_to_cache(base_url, name, data, expires)
            if name == 'activity':
                # This is a superset of the status information so update the cache for that too
                _save_to_cache(base_url,
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


def _save_to_cache(base_url, name, data, expires):
    if use_disk_cache:
        with smart_open(_cache_files[base_url][name], 'wb') as fh:
            pickle.dump((data, expires), fh)

    with _locks[base_url][name]:
        _data[base_url][name] = deepcopy(data)
        _expires[base_url][name] = expires
        _permit_bg_update[base_url][name] = True  # Re-enable background updates for this URL


def _cache_status(base_url, lang):
    logger.debug('caching status')
    url = _urls[base_url]['status']
    req = requests.get(url, headers={'user-agent': user_agent})
    if req.status_code != 200:
        raise Exception('could not access %s' % url)

    try:
        xml_tree = etree.fromstring(req.text.encode('UTF-8'))
        if xml_tree.tag != 'current_status':
            raise Exception('incorrect root element')

        site_status = xml_tree.find('site_status')
        expires = time.mktime(datetime.datetime.strptime(req.headers['Expires'],
                                                         '%a, %d %b %Y %H:%M:%S %Z').utctimetuple())
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
    req = requests.get(url, headers={'user-agent': user_agent})
    if req.status_code != 200:
        raise Exception('could not access %s' % url)

    try:
        expires = time.mktime(datetime.datetime.strptime(req.headers['Expires'],
                                                         '%a, %d %b %Y %H:%M:%S %Z').utctimetuple())
        xml_tree = etree.fromstring(req.text.encode('UTF-8'))
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
    req = requests.get(url, headers={'user-agent': user_agent})
    if req.status_code != 200:
        raise Exception('could not access %s' % url)

    try:
        xml_tree = etree.fromstring(req.text.encode('UTF-8'))
        if xml_tree.tag != 'status_list':
            raise Exception('incorrect root element')

        expires = time.mktime(datetime.datetime.strptime(req.headers['Expires'],
                                                         '%a, %d %b %Y %H:%M:%S %Z').utctimetuple())
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
        desc_elem = mesg_elem.find("description[@lang='{lang}']".format(lang=lang))
        if desc_elem:
            mesg = {'id': mesg_elem.attrib['id'],
                    'priority': mesg_elem.attrib['priority'],
                    'description': desc_elem.text}
        url_elem = mesg_elem.find('url')
        if url_elem:
            mesg['url'] = url_elem.text

        messages.append(mesg)
    return messages

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
                cache_dir = appdirs.user_cache_dir(__name__)

            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

        if base_url not in _urls:
            _urls[base_url] = dict(status=base_url + 'status/current-status.xml',
                                   activity=base_url + 'status/alerting-site-activity.xml',
                                   descriptions=base_url + 'status-descriptions.xml')
            _cache_files[base_url] = {}
            _locks[base_url] = {}
            _expires[base_url] = {}
            _data[base_url] = {}
            _permit_bg_update[base_url] = {}
            for k, v in six.iteritems(_urls[base_url]):
                _locks[base_url][k] = threading.RLock()
                _expires[base_url][k] = 0
                _data[base_url][k] = None
                _permit_bg_update[base_url][k] = True  # Permit background updates
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

# Each lock controls access to the corresponding _expires, _data and _permit_bg_update nested dictionary values
_locks = {}
_expires = {}           # Holds expiry times from the HTTP(S) requests
_data = {}              # Holds the Python representation of the XML page
_permit_bg_update = {}  # Flags to indicate if the page can be fetched by a background thread

_min_time_left = dict(status=20,
                      descriptions=86400)
