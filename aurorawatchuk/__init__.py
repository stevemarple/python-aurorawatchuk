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
__version__ = '0.0.6'
__license__ = 'PSF'


class AuroraWatchUK(object):
    def __init__(self, base_url='http://aurorawatch-api.lancs.ac.uk/0.2/', lang='en'):
        self._base_url = base_url
        self._lang = lang
        init(base_url)

    def _get_expires(self, name):
        with _locks[self._base_url][name]:
            return _expires[self._base_url][name]

    @property
    def lang(self):
        return self._lang

    @property
    def status(self):
        return _get_data(self._base_url, self._lang, 'status')

    @property
    def status_color(self):
        return self.descriptions[self.status.level]['color']

    @property
    def activity(self):
        return _get_data(self._base_url, self._lang, 'activity')

    @property
    def activity_expires(self):
        return self._get_expires('activity')

    @property
    def descriptions(self):
        return _get_data(self._base_url, self._lang, 'descriptions')

    @property
    def descriptions_expires(self):
        return self._get_expires('descriptions')


class Status(object):
    def __init__(self, expires, level, updated, messages):
        self._expires = expires
        self._level = level
        self._updated = updated
        self._messages = messages

    @property
    def expires(self):
        return self._expires

    @property
    def level(self):
        return self._level

    @property
    def updated(self):
        return self._updated

    @property
    def messages(self):
        return self._messages


class Activity(object):
    def __init__(self, expires, thresholds, updated, activity_values, messages):
        self._expires = expires
        self._thresholds = thresholds
        self._updated = updated
        self._activity_values = activity_values
        self._messages = messages

    @property
    def expires(self):
        return self._expires

    @property
    def thresholds(self):
        return self._thresholds

    @property
    def updated(self):
        return self._updated

    @property
    def all(self):
        return self._activity_values

    @property
    def latest(self):
        return self._activity_values[-1]

    @property
    def messages(self):
        return self._messages


class ActivityValue(object):
    def __init__(self, level, datetime, value):
        self._level = level
        self._datetime = datetime
        self._value = value

    @property
    def level(self):
        return self._level

    @property
    def datetime(self):
        return self._datetime

    @property
    def value(self):
        return self._value


def _get_cache_filename(base_url, name):
    # Incorporate protocol and host. Must remove any leading '/' from the HTTP(S) path since that causes
    # os.path.join to disregrard any previous directory parts.
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
                _permit_bg_update[base_url][k] = True #  Permit background updates
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
_expires = {} # Holds expiry times from the HTTP(S) requests
_data = {} # Holds the Python representation of the XML page
_permit_bg_update = {} # Flags to indicate if the page can be fetched by a background thread

_min_time_left = dict(status=20,
                      descriptions=86400)
