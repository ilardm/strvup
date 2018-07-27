import logging
import os
import tempfile
import time
import datetime
from xml.etree import ElementTree


from . import gpx, hrmparser, oauth

LOG = logging.getLogger('strvup.strvup')


ACTIVITY_TYPES = (
    'ride', 'run', 'swim', 'workout', 'hike', 'walk', 'nordicski',
    'alpineski', 'backcountryski', 'iceskate', 'inlineskate',
    'kitesurf', 'rollerski', 'windsurf', 'snowboard', 'snowshoe',
    'ebikeride', 'virtualride',
)


def run(files, tz_offset, oauth_path, activity_type, no_upload, save_merged, merge):
    uploads = []
    unlinks = []

    for gpxfname in files:
        LOG.info('process file %s', gpxfname)

        basename = os.path.splitext(gpxfname)[0]
        hrm = basename + '.hrm'

        if save_merged:
            out = basename + '_hrm.gpx'
        else:
            outfile = tempfile.NamedTemporaryFile(prefix='strvup', delete=False)
            out = outfile.name
            unlinks.append(out)

        LOG.debug('output file %s', out)

        process_files(gpxfname, hrm, tz_offset, out)

        uploads.append((gpxfname, out))

    if merge and len(uploads) > 1:
        if save_merged:
            base = uploads[0][0]

            filenames = [u[0] for u in uploads]
            filenames = [os.path.basename(f) for f in filenames]
            filenames = [os.path.splitext(f)[0] for f in filenames]
            filename = '_'.join(filenames) + os.path.splitext(base)[1]
            out = os.path.join(os.path.dirname(base), filename)
        else:
            outfile = tempfile.NamedTemporaryFile(prefix='strvup', delete=False)
            out = outfile.name
            unlinks.append(out)

        filenames = [u[1] for u in uploads]
        base, filenames = filenames[0], filenames[1:]

        merge_files(base, filenames, out)

        uploads = [('merged file', out)]

    if not no_upload:
        LOG.info('check strava authorization')
        oa_client = oauth.check_oauth(oauth_path)

        for original, upload in uploads:
            LOG.info('upload activity %s', original)
            upload_activity(oa_client, upload, activity_type)
    else:
        LOG.debug('no upload requested')

    if unlinks:
        for fname in unlinks:
            LOG.debug('unlink %s', fname)
            os.unlink(fname)

    LOG.info('done!')


def process_files(gpx_path, hrm_path, tz_offset, out_path):
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
    hrm_parser = hrmparser.HrmParser(hrm_path)
    hrm_parser.parse()

    tz_offset = datetime.datetime.strptime(tz_offset, '%z').tzinfo

    LOG.info('merge gpx and hrm')
    merged_gpx_tree = gpx.merge_gpx_hrm(gpx11_tree, hrm_parser, tz_offset)
    root = merged_gpx_tree.getroot()
    root.attrib.update({
        'creator': 'strvup.py',
        'version': '1.1',
    })

    LOG.info('save result')
    merged_gpx_tree.write(out_path, encoding='UTF-8', xml_declaration=True)


def merge_files(base_path, other_paths, out_path):
    LOG.debug('parse base gpx %s', base_path)
    base_tree = ElementTree.parse(base_path)

    LOG.debug('parse other gpxs %r', other_paths)
    other_trees = [ElementTree.parse(p) for p in other_paths]

    LOG.info('merge gpx files')
    merged = gpx.merge_gpxs(base_tree, other_trees)

    LOG.info('save merged result')
    merged.write(out_path, encoding='UTF-8', xml_declaration=True)


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

    error = status.get('error')
    if error is not None:
        LOG.error('%s', status['error'])

    activity_id = status.get('activity_id')
    if activity_id is not None:
        activity_url = 'https://www.strava.com/activities/{id}'.format(
            id=status['activity_id']
        )
        LOG.info('Plase find your activity at %s', activity_url)
