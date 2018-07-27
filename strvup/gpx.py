import logging
import datetime
from xml.etree import ElementTree
from collections import OrderedDict
import iso8601


LOG = logging.getLogger('strvup.gpx')


GPX_10_NS = 'http://www.topografix.com/GPX/1/0'
GPX_11_NS = 'http://www.topografix.com/GPX/1/1'
GPXTPX_NS = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
NS = {
    'gpx10': GPX_10_NS,
    'gpx11': GPX_11_NS,
    'gpxtpx': GPXTPX_NS,
}

ElementTree.register_namespace('gpx10', GPX_10_NS)
# https://stackoverflow.com/a/8998773
ElementTree.register_namespace('', GPX_11_NS)
ElementTree.register_namespace('gpxtpx', GPXTPX_NS)


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


def merge_gpx_hrm(gpx, hrm, tz_offset):
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
        pt_time_tag.text = pt_time.replace(tzinfo=tz_offset).isoformat()

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
        hre = ElementTree.SubElement(
            tpx, '{{{}}}hr'.format(GPXTPX_NS)
        )
        hre.text = str(hr_sample)

    return gpx

def merge_gpxs(base, others):
    root = base.getroot()

    root_trk = root.find('.//gpx11:trk', NS)

    for other in others:
        other_root = other.getroot()

        other_trksegs = other_root.findall('.//gpx11:trkseg', NS)
        for trkseg in other_trksegs:
            root_trk.append(trkseg)

    return base
