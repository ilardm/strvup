#!/usr/bin/env python3


import os

import argparse
import logging, logging.config

from strvup import strvup, oauth


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
        }
    },
    'root': {
        'level': 'WARNING',
        'handlers': ('console', ),
    }
}

LOG = None


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


def main():
    argparser = argparse.ArgumentParser(
        description='Merge `gpx` and `hrm` files and upload to Strava'
    )
    argparser.add_argument(
        'gpx', help='.gpx input file(s)',
        nargs='+',
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
        choices=strvup.ACTIVITY_TYPES,
    )
    argparser.add_argument(
        '--no-upload', help='do not upload merged files',
        action='store_true',
    )

    args = argparser.parse_args()
    _configure_logging(args.verbosity)

    uploads = []

    for gpx in args.gpx:
        LOG.info('process file %s', gpx)

        basename = os.path.splitext(gpx)[0]
        hrm = basename + '.hrm'
        out = basename + '_hrm.gpx'

        strvup.process_files(gpx, hrm, args.tz, out)

        uploads.append((gpx, out))

    if not args.no_upload:
        LOG.info('check strava authorization')
        oa_client = oauth.check_oauth(args.oauth)

        for original, upload in uploads:
            LOG.info('upload activity %s', original)
            strvup.upload_activity(oa_client, upload, args.type)
    else:
        LOG.debug('no upload requested')

    LOG.info('done!')


if __name__ == '__main__':
    main()
