from atomiccreate import smart_open
import pickle

import datetime
import importlib
import logging
import lxml.etree as etree
import os
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
__version__ = '0.0.0'
__license__ = 'PSF'


class AuroraWatchUK(object):
    def __init__(self, base_url='http://aurorawatch-api.lancs.ac.uk/0.2/', lang='en'):
        self._base_url = base_url
        self._lang = lang
        init(base_url)

    @property
    def lang(self):
        return self._lang

    @property
    def status(self):
        return _get_data(self._base_url, 'status')['status']

    @property
    def status_updated(self):
        return _get_data(self._base_url, 'status')['updated']

    @property
    def status_expires(self):
        return _expires[self._base_url]['status']

    @property
    def descriptions(self):
        return _get_data(self._base_url, 'descriptions')

    @property
    def descriptions_expires(self):
        return _expires[self._base_url]['descriptions']


def _get_cache_filename(base_url, name):
    return os.path.join(cache_dir, os.path.basename(urlsplit(_urls[base_url][name]).path) + '.pck')


def _invalidate_cache(base_url, name):
    logger.debug('invalidating cache for %s %s' % (base_url, name))
    if os.path.exists(_cache_files[base_url][name]):
        os.remove(_cache_files[base_url][name])


def _load_from_cache(base_url, name):
    with open(_cache_files[base_url][name]) as fh:
        return pickle.load(fh)


def _save_to_cache(base_url, name, data, expires):
    #  TO DO: needs a lock to be thread safe
    with smart_open(_cache_files[base_url][name], 'w') as fh:
        pickle.dump((data, expires), fh)


def _get_data(base_url, name, bg_update=False):
    now = time.time()
    time_left = _expires[base_url][name] - now
    if time_left > 0 and not bg_update:
        print('TIME LEFT > 0 AND NOT BG_UPDATE')
        if use_file_cache:
            if name in _min_time_left and time_left < _min_time_left[name]:
                try:
                    # Proactively update by creating a new file cache
                    logger.debug('starting new thread to update %s', name)
                    thread = threading.Thread(target=_get_data,
                                              args=(base_url, name, True))
                    thread.start()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    logger.error('could not proactively update %s', name)
                    logger.debug(traceback.format_exc())
                    raise

                # Reload from cache, it may have been updated recently
                _data[name], _expires[name] = _load_from_cache(base_url, name)
    else:
        print('MUST FETCH')
        try:
            # data, expires = getattr(self, '_cache_' + name)()
            data, expires = globals()['_cache_' + name](base_url)
            if use_file_cache:
                _save_to_cache(base_url, name, data, expires)

            if not bg_update:
                _data[base_url][name] = data
                _expires[base_url][name] = expires
            return data

        except (KeyboardInterrupt, SystemExit):
            raise

        except:
            logger.error('could not get AuroraWatch UK status')
            logger.debug(traceback.format_exc())
            raise
    return _data[base_url][name]


def _cache_status(base_url):
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
        d = dict(status=site_status.attrib['status_id'],
                 updated=datetime.datetime.strptime(xml_tree.find('updated').find('datetime').text,
                                                    '%Y-%m-%dT%H:%M:%S+0000'))
        expires = time.mktime(datetime.datetime.strptime(req.headers['Expires'],
                                                         '%a, %d %b %Y %H:%M:%S %Z').utctimetuple())
        return d, expires
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        logger.error('could not parse status')
        _invalidate_cache(base_url, 'status')
    raise


def _cache_descriptions(base_url):
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
        d = {}
        # TO DO: pull out only description and meaning which matches self._lang
        for status_elem in xml_tree.findall('status'):
            status = status_elem.attrib['id']
            description = {}
            for desc_elem in status_elem.findall('description'):
                description[desc_elem.attrib['lang']] = desc_elem.text
            meaning = {}
            for meaning_elem in status_elem.findall('meaning'):
                meaning[meaning_elem.attrib['lang']] = meaning_elem.text
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


def init(base_url):
    global cache_dir
    global _urls

    if use_file_cache:
        if not cache_dir:
            appdirs = importlib.import_module('appdirs')
            cache_dir = appdirs.user_cache_dir(__name__)

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    if base_url not in _urls:
        _urls[base_url] = dict(status=base_url + 'status/current-status.xml',
                               descriptions=base_url + 'status-descriptions.xml')
        _cache_files[base_url] = {}
        _expires[base_url] = {}
        _data[base_url] = {}
        for k, v in six.iteritems(_urls[base_url]):
            _expires[base_url][k] = 0
            _data[base_url][k] = None
            if use_file_cache:
                _cache_files[base_url][k] = _get_cache_filename(base_url, k)
                try:
                    d, expires = _load_from_cache(base_url, k)
                    _data[base_url][k] = d
                    _expires[base_url][k] = expires
                except:
                    _invalidate_cache(base_url, k)

logger = logging.getLogger(__name__)
user_agent = 'Python AuroraWatch UK module'
use_file_cache = True
cache_dir = None

_urls = {}
_cache_files = {}
_expires = {}
_data = {}

_min_time_left = dict(status=20,
                      descriptions=86400)

