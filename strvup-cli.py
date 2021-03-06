#!/usr/bin/env python3


import argparse
import logging, logging.config

from strvup import strvup


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
        'strvup': {
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
    cfg['loggers']['strvup']['level'] = lvl

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
        'files', help='.gpx input file(s)',
        nargs='+',
    )
    argparser.add_argument(
        '--tz', help='timezone to use for all timestamps, [+-HHMM] format, default to UTC',
        dest='tz_offset',
        default='+0000',
    )
    argparser.add_argument(
        '-v', help='verbosity',
        dest='verbosity',
        action='count', default=0,
    )
    argparser.add_argument(
        '--oauth', help='OAuth config path, default to ~/.config/strvup/oauth.json',
        dest='oauth_path',
        default='~/.config/strvup/oauth.json',
    )
    argparser.add_argument(
        '--type', help='Activity type',
        dest='activity_type',
        choices=strvup.ACTIVITY_TYPES,
    )
    argparser.add_argument(
        '--no-upload', help='do not upload merged files',
        action='store_true',
    )
    argparser.add_argument(
        '--save-merged', help='save merged gpx+hrm in filesystem',
        action='store_true',
    )
    argparser.add_argument(
        '--merge', help='merge multiple files into one',
        action='store_true',
    )

    args = argparser.parse_args()
    _configure_logging(args.verbosity)

    kwargs = vars(args)
    kwargs.pop('verbosity')
    strvup.run(**kwargs)


if __name__ == '__main__':
    main()
