import logging
import time
import datetime
from xml.etree import ElementTree


from . import gpx, hrmparser

LOG = logging.getLogger('strvup.strvup')


ACTIVITY_TYPES = (
    'ride', 'run', 'swim', 'workout', 'hike', 'walk', 'nordicski',
    'alpineski', 'backcountryski', 'iceskate', 'inlineskate',
    'kitesurf', 'rollerski', 'windsurf', 'snowboard', 'snowshoe',
    'ebikeride', 'virtualride',
)


def process_files(gpx_path, hrm_path, tz, out_path):
    LOG.info('parse gpx')
    gpx10_tree = ElementTree.parse(gpx_path)

    root = gpx10_tree.getroot()
    gpx_version = root.attrib.get('version', '1.0')
    if gpx_version == '1.1':
        gpx11_tree = gpx10_tree
    else:
        LOG.info('convert gpx 1.0 -> 1.1')
        gpx11_tree = gpx.convert_gpx_trk_10_11(gpx10_tree)

    LOG.info('parse hrm')
    hrmParser = hrmparser.HrmParser(hrm_path)
    hrmParser.parse()

    tz = datetime.datetime.strptime(tz, '%z').tzinfo

    LOG.info('merge gpx and hrm')
    merged_gpx_tree = gpx.merge_gpx_hrm(gpx11_tree, hrmParser, tz)
    root = merged_gpx_tree.getroot()
    root.attrib.update({
        'creator': 'strvup.py',
        'version': '1.1',
    })

    LOG.info('save result')
    merged_gpx_tree.write(out_path, encoding='UTF-8', xml_declaration=True)


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