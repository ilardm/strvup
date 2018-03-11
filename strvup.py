#!/usr/bin/env python3


import argparse
import logging, logging.config
import datetime
import iso8601
import json
import webbrowser
import urllib
import time
from xml.etree import ElementTree
from collections import OrderedDict
from requests_oauthlib import OAuth2Session
from http.server import HTTPServer, BaseHTTPRequestHandler


LOG_LEVELS = (
    'WARNING',
    'INFO',
    'DEBUG',
)

LOG_DFAULT_VERBOSITY = 'WARNING'
LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'msg': {
            'format': '%(levelname)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'msg',
        },
    },
    'loggers': {
        '__main__': {
            'level': LOG_DFAULT_VERBOSITY,
            'propagate': False,
            'handlers': ('console', ),
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ('console', ),
    }
}

LOG = None

GPX_10_NS = 'http://www.topografix.com/GPX/1/0'
GPX_11_NS = 'http://www.topografix.com/GPX/1/1'
GPXTPX_NS = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
NS = {
    'gpx10': GPX_10_NS,
    'gpx11': GPX_11_NS,
    'gpxtpx': GPXTPX_NS,
}

ACTIVITY_TYPES = (
    'ride', 'run', 'swim', 'workout', 'hike', 'walk', 'nordicski',
    'alpineski', 'backcountryski', 'iceskate', 'inlineskate',
    'kitesurf', 'rollerski', 'windsurf', 'snowboard', 'snowshoe',
    'ebikeride', 'virtualride',
)

ElementTree.register_namespace('gpx10', GPX_10_NS)
# https://stackoverflow.com/a/8998773
ElementTree.register_namespace('', GPX_11_NS)
ElementTree.register_namespace('gpxtpx', GPXTPX_NS)


def _get_log_lvl(verbosity):
    if verbosity < 0:
        return LOG_LEVELS[0]

    if verbosity > len(LOG_LEVELS)-1:
        return LOG_LEVELS[-1]

    return LOG_LEVELS[verbosity]

def _get_log_cfg(lvl):
    cfg = LOG_CONFIG.copy()
    cfg['loggers']['__main__']['level'] = lvl

    return cfg

def _configure_logging(verbosity):
    global LOG

    log_level = _get_log_lvl(verbosity)
    log_cfg = _get_log_cfg(log_level)
    logging.config.dictConfig(log_cfg)
    LOG = logging.getLogger(__name__)


class HrmParser:

    _PARSERS = {
        'Params': '_parse_params',
        'HRData': '_parse_hrm_data',
    }

    def __init__(self, path):
        self.path = path
        self.sections = {}

    @staticmethod
    def _parse_params(lines):
        data = {}
        for line in lines:
            key, value = line.split('=')
            pvalue = None

            if key == 'Date':
                pvalue = datetime.datetime.strptime(value, '%Y%m%d').date()
            elif key == 'StartTime':
                pvalue = datetime.datetime.strptime(value, '%H:%M:%S.%f').time()
            elif key == 'Interval':
                pvalue = int(value)

            if pvalue:
                data[key] = pvalue
        return data

    @staticmethod
    def _parse_hrm_data(lines):
        data = []
        for line in lines:
            # TODO: support cadence/speed/altitude/...
            values = line.split('\t')
            data.append(int(values[0]))

        return data

    def parse(self):
        c_section = ''

        with open(self.path, 'r') as ifd:
            for line in ifd:
                line = line.replace('\n', '')
                is_section = line.startswith('[') \
                             and line.endswith(']')

                if is_section:
                    c_section = line.replace('[', '').replace(']', '')
                    LOG.debug('started section %r', c_section)
                    self.sections[c_section] = []
                    continue

                is_empty = line == ''
                if is_empty:
                    LOG.debug('ended section %r', c_section)
                    c_section = ''
                    continue

                self.sections[c_section].append(line)

        LOG.debug('sctions: %r', self.sections.keys())

        for section, lines in self.sections.items():
            parser = self._PARSERS.get(section)
            if not parser:
                continue

            parser = getattr(self, parser)
            if not parser:
                continue

            LOG.debug('apply %r section parser', section)
            self.sections[section] = parser(lines)

        return self


class OAuthCallbackRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args, **kwargs):
        pass

    def do_GET(self):
        LOG.debug('callback %s: %s', self.command, self.path)

        setattr(self.server, 'auth_request', self.path)

        self.send_response(200)
        self.end_headers()

        self.wfile.write(b'OK')


def _text_converter(src, dst):
    dst.text = src.text
    return dst


def _attr_converter(src, dst):
    dst.attrib.update(src.attrib)
    return dst

_NODES = {
    'trk': {
        'childs': {
            'trkseg': {
                'childs': {
                    'trkpt': {
                        'converter': _attr_converter,
                        'childs': OrderedDict((
                            ('time', {
                                'converter': _text_converter,
                            }),
                            ('fix', {
                                'converter': _text_converter,
                            }),
                            ('sat', {
                                'converter': _text_converter,
                            }),
                        )),
                    },
                },
            },
        },
    },
}

def _convert(root_node, src_root, dst_root):
    for tag, node in root_node.items():
        query = './/gpx10:{}'.format(tag)
        post_convert = node.get('converter')
        childs = node.get('childs', {})

        for src_node in src_root.findall(query, NS):
            dst_node = ElementTree.Element('{{{}}}{}'.format(
                GPX_11_NS, tag
            ))

            if post_convert:
                dst_node = post_convert(src_node, dst_node)

            dst_node = _convert(childs, src_node, dst_node)

            dst_root.append(dst_node)

    return dst_root

def convert_gpx_trk_10_11(gpx10):
    # gpx -> trk -> trkseg -> trkpt -> [time, fix, sat]

    gpx11 = ElementTree.Element('{{{}}}gpx'.format(GPX_11_NS))
    gpx11 = _convert(_NODES, gpx10, gpx11)
    gpx11 = ElementTree.ElementTree(gpx11)

    return gpx11


def merge_gpx_hrm(gpx, hrm, tz):
    root = gpx.getroot()

    points = root.findall('.//gpx11:trkpt', NS)
    hr_start = datetime.datetime.combine(
        hrm.sections['Params']['Date'],
        hrm.sections['Params']['StartTime'],
    ).replace(tzinfo=datetime.timezone.utc)
    hr_samples = hrm.sections['HRData']

    for point in points:
        pt_time_tag = point.find('gpx11:time', NS)
        pt_time = iso8601.parse_date(pt_time_tag.text)
        pt_time_tag.text = pt_time.replace(tzinfo=tz).isoformat()

        delta = int((pt_time - hr_start).total_seconds())
        hr_sample = hr_samples[delta]

        exts = point.find('gpx11:extensions', NS)
        if exts is None:
            exts = ElementTree.SubElement(
                point, '{{{}}}extensions'.format(GPX_11_NS)
            )

        tpx = ElementTree.SubElement(
            exts, '{{{}}}TrackPointExtension'.format(GPXTPX_NS)
        )
        hr = ElementTree.SubElement(
            tpx, '{{{}}}hr'.format(GPXTPX_NS)
        )
        hr.text = str(hr_sample)

    return gpx


def check_oauth(config_path):
    LOG.debug('read oauth config')
    with open(config_path) as ifd:
        config = json.load(ifd)

    oa_client = OAuth2Session(
        client_id=config.get('client_id'),
        redirect_uri=config.get('redirect_uri'),
        scope=['write'],
        token=config.get('token'),
    )

    if oa_client.authorized:
        LOG.info('using previous authorization')
        return oa_client

    LOG.info('run authorization')

    url, _ = oa_client.authorization_url(
        'https://www.strava.com/oauth/authorize'
    )

    LOG.debug('open a browser')
    webbrowser.open(url)

    callback = urllib.parse.urlparse(config['redirect_uri'])
    httpd = HTTPServer(
        (callback.hostname, callback.port),
        OAuthCallbackRequestHandler
    )

    LOG.debug('launch http callback server')
    httpd.handle_request()
    httpd.server_close()
    LOG.debug('served callback')

    parts = urllib.parse.urlparse(getattr(httpd, 'auth_request'))
    query = urllib.parse.parse_qs(parts.query)

    LOG.debug('callback query %r', query)
    token = oa_client.fetch_token(
        'https://www.strava.com/oauth/token',
        code=query['code'][0],
        client_secret=config['client_secret'],
    )

    LOG.debug('token: %r', token)

    config['token'] = token
    with open(config_path, 'w') as ofd:
        json.dump(config, ofd, indent=2)

    return oa_client


def upload_activity(oa_client, track_path, atype=None):
    form = {
        'private': 1,
        'data_type': 'gpx',
    }

    if atype:
        form['activity_type'] = atype

    with open(track_path) as ifd:
        files = {'file': ifd}

        rsp = oa_client.post(
            'https://www.strava.com/api/v3/uploads',
            data=form, files=files
        )

    processing_status = 'Your activity is still being processed.'
    completed = False

    while not completed:
        LOG.debug('status %d; "%s"', rsp.status_code, rsp.text)

        status = rsp.json()
        LOG.info('upload %d -- %s', status['id'], status['status'])

        completed = not status['status'] == processing_status
        if not completed:
            time.sleep(2)
            url = 'https://www.strava.com/api/v3/uploads/{id}'.format(
                id=status['id']
            )
            rsp = oa_client.get(url)

    if not status['error'] == None:
        LOG.info('%s', status['error'])
    if not status['activity_id'] == None:
        activity_url = 'https://www.strava.com/activities/{id}'.format(
            id=status['activity_id']
        )
        LOG.info('Plase find your activity at %s', activity_url)


def main():
    argparser = argparse.ArgumentParser(
        description='Merge `gpx` and `hrm` files and upload to Strava'
    )
    argparser.add_argument(
        'gpx', help='.gpx input file'
    )
    argparser.add_argument(
        'hrm', help='.hrm input file'
    )
    argparser.add_argument(
        'out', help='.gpx output file'
    )
    argparser.add_argument(
        '--tz', help='timezone to use for all timestamps, [+-HHMM] format, default to UTC',
        default='+0000'
    )
    argparser.add_argument(
        '-v', help='verbosity',
        action='count', default=0,
        dest='verbosity'
    )
    argparser.add_argument(
        '--oauth', help='OAuth config path, default to ~/.config/strvup/oauth.json',
        default='~/.config/strvup/oauth.json',
    )
    argparser.add_argument(
        '--type', help='Activity type',
        choices=ACTIVITY_TYPES,
    )

    args = argparser.parse_args()
    _configure_logging(args.verbosity)

    gpx_path = args.gpx
    LOG.info('parse gpx')
    gpx10_tree = ElementTree.parse(gpx_path)

    root = gpx10_tree.getroot()
    gpx_version = root.attrib.get('version', '1.0')
    if gpx_version == '1.1':
        gpx11_tree = gpx10_tree
    else:
        LOG.info('convert gpx 1.0 -> 1.1')
        gpx11_tree = convert_gpx_trk_10_11(gpx10_tree)

    hrm_path = args.hrm
    LOG.info('parse hrm')
    hrmParser = HrmParser(hrm_path)
    hrmParser.parse()

    tz = args.tz
    tz = datetime.datetime.strptime(tz, '%z').tzinfo

    output_path = args.out

    LOG.info('merge gpx and hrm')
    merged_gpx_tree = merge_gpx_hrm(gpx11_tree, hrmParser, tz)
    root = merged_gpx_tree.getroot()
    root.attrib.update({
        'creator': 'strvup.py',
        'version': '1.1',
    })

    LOG.info('save result')
    merged_gpx_tree.write(output_path, encoding='UTF-8', xml_declaration=True)

    LOG.info('check strava authorization')
    oa_client = check_oauth(args.oauth)

    LOG.info('upload activity')
    upload_activity(oa_client, output_path, args.type)

    LOG.info('done!')


if __name__ == '__main__':
    main()
