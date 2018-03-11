#!/usr/bin/env python3


import argparse
import logging, logging.config
import datetime
import csv
import collections


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


def parse_csv(csv_path):
    ret = {}

    with open(csv_path) as ifd:
        reader = csv.DictReader(ifd)
        for row in reader:
            hr = int(row['rate'])
            timestamp = row['dateTime']

            #10.03.2018 17:09:50
            timestamp = datetime.datetime.strptime(timestamp, '%d.%m.%Y %H:%M:%S')
            ret[timestamp] = hr

    return ret


def fill_gaps(samples):
    ret = collections.OrderedDict()

    stamps = sorted(samples.keys())
    for i in range(len(stamps)):
        stamp = stamps[i]
        sample = samples[stamp]

        ret[stamp] = sample

        if i == len(stamps) - 1:
            continue

        nstamp = stamps[i+1]
        stamp_delta = int((nstamp - stamp).total_seconds())

        if stamp_delta > 1:
            nsample = samples[nstamp]
            sample_delta = nsample - sample
            sample_step = sample_delta/stamp_delta

            for j in range(1, stamp_delta):
                nstamp = stamp + datetime.timedelta(seconds=j)
                nsample = sample + sample_step * j

                ret[nstamp] = nsample

    return ret


HEADER = """[Params]
Date={date}
StartTime={start_time}
Interval=1

[HRData]
"""


def write_hrm(samples, output_path):
    stamp = list(samples.keys())[0]
    date = stamp.date().strftime('%Y%m%d')
    start_time = stamp.time().strftime('%H:%M:%S.0')

    header = HEADER.format(date=date, start_time=start_time)

    with open(output_path, 'w') as ofd:
        ofd.write(header)

        for sample in samples.values():
            isample = int(sample)
            ofd.write('{}\n'.format(isample))


def main():
    argparser = argparse.ArgumentParser(
        description='Convert exported HR data from Mi Band Tools to minimal `hrm` file'
    )
    argparser.add_argument(
        'csv', help='.csv input file'
    )
    argparser.add_argument(
        'out', help='.hrm output file'
    )
    argparser.add_argument(
        '-v', help='verbosity',
        action='count', default=0,
        dest='verbosity'
    )

    args = argparser.parse_args()
    _configure_logging(args.verbosity)

    csv_path = args.csv
    LOG.info('parse csv')
    samples = parse_csv(csv_path)

    LOG.info('fill gaps')
    samples = fill_gaps(samples)

    output_path = args.out
    LOG.info('write hrm')
    write_hrm(samples, output_path)

    LOG.info('done!')


if __name__ == '__main__':
    main()
