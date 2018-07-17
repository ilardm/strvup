#!/usr/bin/env python3


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
        choices=strvup.ACTIVITY_TYPES,
    )

    args = argparser.parse_args()
    _configure_logging(args.verbosity)

    LOG.info('process files')
    strvup.process_files(args.gpx, args.hrm, args.tz, args.out)

    LOG.info('check strava authorization')
    oa_client = oauth.check_oauth(args.oauth)

    LOG.info('upload activity')
    strvup.upload_activity(oa_client, args.out, args.type)

    LOG.info('done!')


if __name__ == '__main__':
    main()
